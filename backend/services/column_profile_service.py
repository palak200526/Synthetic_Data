import re
import pandas as pd


def build_column_profile(
    df: pd.DataFrame,
    column: str,
) -> dict:

    series = df[column]

    profile = {
        "column_name": column,
        "dtype": str(series.dtype),
        "row_count": len(series),
        "unique_count": int(series.nunique(dropna=True)),
        "unique_ratio": float(
            series.nunique(dropna=True) / len(series)
        ) if len(series) > 0 else 0.0,
        "null_count": int(series.isna().sum()),
        "null_ratio": float(series.isna().mean()),
    }

    # ---------------------------------------
    # Sample values — reduced from 10 → 5
    # ---------------------------------------

    profile["sample_values"] = (
        series
        .dropna()
        .astype(str)
        .head(5)          # 👈 CHANGE: 10 → 5
        .tolist()
    )

    # ---------------------------------------
    # String information
    # ---------------------------------------

    if (
        pd.api.types.is_string_dtype(series)
        or pd.api.types.is_object_dtype(series)
        or pd.api.types.is_categorical_dtype(series)
    ):

        lengths = (
            series
            .dropna()
            .astype(str)
            .str.len()
        )

        if not lengths.empty:
            profile["string_length"] = {
                "min": int(lengths.min()),
                "max": int(lengths.max()),
                "average": float(lengths.mean()),
            }

        profile["patterns"] = detect_patterns(series)

    # ---------------------------------------
    # Numerical statistics — REMOVED
    # (LLM doesn't need these; adds tokens)
    # ---------------------------------------

    # NOTE: statistics block removed on purpose.
    # It was adding ~30 tokens per column with no
    # meaningful impact on LLM decisions.

    # ---------------------------------------
    # Categorical information
    # ---------------------------------------

    if (
        not pd.api.types.is_numeric_dtype(series)
        and series.nunique(dropna=True) <= 50
    ):
        profile["top_values"] = (
            series
            .value_counts(dropna=True)
            .head(5)      # 👈 CHANGE: 10 → 5
            .to_dict()
        )

    return profile


def detect_patterns(series: pd.Series) -> list[str]:
    """
    Detect well-known patterns (email, phone, uuid).
    Now samples only 30 values instead of 100 for speed.
    """

    patterns = []

    values = (
        series
        .dropna()
        .astype(str)
        .head(30)         # 👈 CHANGE: 100 → 30
    )

    if values.empty:
        return patterns

    pattern_checks = {
        "email": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        "phone": r"^\+?[\d\s().-]{7,}$",
        "uuid": (
            r"^[0-9a-fA-F]{8}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{12}$"
        ),
    }

    for pattern_name, regex in pattern_checks.items():
        matches = values.str.match(regex, na=False)
        if matches.mean() >= 0.8:
            patterns.append(pattern_name)

    return patterns


def build_dataset_column_profiles(
    df: pd.DataFrame
) -> list[dict]:

    profiles = []

    for column in df.columns:
        profiles.append(
            build_column_profile(df, column)
        )

    return profiles