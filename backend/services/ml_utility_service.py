from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder

from backend.services.statistical_evaluation_service import (
    determine_column_eligibility,
)

logger = logging.getLogger(__name__)

COMMON_TARGET_NAMES = [
    "target",
    "label",
    "class",
    "sentiment",
    "status",
    "churn",
    "outcome",
    "rating",
    "fraud",
    "is_churn",
    "converted",
    "category",
    "confidence score",
    "confidence_score",
    "delay_rate",
    "total_cost",
    "cost",
    "price",
]


def identify_prediction_task(
    eligible_columns: list[str],
    real_dataframe: pd.DataFrame,
    preferred_target: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Identify target column and task type ('classification' or 'regression').

    Returns (target_column, task_type) or (None, None).
    """
    if len(eligible_columns) < 2:
        return None, None

    if preferred_target and preferred_target in eligible_columns:
        series = real_dataframe[preferred_target].dropna()
        if pd.api.types.is_numeric_dtype(series) and series.nunique() > 10:
            return preferred_target, "regression"
        elif series.nunique() >= 2:
            return preferred_target, "classification"

    # Search for known target names first
    for name in COMMON_TARGET_NAMES:
        for col in eligible_columns:
            if col.strip().lower() == name:
                series = real_dataframe[col].dropna()
                if pd.api.types.is_numeric_dtype(series) and series.nunique() > 10:
                    return col, "regression"
                elif 2 <= series.nunique() <= 20:
                    return col, "classification"

    # Search for low-cardinality categorical target
    for col in eligible_columns:
        series = real_dataframe[col].dropna()
        if not pd.api.types.is_numeric_dtype(series) and 2 <= series.nunique() <= 10:
            return col, "classification"

    # Search for numerical regression target with continuous variance
    for col in eligible_columns:
        series = pd.to_numeric(real_dataframe[col], errors="coerce").dropna()
        if pd.api.types.is_numeric_dtype(real_dataframe[col]) and series.nunique() > 10 and series.std() > 0:
            return col, "regression"

    return None, None


def evaluate_ml_utility(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    column_configurations: list[dict] | None = None,
    dataset_profile: dict | None = None,
    target_column: str | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    US-025: Synthetic-Train / Real-Test ML Utility Evaluation.

    Workflow:
    1. Identify prediction task (classification or regression).
    2. Split real dataset into Real Train and Real Test.
    3. Train ML model on Synthetic Data.
    4. Evaluate on Real Test set.
    5. Train baseline ML model on Real Train set and evaluate on Real Test set.
    6. Compare synthetic predictive performance against real baseline.
    """
    if real_dataframe.empty:
        raise ValueError("Real dataset is empty.")

    if synthetic_dataframe.empty:
        raise ValueError("Synthetic dataset is empty.")

    common_columns = [
        col for col in real_dataframe.columns if col in synthetic_dataframe.columns
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

    # Determine eligible feature/target columns (exclude free-form text, identifiers, datetime)
    eligible_columns = []
    for col in common_columns:
        status, _, _ = determine_column_eligibility(
            column_name=col,
            real_series=real_dataframe[col],
            configuration=config_map.get(col),
            profile_column=profile_map.get(col),
        )
        if status == "evaluated":
            eligible_columns.append(col)

    target_col, task_type = identify_prediction_task(
        eligible_columns=eligible_columns,
        real_dataframe=real_dataframe,
        preferred_target=target_column,
    )

    if not target_col or not task_type:
        return {
            "metric": "ml_utility",
            "status": "not_applicable",
            "reason": "No suitable prediction task identified",
            "overall_score": None,
            "utility_score": None,
            "task_type": None,
            "target_column": None,
            "synthetic_metrics": {},
            "baseline_metrics": {},
        }

    feature_cols = [c for c in eligible_columns if c != target_col]
    if not feature_cols:
        return {
            "metric": "ml_utility",
            "status": "not_applicable",
            "reason": "No suitable feature columns available for prediction task",
            "overall_score": None,
            "utility_score": None,
            "task_type": task_type,
            "target_column": target_col,
            "synthetic_metrics": {},
            "baseline_metrics": {},
        }

    try:
        # Prepare datasets
        real_clean = real_dataframe[eligible_columns].dropna(subset=[target_col]).copy()
        synth_clean = synthetic_dataframe[eligible_columns].dropna(subset=[target_col]).copy()

        if len(real_clean) < 10 or len(synth_clean) < 5:
            return {
                "metric": "ml_utility",
                "status": "not_applicable",
                "reason": "Insufficient records for machine learning evaluation",
                "overall_score": None,
                "utility_score": None,
                "task_type": task_type,
                "target_column": target_col,
                "synthetic_metrics": {},
                "baseline_metrics": {},
            }

        # Train/Test Split Real data
        real_train, real_test = train_test_split(
            real_clean,
            test_size=test_size,
            random_state=random_state,
        )

        # Preprocess features
        num_features = [
            c for c in feature_cols if pd.api.types.is_numeric_dtype(real_clean[c])
        ]
        cat_features = [c for c in feature_cols if c not in num_features]

        # Fit encoders/imputers on real training features
        feature_medians = {}
        for c in num_features:
            med = pd.to_numeric(real_train[c], errors="coerce").median()
            feature_medians[c] = float(med) if pd.notna(med) else 0.0

        cat_encoder = None
        if cat_features:
            cat_encoder = OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1,
            )
            cat_train_str = real_train[cat_features].fillna("__missing__").astype(str)
            cat_encoder.fit(cat_train_str)

        def transform_features(df_in: pd.DataFrame) -> np.ndarray:
            parts = []
            if num_features:
                num_mat = np.zeros((len(df_in), len(num_features)))
                for idx, c in enumerate(num_features):
                    vals = pd.to_numeric(df_in[c], errors="coerce").fillna(feature_medians[c]).to_numpy()
                    num_mat[:, idx] = vals
                parts.append(num_mat)
            if cat_features and cat_encoder:
                cat_str = df_in[cat_features].fillna("__missing__").astype(str)
                cat_mat = cat_encoder.transform(cat_str)
                parts.append(cat_mat)
            return np.hstack(parts)

        X_real_train = transform_features(real_train)
        X_real_test = transform_features(real_test)
        X_synth_train = transform_features(synth_clean)

        if task_type == "classification":
            # Encode target labels
            label_encoder = LabelEncoder()
            y_real_train = label_encoder.fit_transform(real_train[target_col].astype(str))
            y_real_test = label_encoder.transform(real_test[target_col].astype(str))

            # Synthetic target alignment
            synth_targets = synth_clean[target_col].astype(str)
            valid_synth_mask = synth_targets.isin(label_encoder.classes_)
            if valid_synth_mask.sum() < 2:
                return {
                    "metric": "ml_utility",
                    "status": "not_applicable",
                    "reason": "Synthetic target categories do not overlap with real classes",
                    "overall_score": None,
                    "utility_score": None,
                    "task_type": task_type,
                    "target_column": target_col,
                    "synthetic_metrics": {},
                    "baseline_metrics": {},
                }

            X_synth_train = X_synth_train[valid_synth_mask]
            y_synth_train = label_encoder.transform(synth_targets[valid_synth_mask])

            # Train models
            baseline_model = RandomForestClassifier(
                n_estimators=50,
                max_depth=6,
                random_state=random_state,
            )
            baseline_model.fit(X_real_train, y_real_train)

            synth_model = RandomForestClassifier(
                n_estimators=50,
                max_depth=6,
                random_state=random_state,
            )
            synth_model.fit(X_synth_train, y_synth_train)

            # Predict on Real Test Set
            y_pred_base = baseline_model.predict(X_real_test)
            y_pred_synth = synth_model.predict(X_real_test)

            baseline_metrics = {
                "accuracy": round(float(accuracy_score(y_real_test, y_pred_base)), 4),
                "precision": round(
                    float(precision_score(y_real_test, y_pred_base, average="weighted", zero_division=0)), 4
                ),
                "recall": round(
                    float(recall_score(y_real_test, y_pred_base, average="weighted", zero_division=0)), 4
                ),
                "f1": round(
                    float(f1_score(y_real_test, y_pred_base, average="weighted", zero_division=0)), 4
                ),
            }

            synthetic_metrics = {
                "accuracy": round(float(accuracy_score(y_real_test, y_pred_synth)), 4),
                "precision": round(
                    float(precision_score(y_real_test, y_pred_synth, average="weighted", zero_division=0)), 4
                ),
                "recall": round(
                    float(recall_score(y_real_test, y_pred_synth, average="weighted", zero_division=0)), 4
                ),
                "f1": round(
                    float(f1_score(y_real_test, y_pred_synth, average="weighted", zero_division=0)), 4
                ),
            }

            base_f1 = baseline_metrics["f1"]
            syn_f1 = synthetic_metrics["f1"]

            if base_f1 > 0:
                rel_f1 = syn_f1 / base_f1
                score = round(min(1.0, max(0.0, rel_f1)) * 100.0, 2)
            else:
                score = 100.0 if syn_f1 == 0.0 else 50.0

            return {
                "metric": "ml_utility",
                "status": "evaluated",
                "task_type": "classification",
                "target_column": target_col,
                "feature_columns": feature_cols,
                "model_type": "RandomForestClassifier",
                "synthetic_metrics": synthetic_metrics,
                "baseline_metrics": baseline_metrics,
                "utility_score": score,
                "overall_score": score,
            }

        else:  # regression
            y_real_train = pd.to_numeric(real_train[target_col], errors="coerce").fillna(0.0).to_numpy()
            y_real_test = pd.to_numeric(real_test[target_col], errors="coerce").fillna(0.0).to_numpy()
            y_synth_train = pd.to_numeric(synth_clean[target_col], errors="coerce").fillna(0.0).to_numpy()

            baseline_model = RandomForestRegressor(
                n_estimators=50,
                max_depth=6,
                random_state=random_state,
            )
            baseline_model.fit(X_real_train, y_real_train)

            synth_model = RandomForestRegressor(
                n_estimators=50,
                max_depth=6,
                random_state=random_state,
            )
            synth_model.fit(X_synth_train, y_synth_train)

            y_pred_base = baseline_model.predict(X_real_test)
            y_pred_synth = synth_model.predict(X_real_test)

            base_rmse = float(np.sqrt(mean_squared_error(y_real_test, y_pred_base)))
            synth_rmse = float(np.sqrt(mean_squared_error(y_real_test, y_pred_synth)))

            baseline_metrics = {
                "mae": round(float(mean_absolute_error(y_real_test, y_pred_base)), 4),
                "rmse": round(base_rmse, 4),
                "r2": round(float(r2_score(y_real_test, y_pred_base)), 4),
            }

            synthetic_metrics = {
                "mae": round(float(mean_absolute_error(y_real_test, y_pred_synth)), 4),
                "rmse": round(synth_rmse, 4),
                "r2": round(float(r2_score(y_real_test, y_pred_synth)), 4),
            }

            rmse_diff = abs(synth_rmse - base_rmse)
            denom = max(base_rmse, 1e-4)
            score = round(max(0.0, 1.0 - (rmse_diff / denom)) * 100.0, 2)

            return {
                "metric": "ml_utility",
                "status": "evaluated",
                "task_type": "regression",
                "target_column": target_col,
                "feature_columns": feature_cols,
                "model_type": "RandomForestRegressor",
                "synthetic_metrics": synthetic_metrics,
                "baseline_metrics": baseline_metrics,
                "utility_score": score,
                "overall_score": score,
            }

    except Exception as exc:
        logger.exception("ML utility evaluation failed: %s", exc)
        return {
            "metric": "ml_utility",
            "status": "error",
            "reason": str(exc),
            "overall_score": None,
            "utility_score": None,
            "task_type": task_type,
            "target_column": target_col,
            "synthetic_metrics": {},
            "baseline_metrics": {},
        }
