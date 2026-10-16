from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.services.statistical_evaluation_service import (
    determine_column_eligibility,
)

logger = logging.getLogger(__name__)

MAX_CATEGORY_CARDINALITY = 30


def _cramers_v(x: pd.Series, y: pd.Series) -> float:
    """Bias-corrected Cramer's V between two categorical series (0..1)."""
    tbl = pd.crosstab(x, y)
    if tbl.shape[0] < 2 or tbl.shape[1] < 2:
        return 0.0
    obs = tbl.to_numpy(dtype=float)
    n = obs.sum()
    if n <= 1:
        return 0.0
    expected = np.outer(obs.sum(axis=1), obs.sum(axis=0)) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = float(np.nansum((obs - expected) ** 2 / expected))
    r, k = obs.shape
    phi2 = chi2 / n
    phi2c = max(0.0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
    rc = r - ((r - 1) ** 2) / (n - 1)
    kc = k - ((k - 1) ** 2) / (n - 1)
    denom = min(kc - 1, rc - 1)
    return float(np.sqrt(phi2c / denom)) if denom > 0 else 0.0


def _evaluate_categorical_association(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    columns: list[str],
) -> dict[str, Any]:
    """
    Used when a dataset has fewer than 2 numerical columns: measures whether
    category-to-category dependencies (Cramer's V) are preserved.
    """
    def _mat(df: pd.DataFrame) -> pd.DataFrame:
        m = pd.DataFrame(np.eye(len(columns)), index=columns, columns=columns)
        for i, a in enumerate(columns):
            for b in columns[i + 1:]:
                v = _cramers_v(df[a].astype(str), df[b].astype(str))
                m.loc[a, b] = v
                m.loc[b, a] = v
        return m

    src = _mat(real_dataframe)
    syn = _mat(synthetic_dataframe)
    diff = (src - syn).abs()
    pair_diffs = [
        float(diff.loc[a, b])
        for i, a in enumerate(columns)
        for b in columns[i + 1:]
    ]
    mean_diff = float(np.mean(pair_diffs)) if pair_diffs else 0.0
    score = round(max(0.0, 1.0 - mean_diff) * 100.0, 2)
    return {
        "metric": "correlation_covariance",
        "status": "evaluated",
        "association_type": "cramers_v",
        "note": (
            "Fewer than 2 numerical columns, so category-to-category "
            "association (Cramer's V) was compared instead of Pearson correlation."
        ),
        "overall_score": score,
        "relationship_similarity_score": score,
        "correlation_similarity": score,
        "covariance_similarity": None,
        "mean_correlation_difference": round(mean_diff, 4),
        "mean_normalized_covariance_difference": None,
        "numerical_columns": columns,
        "source_correlation": src.round(4).to_dict(),
        "synthetic_correlation": syn.round(4).to_dict(),
        "correlation_difference": diff.round(4).to_dict(),
        "source_covariance": {},
        "synthetic_covariance": {},
        "covariance_difference": {},
    }
EPSILON = 1e-9


def evaluate_correlation_covariance(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    column_configurations: list[dict] | None = None,
    dataset_profile: dict | None = None,
) -> dict[str, Any]:
    """
    US-024: Correlation and Covariance Utility Evaluation.

    Measures whether numerical feature relationships and covariances
    are preserved between real and synthetic data.

    Only applicable numerical columns are included. Identifiers,
    free-form text, categoricals, and datetimes are excluded.
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

    # Index configurations & profile
    config_map = {}
    if column_configurations:
        for cfg in column_configurations:
            if isinstance(cfg, dict) and "column_name" in cfg:
                config_map[cfg["column_name"]] = cfg

    profile_map = {}
    if dataset_profile and isinstance(dataset_profile, dict):
        col_info = dataset_profile.get("column_information") or dataset_profile.get("columns") or []
        if isinstance(col_info, list):
            for col_prof in col_info:
                if isinstance(col_prof, dict) and "column_name" in col_prof:
                    profile_map[col_prof["column_name"]] = col_prof
        elif isinstance(col_info, dict):
            profile_map = col_info

    # Filter applicable numerical columns
    applicable_numerical_columns = []
    for col in common_columns:
        status, _, col_type = determine_column_eligibility(
            column_name=col,
            real_series=real_dataframe[col],
            configuration=config_map.get(col),
            profile_column=profile_map.get(col),
        )
        if status == "evaluated" and col_type == "numerical":
            applicable_numerical_columns.append(col)

    # Check minimum requirement: at least 2 numerical columns needed
    if len(applicable_numerical_columns) < 2:
        cat_cols = []
        for col in common_columns:
            c_status, _, c_type = determine_column_eligibility(
                column_name=col,
                real_series=real_dataframe[col],
                configuration=config_map.get(col),
                profile_column=profile_map.get(col),
            )
            if (
                c_status == "evaluated"
                and c_type == "categorical"
                and 1 < real_dataframe[col].nunique(dropna=True) <= MAX_CATEGORY_CARDINALITY
            ):
                cat_cols.append(col)
        if len(cat_cols) >= 2:
            return _evaluate_categorical_association(
                real_dataframe, synthetic_dataframe, cat_cols
            )
        return {
            "metric": "correlation_covariance",
            "status": "not_applicable",
            "reason": (
                "Insufficient numerical columns for correlation evaluation "
                f"(minimum 2 required, found {len(applicable_numerical_columns)})"
            ),
            "overall_score": None,
            "relationship_similarity_score": None,
            "correlation_similarity": None,
            "covariance_similarity": None,
            "numerical_columns": applicable_numerical_columns,
            "source_correlation": {},
            "synthetic_correlation": {},
            "correlation_difference": {},
            "source_covariance": {},
            "synthetic_covariance": {},
            "covariance_difference": {},
        }

    # Extract and clean numerical data
    real_num = pd.DataFrame()
    synth_num = pd.DataFrame()

    for col in applicable_numerical_columns:
        real_num[col] = pd.to_numeric(real_dataframe[col], errors="coerce")
        synth_num[col] = pd.to_numeric(synthetic_dataframe[col], errors="coerce")

    # Check sufficient data rows
    if len(real_num.dropna(how="all")) < 2 or len(synth_num.dropna(how="all")) < 2:
        return {
            "metric": "correlation_covariance",
            "status": "not_applicable",
            "reason": "Insufficient data rows to calculate correlation/covariance matrices",
            "overall_score": None,
            "relationship_similarity_score": None,
            "correlation_similarity": None,
            "covariance_similarity": None,
            "numerical_columns": applicable_numerical_columns,
            "source_correlation": {},
            "synthetic_correlation": {},
            "correlation_difference": {},
            "source_covariance": {},
            "synthetic_covariance": {},
            "covariance_difference": {},
        }

    # Handle missing values: impute with median or 0.0
    for col in applicable_numerical_columns:
        real_med = real_num[col].median()
        synth_med = synth_num[col].median()
        real_num[col] = real_num[col].fillna(real_med if pd.notna(real_med) else 0.0)
        synth_num[col] = synth_num[col].fillna(synth_med if pd.notna(synth_med) else 0.0)

    # Compute correlation and covariance matrices
    # Constant columns (std == 0) produce NaN in corr; fill with 0.0, diagonal with 1.0
    source_corr_df = real_num.corr().fillna(0.0)
    synthetic_corr_df = synth_num.corr().fillna(0.0)
    for col in applicable_numerical_columns:
        source_corr_df.loc[col, col] = 1.0
        synthetic_corr_df.loc[col, col] = 1.0

    source_cov_df = real_num.cov().fillna(0.0)
    synthetic_cov_df = synth_num.cov().fillna(0.0)

    corr_diff_df = (source_corr_df - synthetic_corr_df).abs()
    cov_diff_df = (source_cov_df - synthetic_cov_df).abs()

    # Calculate off-diagonal pairwise relationship similarity
    n = len(applicable_numerical_columns)
    corr_diffs = []
    norm_cov_diffs = []

    for i in range(n):
        col_i = applicable_numerical_columns[i]
        real_std_i = float(real_num[col_i].std())

        for j in range(i + 1, n):
            col_j = applicable_numerical_columns[j]
            real_std_j = float(real_num[col_j].std())

            # Correlation difference (range [0, 2])
            c_diff = float(corr_diff_df.loc[col_i, col_j])
            corr_diffs.append(c_diff)

            # Covariance difference normalized by real standard deviation scale
            cov_scale = max(real_std_i * real_std_j, EPSILON)
            v_diff = float(cov_diff_df.loc[col_i, col_j])
            norm_cov_diff = min(v_diff / cov_scale, 1.0)
            norm_cov_diffs.append(norm_cov_diff)

    if corr_diffs:
        mean_corr_diff = float(np.mean(corr_diffs))
        correlation_similarity = max(0.0, 1.0 - (mean_corr_diff / 2.0)) * 100.0
    else:
        correlation_similarity = 100.0
        mean_corr_diff = 0.0

    if norm_cov_diffs:
        mean_norm_cov_diff = float(np.mean(norm_cov_diffs))
        covariance_similarity = max(0.0, 1.0 - mean_norm_cov_diff) * 100.0
    else:
        covariance_similarity = 100.0
        mean_norm_cov_diff = 0.0

    overall_score = round(
        float(np.mean([correlation_similarity, covariance_similarity])), 2
    )

    return {
        "metric": "correlation_covariance",
        "status": "evaluated",
        "overall_score": overall_score,
        "relationship_similarity_score": overall_score,
        "correlation_similarity": round(correlation_similarity, 2),
        "covariance_similarity": round(covariance_similarity, 2),
        "mean_correlation_difference": round(mean_corr_diff, 4),
        "mean_normalized_covariance_difference": round(mean_norm_cov_diff, 4),
        "numerical_columns": applicable_numerical_columns,
        "source_correlation": source_corr_df.round(4).to_dict(),
        "synthetic_correlation": synthetic_corr_df.round(4).to_dict(),
        "correlation_difference": corr_diff_df.round(4).to_dict(),
        "source_covariance": source_cov_df.round(4).to_dict(),
        "synthetic_covariance": synthetic_cov_df.round(4).to_dict(),
        "covariance_difference": cov_diff_df.round(4).to_dict(),
    }