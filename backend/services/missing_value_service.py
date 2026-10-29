"""Robust missing-value handling shared by preprocessing and generation.

The imputation is deliberately conservative and never treats an empty string as
a meaningful category. For date columns, use the median observed date rather
than a text mode. This guarantees a complete training frame; domain constraints
(such as delivery date >= shipment date) must still be checked after generation.
"""

import re
import pandas as pd
import numpy as np

_DATE_NAME = re.compile(r"(^|_)(date|datetime|timestamp|time)(_|$)", re.I)
_NUMERIC_NAME = re.compile(r"(amount|price|cost|quantity|qty|count|number|num|score|rate|percent|percentage|age|total|balance|weight|height|duration|days|hours|units|revenue|profit|salary|latitude|longitude)$", re.I)


def _normalise_missing(series: pd.Series) -> pd.Series:
    series = series.copy()
    if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype):
        text = series.astype("string").str.strip()
        series = series.mask(text.eq("") | text.str.lower().isin(["nan", "none", "null", "nat"]))
    return series.mask(series.isin([np.inf, -np.inf]))


def _is_date_column(column, series: pd.Series) -> bool:
    if _DATE_NAME.search(str(column)):
        return True
    if not (pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype)):
        return False
    sample = series.dropna().astype(str).head(100)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return float(parsed.notna().mean()) >= 0.8


def _fill_value(column, series: pd.Series, reference: pd.Series | None = None):
    source = reference if reference is not None else series
    source = _normalise_missing(source).dropna()

    if _is_date_column(column, series) or _is_date_column(column, source):
        parsed = pd.to_datetime(source, errors="coerce", format="mixed").dropna()
        if not parsed.empty:
            median_ns = int(parsed.astype("int64").median())
            return pd.Timestamp(median_ns)
        # No date information exists; use an explicit, stable sentinel instead
        # of inventing a date based on the machine's current clock.
        return pd.Timestamp("2000-01-01")

    if pd.api.types.is_bool_dtype(series.dtype):
        if not source.empty:
            return bool(source.mode().iloc[0])
        return False

    if pd.api.types.is_numeric_dtype(series.dtype) or (source.empty and _NUMERIC_NAME.search(str(column))):
        numeric = pd.to_numeric(source, errors="coerce").dropna()
        if not numeric.empty:
            return float(numeric.median())
        return 0

    if not source.empty:
        modes = source.mode(dropna=True)
        if not modes.empty:
            return modes.iloc[0]
    return "Unknown"


def handle_missing_values(dataframe: pd.DataFrame, reference_dataframe: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a copy with NaN, infinities and blank strings imputed.

    ``reference_dataframe`` lets generated data use the same learned fill values
    as its preprocessed training dataset. It is optional for backward compatibility.
    """
    if dataframe is None:
        raise ValueError("Dataframe cannot be None.")

    result = dataframe.copy()
    reference_dataframe = reference_dataframe if reference_dataframe is not None else dataframe

    for column in result.columns:
        result[column] = _normalise_missing(result[column])

        # A completely blank column has no information from which to infer a
        # numeric, date, or categorical value. Keep the column and row count,
        # and use the explicit requested sentinel in both preprocessing and
        # generation input. Do this before dtype-based imputation so an
        # all-null numeric/date column does not become 0 or an invented date.
        if result[column].isna().all():
            result[column] = "unknown"
            continue

        if not result[column].isna().any():
            continue
        reference = reference_dataframe[column] if column in reference_dataframe.columns else None
        fill_value = _fill_value(column, result[column], reference)
        result[column] = result[column].fillna(fill_value)

        # Keep date columns consistently represented as ISO strings when the
        # incoming column was text, so downstream CSV/API schema stays stable.
        if _is_date_column(column, result[column]) and (
            pd.api.types.is_object_dtype(dataframe[column].dtype)
            or pd.api.types.is_string_dtype(dataframe[column].dtype)
        ):
            parsed = pd.to_datetime(result[column], errors="coerce", format="mixed")
            result[column] = parsed.dt.strftime("%Y-%m-%d").fillna("2000-01-01")

    # Defensive final pass: unexpected extension dtypes or mixed values should
    # never allow a missing value to silently reach a generator.
    for column in result.columns:
        if result[column].isna().any():
            fill_value = _fill_value(column, result[column], reference_dataframe.get(column))
            result[column] = result[column].fillna(fill_value)

    return result
