from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import ks_2samp

EPSILON = 1e-9

TEXT_KEYWORDS = {
    "text",
    "feedback",
    "comment",
    "comments",
    "review",
    "reviews",
    "description",
    "summary",
    "notes",
    "note",
    "message",
    "body",
    "content",
    "prompt",
    "response",
    "transcript",
    "detail",
    "details",
}

IDENTIFIER_KEYWORDS = {
    "id",
    "user id",
    "user_id",
    "userid",
    "customer id",
    "customer_id",
    "customerid",
    "order id",
    "order_id",
    "orderid",
    "product id",
    "product_id",
    "productid",
    "uuid",
    "guid",
    "ssn",
    "key",
}

DATETIME_KEYWORDS = {
    "date",
    "time",
    "date/time",
    "date_time",
    "datetime",
    "timestamp",
    "created at",
    "created_at",
    "updated at",
    "updated_at",
    "order date",
    "order_date",
    "delivery date",
    "delivery_date",
}


def _bounded_similarity(difference: float, scale: float) -> float:
    """
    Convert a difference into a similarity score between 0 and 1.
    """
    if scale <= EPSILON:
        return 1.0 if difference <= EPSILON else 0.0

    normalized_difference = difference / scale

    return max(
        0.0,
        1.0 - min(normalized_difference, 1.0),
    )


def _evaluate_numerical_column(
    real_series: pd.Series,
    synthetic_series: pd.Series,
) -> dict:
    """
    Evaluate one numerical column using:
    - mean similarity
    - standard deviation similarity
    - KS distribution similarity
    """
    real_values = pd.to_numeric(
        real_series,
        errors="coerce",
    ).dropna()

    synthetic_values = pd.to_numeric(
        synthetic_series,
        errors="coerce",
    ).dropna()

    if len(real_values) < 2 or len(synthetic_values) < 2:
        return {
            "column_type": "numerical",
            "status": "insufficient_data",
            "reason": "insufficient_numerical_data",
            "score": None,
        }

    real_mean = float(real_values.mean())
    synthetic_mean = float(synthetic_values.mean())

    real_std = float(real_values.std())
    synthetic_std = float(synthetic_values.std())

    mean_difference = abs(real_mean - synthetic_mean)
    std_difference = abs(real_std - synthetic_std)

    mean_similarity = _bounded_similarity(
        difference=mean_difference,
        scale=max(abs(real_std), EPSILON),
    )

    std_similarity = _bounded_similarity(
        difference=std_difference,
        scale=max(abs(real_std), EPSILON),
    )

    ks_result = ks_2samp(
        real_values,
        synthetic_values,
    )

    ks_statistic = float(ks_result.statistic)
    ks_similarity = max(0.0, 1.0 - ks_statistic)

    column_score = float(
        np.mean(
            [
                mean_similarity,
                std_similarity,
                ks_similarity,
            ]
        )
    )

    return {
        "column_type": "numerical",
        "status": "evaluated",
        "source": {
            "mean": real_mean,
            "std": real_std,
            "min": float(real_values.min()),
            "max": float(real_values.max()),
        },
        "synthetic": {
            "mean": synthetic_mean,
            "std": synthetic_std,
            "min": float(synthetic_values.min()),
            "max": float(synthetic_values.max()),
        },
        "metrics": {
            "mean_similarity": round(mean_similarity, 4),
            "std_similarity": round(std_similarity, 4),
            "ks_statistic": round(ks_statistic, 4),
            "ks_similarity": round(ks_similarity, 4),
        },
        "score": round(column_score * 100, 2),
    }


def _evaluate_categorical_column(
    real_series: pd.Series,
    synthetic_series: pd.Series,
) -> dict:
    """
    Evaluate one categorical column using
    Jensen-Shannon distribution similarity.
    """
    real_values = real_series.dropna().astype(str)
    synthetic_values = synthetic_series.dropna().astype(str)

    if len(real_values) == 0 or len(synthetic_values) == 0:
        return {
            "column_type": "categorical",
            "status": "insufficient_data",
            "reason": "insufficient_categorical_data",
            "score": None,
        }

    real_distribution = real_values.value_counts(normalize=True)
    synthetic_distribution = synthetic_values.value_counts(normalize=True)

    categories = sorted(
        set(real_distribution.index) | set(synthetic_distribution.index)
    )

    real_probabilities = np.array(
        [real_distribution.get(category, 0.0) for category in categories],
        dtype=float,
    )

    synthetic_probabilities = np.array(
        [synthetic_distribution.get(category, 0.0) for category in categories],
        dtype=float,
    )

    js_distance = float(
        jensenshannon(
            real_probabilities,
            synthetic_probabilities,
            base=2,
        )
    )

    if np.isnan(js_distance):
        categorical_similarity = 0.0
        js_distance = 1.0
    else:
        categorical_similarity = max(0.0, 1.0 - js_distance)

    return {
        "column_type": "categorical",
        "status": "evaluated",
        "category_count": len(categories),
        "metrics": {
            "js_distance": round(js_distance, 4),
            "distribution_similarity": round(categorical_similarity, 4),
        },
        "score": round(categorical_similarity * 100, 2),
    }


