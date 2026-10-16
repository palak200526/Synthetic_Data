from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
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

# The real-data model must beat a trivial model by at least this much,
# otherwise the target cannot be predicted from the other columns and the
# "synthetic vs real" ML comparison would be meaningless.
MIN_CLASSIFICATION_LIFT = 0.05   # accuracy above majority-class model
MIN_REGRESSION_R2 = 0.05         # R2 of the real-data baseline


def _not_predictable(task_type, target_col, feature_cols, reason, baseline=None, detail=None):
    return {
        "metric": "ml_utility",
        "status": "not_applicable",
        "reason": reason,
        "reason_detail": detail,
        "overall_score": None,
        "utility_score": None,
        "task_type": task_type,
        "target_column": target_col,
        "feature_columns": feature_cols,
        "synthetic_metrics": {},
        "baseline_metrics": baseline or {},
    }

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


def _evaluate_single_target(
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

            # Gate: is the target learnable from the real data at all?
            dummy = DummyClassifier(strategy="most_frequent")
            dummy.fit(X_real_train, y_real_train)
            dummy_pred = dummy.predict(X_real_test)
            dummy_f1 = float(
                f1_score(y_real_test, dummy_pred, average="weighted", zero_division=0)
            )
            dummy_acc = float(accuracy_score(y_real_test, dummy_pred))
            base_acc = float(baseline_metrics.get("accuracy", 0.0))
            baseline_metrics["majority_class_f1"] = round(dummy_f1, 4)
            baseline_metrics["majority_class_accuracy"] = round(dummy_acc, 4)
            # Compare ACCURACY with the majority-class accuracy: on balanced
            # targets (e.g. gender 50/50) a coin flip already scores ~0.5.
            if base_acc < dummy_acc + MIN_CLASSIFICATION_LIFT:
                return _not_predictable(
                    task_type,
                    target_col,
                    feature_cols,
                    (
                        f"'{target_col}' cannot be predicted from the other columns, so "
                        "ML Utility cannot be measured for it. Even a model trained on the "
                        f"REAL data is right only {base_acc:.0%} of the time, which is no "
                        "better than always guessing the most common value "
                        f"({dummy_acc:.0%}). If real data cannot teach a model this column, "
                        "synthetic data cannot be judged on it either. This is a property of "
                        "the column, not a problem with your synthetic data. Choose a target "
                        "that depends on the other columns (for example an outcome or a "
                        "score), or select Auto."
                    ),
                    baseline_metrics,
                    detail=(
                        f"real-data accuracy {base_acc:.2f} vs majority-class accuracy "
                        f"{dummy_acc:.2f}; required lift {MIN_CLASSIFICATION_LIFT:.2f}"
                    ),
                )

            # Symmetric closeness: 100 only when synthetic == real baseline.
            # (Old formula was capped, so it returned 100 for almost any data.)
            hi = max(base_f1, syn_f1)
            score = round((min(base_f1, syn_f1) / hi) * 100.0, 2) if hi > 0 else 100.0

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

            base_r2 = baseline_metrics["r2"]
            if base_r2 < MIN_REGRESSION_R2:
                return _not_predictable(
                    task_type,
                    target_col,
                    feature_cols,
                    (
                        f"'{target_col}' cannot be predicted from the other columns, so "
                        "ML Utility cannot be measured for it. A model trained on the REAL "
                        f"data explains only {max(base_r2, 0.0):.0%} of the variation in this "
                        "column. If real data cannot teach a model this column, synthetic "
                        "data cannot be judged on it either. This is a property of the "
                        "column, not a problem with your synthetic data. Choose a target "
                        "that depends on the other columns (for example an outcome or a "
                        "score), or select Auto."
                    ),
                    baseline_metrics,
                    detail=(
                        f"real-data R2 {base_r2:.2f}; required minimum {MIN_REGRESSION_R2:.2f}"
                    ),
                )

            # Smooth, symmetric closeness (same idea as classification):
            # 100 = identical error, decays gradually instead of hitting a
            # hard 0 once the synthetic model is 2x worse than the baseline.
            lo = min(base_rmse, synth_rmse)
            hi = max(base_rmse, synth_rmse)
            score = round((lo / hi) * 100.0, 2) if hi > 1e-12 else 100.0

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


def _candidate_targets(real_dataframe: pd.DataFrame, eligible: list[str], limit: int = 6) -> list[str]:
    """Rank plausible prediction targets (most sensible first)."""
    ranked: list[str] = []

    def add(col: str) -> None:
        if col not in ranked:
            ranked.append(col)

    for name in COMMON_TARGET_NAMES:
        for col in eligible:
            if col.strip().lower() == name:
                add(col)
    if eligible:
        add(eligible[-1])  # datasets usually end with the outcome column
    for col in eligible:
        ser = real_dataframe[col].dropna()
        if not pd.api.types.is_numeric_dtype(ser) and 2 <= ser.nunique() <= 10:
            add(col)
    for col in eligible:
        ser = pd.to_numeric(real_dataframe[col], errors="coerce").dropna()
        if pd.api.types.is_numeric_dtype(real_dataframe[col]) and ser.nunique() > 10 and ser.std() > 0:
            add(col)
    for col in eligible:
        ser = real_dataframe[col].dropna()
        if pd.api.types.is_numeric_dtype(ser) and 2 <= ser.nunique() <= 10:
            add(col)
    return ranked[:limit]


def evaluate_ml_utility(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    column_configurations: list[dict] | None = None,
    dataset_profile: dict | None = None,
    target_column: str | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    target_source: str | None = None,
) -> dict[str, Any]:
    """
    ML utility with automatic target selection.

    If the caller does not name a target, several candidate columns are tried
    and the first one that is genuinely predictable from the other columns is
    used (a random target such as gender makes the comparison meaningless).
    """
    kwargs = dict(
        column_configurations=column_configurations,
        dataset_profile=dataset_profile,
        test_size=test_size,
        random_state=random_state,
    )
    if target_column:
        res = _evaluate_single_target(
            real_dataframe, synthetic_dataframe, target_column=target_column, **kwargs
        )
        res["target_source"] = target_source or "user"
        return res

    common = [c for c in real_dataframe.columns if c in synthetic_dataframe.columns]
    config_map = {
        c["column_name"]: c
        for c in (column_configurations or [])
        if isinstance(c, dict) and "column_name" in c
    }
    profile_map: dict = {}
    if isinstance(dataset_profile, dict):
        info = dataset_profile.get("column_information") or dataset_profile.get("columns") or []
        if isinstance(info, list):
            profile_map = {
                p["column_name"]: p for p in info
                if isinstance(p, dict) and "column_name" in p
            }
        elif isinstance(info, dict):
            profile_map = info
    eligible = []
    for col in common:
        st, _, _ = determine_column_eligibility(
            column_name=col, real_series=real_dataframe[col],
            configuration=config_map.get(col), profile_column=profile_map.get(col),
        )
        if st == "evaluated":
            eligible.append(col)

    candidates = _candidate_targets(real_dataframe, eligible)
    if not candidates:
        return _evaluate_single_target(real_dataframe, synthetic_dataframe, **kwargs)

    first_failure = None
    tried: list[str] = []
    for cand in candidates:
        res = _evaluate_single_target(
            real_dataframe, synthetic_dataframe, target_column=cand, **kwargs
        )
        tried.append(cand)
        if res.get("status") == "evaluated":
            res["targets_tried"] = tried
            return res
        if first_failure is None:
            first_failure = res

    first_failure = first_failure or {}
    first_failure["targets_tried"] = tried
    first_failure["reason"] = (
        "None of the candidate target columns ("
        + ", ".join(tried)
        + ") can be predicted from the other columns in this dataset, so an "
        "ML-utility comparison would not be meaningful."
    )
    return first_failure


# ---------------------------------------------------------------------------
# Target candidates (what the user can pick in the dropdown)
# ---------------------------------------------------------------------------

def _eligible_ml_columns(real_dataframe, synthetic_dataframe, column_configurations, dataset_profile):
    common = [c for c in real_dataframe.columns if c in synthetic_dataframe.columns]
    config_map = {
        c["column_name"]: c
        for c in (column_configurations or [])
        if isinstance(c, dict) and "column_name" in c
    }
    profile_map: dict = {}
    if isinstance(dataset_profile, dict):
        info = dataset_profile.get("column_information") or dataset_profile.get("columns") or []
        if isinstance(info, list):
            profile_map = {
                p["column_name"]: p for p in info
                if isinstance(p, dict) and "column_name" in p
            }
        elif isinstance(info, dict):
            profile_map = info
    eligible = []
    for col in common:
        st, _, _ = determine_column_eligibility(
            column_name=col, real_series=real_dataframe[col],
            configuration=config_map.get(col), profile_column=profile_map.get(col),
        )
        if st == "evaluated":
            eligible.append(col)
    return eligible


def list_ml_target_candidates(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    column_configurations: list[dict] | None = None,
    dataset_profile: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Columns that can be offered as an ML target in the dropdown.

    This is a cheap listing only: NO model is trained here. Whether the chosen
    column is actually predictable is checked later, and only for the column
    that is really used (see _evaluate_single_target).

    - numeric with > 10 distinct values  -> regression
    - 2..20 distinct values              -> classification
    """
    eligible = _eligible_ml_columns(
        real_dataframe, synthetic_dataframe, column_configurations, dataset_profile
    )
    if len(eligible) < 2:
        return []

    candidates: list[dict[str, Any]] = []
    for col in eligible:
        n_unique = int(real_dataframe[col].dropna().nunique())
        is_num = pd.api.types.is_numeric_dtype(real_dataframe[col])
        if is_num and n_unique > 10:
            task = "regression"
        elif 2 <= n_unique <= 20:
            task = "classification"
        else:
            continue

        candidates.append({
            "column": col,
            "task_type": task,
            "unique_values": n_unique,
            "dtype": "numeric" if is_num else "categorical",
        })

    return candidates