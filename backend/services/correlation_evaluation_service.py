from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.services.statistical_evaluation_service import (
    determine_column_eligibility,
)

logger = logging.getLogger(__name__)
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