def _is_datetime_series(series: pd.Series) -> bool:
    """Check if series contains date or datetime values."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    # Avoid attempting on purely numerical series
    if pd.api.types.is_numeric_dtype(series):
        return False

    sample = series.dropna().astype(str).head(20)
    if sample.empty:
        return False

    # Check for date-like regex or datetime parsing
    date_patterns = [
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}",
        r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}",
    ]
    matches = 0
    for val in sample:
        val_clean = val.strip()
        if any(re.match(pat, val_clean) for pat in date_patterns):
            matches += 1

    if matches / len(sample) >= 0.5:
        return True

    # Try pd.to_datetime on sample
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            converted = pd.to_datetime(sample, errors="coerce")
        if converted.notna().mean() >= 0.7:
            return True
    except Exception:
        pass

    return False


def _is_text_series(series: pd.Series) -> bool:
    """Check if series looks like free-form text."""
    if not (
        pd.api.types.is_string_dtype(series)
        or pd.api.types.is_object_dtype(series)
    ):
        return False

    sample = series.dropna().astype(str).head(30)
    if sample.empty:
        return False

    avg_len = sample.str.len().mean()
    # If average length is long (> 30 characters) or average word count is high (> 3 words)
    avg_words = sample.apply(lambda s: len(s.split())).mean()
    unique_ratio = sample.nunique() / len(sample)

    if (avg_len > 35 or avg_words > 4) and unique_ratio > 0.4:
        return True

    return False


def _is_identifier_series(series: pd.Series) -> bool:
    """Check if series contains identifier-like tokens/UUIDs."""
    sample = series.dropna().astype(str).head(30)
    if sample.empty:
        return False

    uuid_pattern = r"^[0-9a-fA-F-]{8,36}$"
    if sample.str.match(uuid_pattern).mean() >= 0.8:
        return True

    return False


def determine_column_eligibility(
    column_name: str,
    real_series: pd.Series,
    configuration: dict | None = None,
    profile_column: dict | None = None,
) -> tuple[str, str | None, str]:
    """
    Determine eligibility of a column for statistical similarity.

    Returns:
        (status, reason, column_type)
        where status is 'evaluated' or 'excluded'
    """
    norm_name = column_name.strip().lower()

    # -------------------------------------------------------------
    # 1. Use existing configuration metadata if available
    # -------------------------------------------------------------
    if configuration:
        action = str(configuration.get("action", "")).lower()
        col_type = str(configuration.get("column_type", "")).lower()
        is_ident = bool(configuration.get("is_identifier", False))

        if is_ident or action == "new_id" or col_type in ("identifier", "id"):
            return "excluded", "identifier", "identifier"

        if action in ("llm", "text") or col_type in ("text", "free_form_text"):
            return "excluded", "free_form_text", "free_form_text"

        if col_type in ("date", "datetime", "timestamp"):
            return "excluded", "datetime_not_supported", "datetime"

    # -------------------------------------------------------------
    # 2. Use existing profiling metadata if available
    # -------------------------------------------------------------
    if profile_column:
        classification = str(profile_column.get("classification", "")).lower()
        patterns = [
            p.lower() for p in profile_column.get("patterns", []) or []
        ]

        if (
            classification in ("identifier", "id")
            or profile_column.get("is_identifier")
            or "uuid" in patterns
        ):
            return "excluded", "identifier", "identifier"

        if classification in ("text", "free_form_text"):
            return "excluded", "free_form_text", "free_form_text"

        if classification in ("date", "datetime", "timestamp"):
            return "excluded", "datetime_not_supported", "datetime"

    # -------------------------------------------------------------
    # 3. Dynamic Name & Content Matching
    # -------------------------------------------------------------
    # 3a. Identifier check
    if (
        norm_name in IDENTIFIER_KEYWORDS
        or norm_name.endswith("_id")
        or norm_name.endswith(" id")
        or norm_name.startswith("id_")
        or norm_name.startswith("id ")
        or _is_identifier_series(real_series)
    ):
        return "excluded", "identifier", "identifier"

    # 3b. Free-form text check
    if norm_name in TEXT_KEYWORDS or any(
        kw in norm_name.split() for kw in TEXT_KEYWORDS
    ) or _is_text_series(real_series):
        return "excluded", "free_form_text", "free_form_text"

    # 3c. Datetime check
    if (
        norm_name in DATETIME_KEYWORDS
        or any(kw in norm_name for kw in ("date", "datetime", "timestamp"))
        or _is_datetime_series(real_series)
    ):
        return "excluded", "datetime_not_supported", "datetime"

    # 3d. Numerical check
    if pd.api.types.is_numeric_dtype(real_series):
        return "evaluated", None, "numerical"

    # 3e. Categorical check
    if (
        pd.api.types.is_string_dtype(real_series)
        or pd.api.types.is_object_dtype(real_series)
        or pd.api.types.is_bool_dtype(real_series)
        or pd.api.types.is_categorical_dtype(real_series)
    ):
        return "evaluated", None, "categorical"

    return "excluded", "unsupported_data_type", "unsupported"


def evaluate_statistical_similarity(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    column_configurations: list[dict] | None = None,
    dataset_profile: dict | None = None,
) -> dict:
    """
    Evaluate statistical similarity between real and synthetic datasets.

    Preserves correct categorical (JS distance) and numerical (Mean, Std, KS)
    metrics, while properly excluding:
    - Free-form text (status: 'excluded', reason: 'free_form_text')
    - Identifiers (status: 'excluded', reason: 'identifier')
    - Datetime (status: 'excluded', reason: 'datetime_not_supported')

    Only evaluated columns contribute to overall_score.
    If no evaluated columns exist, overall_score is None with a meaningful message.
    """
    if real_dataframe.empty:
        raise ValueError("Real dataset is empty.")

    if synthetic_dataframe.empty:
        raise ValueError("Synthetic dataset is empty.")

    common_columns = [
        column
        for column in real_dataframe.columns
        if column in synthetic_dataframe.columns
    ]

    if not common_columns:
        raise ValueError(
            "No common columns found between real and synthetic datasets."
        )

    # Index configurations by column name
    config_map = {}
    if column_configurations:
        for cfg in column_configurations:
            if isinstance(cfg, dict) and "column_name" in cfg:
                config_map[cfg["column_name"]] = cfg

    # Index profile by column name
    profile_map = {}
    if dataset_profile and isinstance(dataset_profile, dict):
        col_info = dataset_profile.get("column_information") or dataset_profile.get("columns") or []
        if isinstance(col_info, list):
            for col_prof in col_info:
                if isinstance(col_prof, dict) and "column_name" in col_prof:
                    profile_map[col_prof["column_name"]] = col_prof
        elif isinstance(col_info, dict):
            profile_map = col_info

    column_results: dict[str, dict[str, Any]] = {}
    valid_scores: list[float] = []

    for column in common_columns:
        real_series = real_dataframe[column]
        synthetic_series = synthetic_dataframe[column]

        cfg = config_map.get(column)
        prof = profile_map.get(column)

        status, reason, col_type = determine_column_eligibility(
            column_name=column,
            real_series=real_series,
            configuration=cfg,
            profile_column=prof,
        )

        if status == "excluded":
            column_results[column] = {
                "column_type": col_type,
                "status": "excluded",
                "reason": reason,
                "score": None,
            }
            continue

        if col_type == "numerical":
            result = _evaluate_numerical_column(
                real_series=real_series,
                synthetic_series=synthetic_series,
            )
        elif col_type == "categorical":
            result = _evaluate_categorical_column(
                real_series=real_series,
                synthetic_series=synthetic_series,
            )
        else:
            result = {
                "column_type": col_type,
                "status": "excluded",
                "reason": reason or "unsupported_data_type",
                "score": None,
            }

        column_results[column] = result

        if result.get("status") == "evaluated" and result.get("score") is not None:
            valid_scores.append(float(result["score"]))

    evaluated_count = len(valid_scores)
    excluded_count = sum(
        1 for r in column_results.values() if r.get("status") == "excluded"
    )

    if valid_scores:
        overall_score = round(float(np.mean(valid_scores)), 2)
        message = "Statistical evaluation completed successfully."
    else:
        overall_score = None
        message = (
            "No applicable numerical or categorical columns were evaluated."
        )

    return {
        "metric": "statistical_similarity",
        "overall_score": overall_score,
        "evaluated_columns": evaluated_count,
        "excluded_columns": excluded_count,
        "total_common_columns": len(common_columns),
        "columns": column_results,
        "message": message,
    }