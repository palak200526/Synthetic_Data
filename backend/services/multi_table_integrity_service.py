"""
Integrity helpers for multi-table (parent/child) synthetic generation.

The single-table pipeline (generation_service.generate_rows) already detects
derived columns and regenerates IDs.  The multi-table path used to fit the
model on the raw dataframes, which let the model invent:

    * duplicate primary keys            (purchase_order_id repeated)
    * derived values that don't add up  (total_amount != quantity * unit_price)
    * names that no longer match the ID (SUP001 -> "Supplier 18")
    * collapsed categories              (only Approved / Cancelled, all active = Yes)

This module fixes each of those *in the data itself*:

    prepare_training_frame()   -> what the model should (and should not) learn
    postprocess_generated()    -> restore IDs, derived values, decimals, categories
    apply_key_functions()      -> recompute columns that are a pure function of a key
    validate_linked_tables()   -> hard checks, returned with the generation result
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backend.services.id_pattern_service import generate_ids_like
from backend.services.quality_enhancement_service import (
    apply_derived_features,
    detect_derived_features,
)

logger = logging.getLogger(__name__)

MAX_CATEGORIES = 20
MAX_NUMERIC_COLUMNS_FOR_RULES = 40
MAX_DECIMALS = 6

_ID_NAME_PATTERN = re.compile(
    r"(^|_)(id|key|code|uuid|ref|no|number)(_|$)|id$",
    re.IGNORECASE,
)


# ----------------------------------------------------------------------
# Profile
# ----------------------------------------------------------------------

@dataclass
class TableProfile:
    # unique, id-like columns that are NOT part of a configured relationship
    id_columns: list[str] = field(default_factory=list)
    # relationship key columns (parent PK / child FK) - rebuilt by the linker
    relationship_columns: list[str] = field(default_factory=list)
    # arithmetic rules, e.g. total_amount = quantity * unit_price
    derived_rules: list[dict[str, Any]] = field(default_factory=list)
    # {key column: [columns that are a pure function of that key]}
    key_function_columns: dict[str, list[str]] = field(default_factory=dict)
    # {column: number of decimals found in the original data}
    decimals: dict[str, int] = field(default_factory=dict)
    # low-cardinality categorical columns whose distribution must be kept
    categorical_columns: list[str] = field(default_factory=list)

    @property
    def derived_targets(self) -> list[str]:
        return [r["target"] for r in self.derived_rules if r.get("target")]

    @property
    def columns_not_modelled(self) -> list[str]:
        cols = set(self.id_columns) | set(self.relationship_columns)
        cols |= set(self.derived_targets)
        for fn_cols in self.key_function_columns.values():
            cols |= set(fn_cols)
        return list(cols)


# ----------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------

def _looks_like_id(name: str) -> bool:
    return bool(_ID_NAME_PATTERN.search(str(name)))


def _find_id_columns(df: pd.DataFrame, exclude: set[str]) -> list[str]:
    columns = []
    if len(df) < 2:
        return columns
    for column in df.columns:
        if column in exclude or not _looks_like_id(column):
            continue
        series = df[column]
        if series.isna().any() or not series.is_unique:
            continue
        if pd.api.types.is_float_dtype(series):
            continue
        columns.append(column)
    return columns


def _last_number(value: Any) -> int | None:
    groups = re.findall(r"\d+", str(value))
    return int(groups[-1]) if groups else None


def _find_key_function_columns(
    df: pd.DataFrame,
    key_column: str,
    exclude: set[str],
) -> list[str]:
    """
    Text columns that are unique and carry the same trailing number as the key
    (SUP017 <-> "Supplier 17").  Such columns are a function of the key and
    must be rebuilt from it instead of being modelled independently.
    """
    columns = []
    if key_column not in df.columns or len(df) < 2:
        return columns
    keys = df[key_column].tolist()
    for column in df.columns:
        if column == key_column or column in exclude:
            continue
        series = df[column]
        if not (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
        ):
            continue
        if series.isna().any() or not series.is_unique:
            continue
        matches = 0
        for key, value in zip(keys, series.tolist()):
            a, b = _last_number(key), _last_number(value)
            if a is not None and b is not None and a == b:
                matches += 1
        if matches / len(df) >= 0.95:
            columns.append(column)
    return columns


def _infer_decimals(series: pd.Series) -> int | None:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if values.size == 0:
        return None
    for decimals in range(MAX_DECIMALS + 1):
        if np.allclose(values, np.round(values, decimals), atol=1e-9):
            return decimals
    return None


def analyze_table(
    original: pd.DataFrame,
    parent_key_columns: set[str] | None = None,
    foreign_key_columns: set[str] | None = None,
) -> TableProfile:
    profile = TableProfile()
    parent_key_columns = set(parent_key_columns or set())
    foreign_key_columns = set(foreign_key_columns or set())
    relationship_columns = parent_key_columns | foreign_key_columns
    profile.relationship_columns = [
        c for c in original.columns if c in relationship_columns
    ]

    profile.id_columns = _find_id_columns(original, exclude=relationship_columns)

    # Columns that are a function of a (parent) key, e.g. supplier_name
    protected = set(relationship_columns) | set(profile.id_columns)
    for key_column in parent_key_columns:
        fn_cols = _find_key_function_columns(original, key_column, exclude=protected)
        if fn_cols:
            profile.key_function_columns[key_column] = fn_cols

    # Arithmetic rules (A * B = C ...) on numeric, non-id columns
    numeric = [
        c
        for c in original.select_dtypes(include="number").columns
        if c not in protected
    ]
    if 3 <= len(numeric) <= MAX_NUMERIC_COLUMNS_FOR_RULES:
        try:
            rules = detect_derived_features(original[numeric])
            profile.derived_rules = [
                r for r in rules if r.get("type") == "arithmetic"
            ]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Derived-rule detection failed: %s", exc)

    # Decimal precision of float columns
    for column in original.select_dtypes(include="float").columns:
        decimals = _infer_decimals(original[column])
        if decimals is not None:
            profile.decimals[column] = decimals

    # Categorical columns whose category set must survive generation
    not_modelled = set(profile.columns_not_modelled)
    for column in original.columns:
        if column in not_modelled:
            continue
        series = original[column].dropna()
        if series.empty:
            continue
        is_text = (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
            or pd.api.types.is_bool_dtype(series)
        )
        if is_text and series.nunique() <= MAX_CATEGORIES and series.nunique() < len(series):
            profile.categorical_columns.append(column)

    return profile


# ----------------------------------------------------------------------
# Before training
# ----------------------------------------------------------------------

def prepare_training_frame(
    original: pd.DataFrame,
    profile: TableProfile,
) -> pd.DataFrame:
    """Drop everything the model must not learn (IDs, keys, derived values)."""
    train = original.drop(columns=profile.columns_not_modelled, errors="ignore").copy()
    if train.shape[1] == 0:
        # Nothing left to model: fall back to the original frame so the
        # generator still has something to fit on.
        return original.copy()
    return train


# ----------------------------------------------------------------------
# After generation
# ----------------------------------------------------------------------

def _stratified_sample(values: list[Any], proportions: np.ndarray, n: int, rng) -> list[Any]:
    """Exact-proportion sample (largest remainder), shuffled."""
    raw = proportions * n
    counts = np.floor(raw).astype(int)
    remainder = n - counts.sum()
    if remainder > 0:
        order = np.argsort(-(raw - counts))
        for idx in order[:remainder]:
            counts[idx] += 1
    out: list[Any] = []
    for value, count in zip(values, counts):
        out.extend([value] * int(count))
    out = out[:n]
    rng.shuffle(out)
    return out


def _restore_categories(
    original: pd.DataFrame,
    synthetic: pd.DataFrame,
    column: str,
    rng,
    tvd_tolerance: float = 0.15,
) -> pd.DataFrame:
    real = original[column].dropna()
    real_freq = real.value_counts(normalize=True)
    syn_freq = synthetic[column].value_counts(normalize=True)

    missing = set(real_freq.index) - set(syn_freq.index)
    tvd = 0.5 * sum(
        abs(real_freq.get(c, 0.0) - syn_freq.get(c, 0.0))
        for c in set(real_freq.index) | set(syn_freq.index)
    )
    if not missing and tvd <= tvd_tolerance:
        return synthetic

    synthetic = synthetic.copy()
    synthetic[column] = _stratified_sample(
        real_freq.index.tolist(),
        real_freq.to_numpy(dtype=float),
        len(synthetic),
        rng,
    )
    logger.info(
        "Restored categories of '%s' (missing=%s, tvd=%.2f)",
        column,
        sorted(map(str, missing)),
        tvd,
    )
    return synthetic


def postprocess_generated(
    original: pd.DataFrame,
    synthetic: pd.DataFrame,
    profile: TableProfile,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Re-create all columns that were removed before training and enforce
    decimals, derived values and category coverage.
    """
    result = synthetic.copy().reset_index(drop=True)
    n = len(result)

    # 1. Unique IDs (same format as the real ones, never repeated)
    for column in profile.id_columns:
        result[column] = generate_ids_like(source=original[column], count=n)

    # 2. Placeholders for relationship columns (overwritten by the linker)
    for column in profile.relationship_columns:
        if column not in result.columns:
            result[column] = (
                original[column].sample(n=n, replace=True, random_state=int(rng.integers(0, 2**31 - 1))).to_numpy()
                if len(original)
                else None
            )

    # 3. Placeholders for key-function columns (rebuilt by apply_key_functions)
    for fn_cols in profile.key_function_columns.values():
        for column in fn_cols:
            if column not in result.columns:
                result[column] = original[column].sample(
                    n=n,
                    replace=True,
                    random_state=int(rng.integers(0, 2**31 - 1)),
                ).to_numpy()

    # 4. Integer dtype + decimals on the modelled operands
    for column in result.columns:
        if column not in original.columns or column in profile.derived_targets:
            continue
        if pd.api.types.is_integer_dtype(original[column]) and pd.api.types.is_numeric_dtype(result[column]):
            result[column] = result[column].round().astype(original[column].dtype)
        elif column in profile.decimals and pd.api.types.is_numeric_dtype(result[column]):
            result[column] = result[column].round(profile.decimals[column])

    # 5. Derived columns always recomputed from their operands
    if profile.derived_rules:
        result = apply_derived_features(result, profile.derived_rules)
        for target in profile.derived_targets:
            if target not in result.columns:
                continue
            if pd.api.types.is_integer_dtype(original[target]):
                result[target] = result[target].round().astype(original[target].dtype)
            else:
                decimals = profile.decimals.get(target, 2)
                result[target] = result[target].round(decimals)

    # 6. Category coverage
    for column in profile.categorical_columns:
        if column in result.columns:
            result = _restore_categories(original, result, column, rng)

    return result.reindex(columns=original.columns)


