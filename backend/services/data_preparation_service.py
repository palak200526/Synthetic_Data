"""Automatic categorical encoding for Datrixa's downstream ML preprocessing.

No UI choice or database field is required: candidate encodings are evaluated
from the current column's cardinality, frequency distribution, and dimensional
cost. The chosen method and candidate scores are returned in encoding_metadata.
Synthetic-data generation deliberately bypasses this service in
preprocessing_service.py so generators retain the uploaded schema.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

import pandas as pd


def _is_categorical(series: pd.Series) -> bool:
    dtype = series.dtype
    return (
        pd.api.types.is_string_dtype(dtype)
        or pd.api.types.is_object_dtype(dtype)
        or pd.api.types.is_bool_dtype(dtype)
        or isinstance(dtype, pd.CategoricalDtype)
    )


def _is_identifier_like(column: str, series: pd.Series, unique_count: int) -> bool:
    name = str(column).strip().lower()
    name_hint = (
        name in {"id", "uuid", "guid", "pk", "primary_key", "record_id"}
        or name.endswith("_id")
        or name.endswith(" id")
        or name.endswith("_uuid")
        or name.endswith("_key")
    )
    unique_ratio = unique_count / max(1, len(series))
    # A nearly unique free-text column is also expensive and usually not a
    # meaningful categorical feature, even if its name does not say "id".
    return name_hint or (len(series) >= 20 and unique_ratio >= 0.98)


def _stable_categories(series: pd.Series) -> list[str]:
    return sorted(series.dropna().astype(str).unique().tolist())


def _hash_bucket(value: str, n_features: int) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % n_features


def _candidate_scores(series: pd.Series, unique_count: int, max_categories: int,
                      hashing_features: int) -> dict[str, dict[str, float]]:
    """Estimate quality/cost trade-offs without a target variable.

    These are selection scores, not a claim that one encoding is universally
    best. A target-aware benchmark would be needed to measure downstream model
    accuracy. Lower score is preferred.
    """
    n_rows = max(1, len(series))
    missing_present = bool(series.isna().any())
    category_count = unique_count + int(missing_present)
    onehot_dims = max(1, category_count)
    binary_dims = max(1, math.ceil(math.log2(max(2, category_count))))
    hash_dims = max(2, min(int(hashing_features), 256))

    # Repeated category frequencies make frequency/count encoding lossy when
    # different categories occur equally often. Estimate that collision rate.
    values = series.astype("string").fillna("__MISSING__")
    frequencies = values.value_counts(dropna=False)
    frequency_group_sizes = frequencies.value_counts()
    repeated_category_count = int(frequency_group_sizes[frequency_group_sizes > 1].sum())
    frequency_loss = min(1.0, repeated_category_count / max(1, category_count))

    # Hashing collision estimate from the birthday approximation.
    hash_collision = min(1.0, (category_count * max(0, category_count - 1)) / (2 * hash_dims))
    hash_collision = min(1.0, hash_collision / max(1, category_count))

    # Normalize dimensionality against the source cardinality, with a small
    # floor so a one-column encoding is not treated as cost-free.
    def complexity(dimensions: int) -> float:
        # Use an absolute feature budget, not a fraction of source cardinality.
        return min(1.0, dimensions / max(1, max_categories))

    # Lower is better. One-hot is lossless but costs one feature/category;
    # binary is compact but has arbitrary bit patterns; frequency/count are
    # compact but may map different categories to the same value; hashing may
    # collide. These are transparent heuristic costs, not measured model scores.
    raw = {
        "onehot": (0.05 + 0.40 * complexity(onehot_dims), onehot_dims),
        "binary": (0.18 + 0.04 * complexity(binary_dims), binary_dims),
        "frequency": (0.18 + 0.35 * frequency_loss, 1),
        "count": (0.20 + 0.35 * frequency_loss, 1),
        "hashing": (0.22 + 0.30 * hash_collision + 0.03 * complexity(hash_dims), hash_dims),
    }

    # One-hot is normally best for low cardinality; binary wins once a one-hot
    # expansion becomes comparatively wide. For high cardinality, frequency
    # and hashing compete on estimated information loss versus size.
    scores = {
        method: {"score": round(float(score), 4), "output_dimensions": float(dims)}
        for method, (score, dims) in raw.items()
    }
    return scores


def _choose_method(column: str, series: pd.Series, unique_count: int,
                   max_categories: int, hashing_features: int) -> tuple[str, dict[str, dict[str, float]], str | None]:
    if unique_count <= 1:
        return "skip_constant", {}, "Column has at most one non-null category."
    if _is_identifier_like(column, series, unique_count):
        return "skip_identifier", {}, "Identifier-like or almost-unique column; encoding could add noise or excessive dimensions."

    # Avoid treating long free-form text as ordinary categorical features.
    non_null = series.dropna().astype(str)
    if len(non_null) and non_null.str.len().median() >= 80 and unique_count / max(1, len(series)) > 0.2:
        return "skip_free_text", {}, "High-cardinality free-form text should be handled as text, not categorical encoding."

    scores = _candidate_scores(series, unique_count, max_categories, hashing_features)
    # Select the lowest-scoring method; no cardinality override forces One-Hot.
    method = min(scores, key=lambda name: scores[name]["score"])
    return method, scores, None


def prepare_data_for_model(
    dataframe: pd.DataFrame,
    skip_columns=None,
    max_categories: int = 30,
    hashing_features: int = 8,
):
    """Automatically compare encoding candidates and apply the selected method.

    The caller never has to choose an encoding. Results include the selected
    method, candidate scores, and fitted mappings for diagnostics/reuse.
    """
    dataframe = dataframe.copy()
    skip = set(skip_columns or [])
    original_numeric = dataframe.select_dtypes(include="number").columns.tolist()
    categorical_columns: list[str] = []
    metadata: dict[str, Any] = {}

    candidates = [column for column in dataframe.columns
                  if column not in skip and _is_categorical(dataframe[column])]

    for column in candidates:
        series = dataframe[column]
        unique_count = int(series.nunique(dropna=True))
        method, scores, reason = _choose_method(
            str(column), series, unique_count, max_categories, hashing_features
        )
        if method.startswith("skip_"):
            metadata[column] = {
                "selected_method": method,
                "reason": reason,
                "candidate_scores": scores,
            }
            continue

        categorical_columns.append(column)
        text_values = series.astype("string").fillna("__MISSING__")
        categories = _stable_categories(series)
        info: dict[str, Any] = {
            "selected_method": method,
            "candidate_scores": scores,
            "category_count": unique_count,
            "categories": categories,
        }

        if method == "onehot":
            dummies = pd.get_dummies(text_values, prefix=column, dtype=int)
            dataframe = dataframe.drop(columns=[column]).join(dummies)
            info["output_columns"] = list(dummies.columns)
        elif method == "binary":
            mapping = {value: index for index, value in enumerate(categories)}
            mapping["__MISSING__"] = len(mapping)
            codes = text_values.map(mapping).fillna(len(mapping)).astype(int)
            width = max(1, math.ceil(math.log2(max(2, len(mapping)))))
            dataframe = dataframe.drop(columns=[column])
            output_columns = []
            for bit in range(width):
                output_column = f"{column}_bin_{bit}"
                dataframe[output_column] = codes.map(lambda code: (int(code) >> bit) & 1).astype("int8")
                output_columns.append(output_column)
            info.update({"mapping": mapping, "width": width, "output_columns": output_columns})
        elif method in {"frequency", "count"}:
            counts = text_values.value_counts(dropna=False)
            values = counts / max(1, len(text_values)) if method == "frequency" else counts
            mapping = {str(key): (float(value) if method == "frequency" else int(value))
                       for key, value in values.items()}
            dataframe[column] = text_values.map(mapping).fillna(0)
            info.update({"mapping": mapping, "unknown_value": 0})
        elif method == "hashing":
            n_features = max(2, min(int(hashing_features), 256))
            buckets = text_values.map(lambda value: _hash_bucket(str(value), n_features))
            dataframe = dataframe.drop(columns=[column])
            output_columns = []
            for bucket in range(n_features):
                output_column = f"{column}_hash_{bucket}"
                dataframe[output_column] = (buckets == bucket).astype("int8")
                output_columns.append(output_column)
            info.update({
                "n_features": n_features,
                "output_columns": output_columns,
                "warning": "Hash collisions are possible; inverse transformation is not exact.",
            })
        metadata[column] = info

    return {
        "dataframe": dataframe,
        "numerical_columns": dataframe.select_dtypes(include="number").columns.tolist() or original_numeric,
        "categorical_columns": categorical_columns,
        "encoding_metadata": metadata,
    }