# ----------------------------------------------------------------------
# Key-derived columns (after the linker set the final parent keys)
# ----------------------------------------------------------------------

def _render_like(template: Any, key: Any) -> Any:
    """Build a value like `template` carrying the trailing number of `key`."""
    number = _last_number(key)
    template_text = str(template)
    matches = list(re.finditer(r"\d+", template_text))
    if number is None or not matches:
        return template
    last = matches[-1]
    digits = str(number).zfill(len(last.group()))
    return template_text[: last.start()] + digits + template_text[last.end():]


def apply_key_functions(
    original: pd.DataFrame,
    synthetic: pd.DataFrame,
    key_column: str,
    columns: list[str],
) -> pd.DataFrame:
    result = synthetic.copy()
    for column in columns:
        if column not in original.columns or column not in result.columns:
            continue
        mapping = dict(zip(original[key_column], original[column]))
        template = original[column].iloc[0]
        result[column] = result[key_column].map(
            lambda key: mapping[key] if key in mapping else _render_like(template, key)
        )
    return result


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

def validate_linked_tables(
    tables: dict[Any, pd.DataFrame],
    originals: dict[Any, pd.DataFrame],
    relationships: list[dict],
    profiles: dict[Any, TableProfile],
    tolerance: float = 0.01,
) -> dict[str, Any]:
    """Hard integrity checks on the generated tables."""
    checks: list[dict[str, Any]] = []

    def add(name: str, table: Any, passed: bool, detail: str = "") -> None:
        checks.append(
            {"check": name, "table": table, "passed": bool(passed), "detail": detail}
        )
        if not passed:
            logger.warning("Integrity check failed [%s / %s]: %s", name, table, detail)

    for dataset_id, df in tables.items():
        profile = profiles.get(dataset_id, TableProfile())

        # Primary keys
        for column in profile.id_columns:
            dup = int(df[column].duplicated().sum()) if column in df.columns else 0
            add("primary_key_unique", dataset_id, dup == 0, f"{column}: {dup} duplicates")

        # Derived columns
        for rule in profile.derived_rules:
            target, op = rule["target"], rule["operation"]
            left, right = rule["operands"]
            if not {target, left, right} <= set(df.columns):
                continue
            l = pd.to_numeric(df[left], errors="coerce")
            r = pd.to_numeric(df[right], errors="coerce")
            with np.errstate(divide="ignore", invalid="ignore"):
                expected = {
                    "multiply": l * r,
                    "add": l + r,
                    "subtract": l - r,
                    "divide": l / r.replace(0, np.nan),
                }[op]
            bad = int(((df[target] - expected).abs() > max(tolerance, 0.5 * 10 ** -profile.decimals.get(target, 2))).sum())
            add("derived_consistent", dataset_id, bad == 0, f"{target} = {left} {op} {right}: {bad} rows off")

        # Category coverage
        original = originals.get(dataset_id)
        if original is not None:
            for column in profile.categorical_columns:
                if column not in df.columns:
                    continue
                missing = set(original[column].dropna().unique()) - set(df[column].dropna().unique())
                add(
                    "categories_preserved",
                    dataset_id,
                    not missing,
                    f"{column}: missing {sorted(map(str, missing))}" if missing else column,
                )

    # Foreign keys
    for rel in relationships:
        parent = tables.get(rel["parent_dataset_id"])
        child = tables.get(rel["child_dataset_id"])
        if parent is None or child is None:
            continue
        pcol, ccol = rel["parent_column"], rel["child_column"]
        add("parent_key_unique", rel["parent_dataset_id"], parent[pcol].is_unique and parent[pcol].notna().all(), pcol)
        orphans = int((~child[ccol].isin(parent[pcol])).sum())
        add("foreign_key_valid", rel["child_dataset_id"], orphans == 0, f"{ccol}: {orphans} orphans")

    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
    }