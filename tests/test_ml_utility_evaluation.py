import numpy as np
import pandas as pd
import pytest

from backend.services.ml_utility_service import (
    evaluate_ml_utility,
    identify_prediction_task,
)


def test_us025_classification_task():
    np.random.seed(42)
    n = 120

    # Feature 1 & 2
    f1 = np.random.normal(10, 2, n)
    f2 = np.random.normal(50, 5, n)
    # Binary class target based on features
    label = np.where(f1 + 0.1 * f2 > 15, "high", "low")

    real_df = pd.DataFrame({"feature_1": f1, "feature_2": f2, "target": label})

    # Synthetic with matching distribution
    synth_f1 = np.random.normal(10, 2, n)
    synth_f2 = np.random.normal(50, 5, n)
    synth_label = np.where(synth_f1 + 0.1 * synth_f2 > 15, "high", "low")

    synth_df = pd.DataFrame({
        "feature_1": synth_f1,
        "feature_2": synth_f2,
        "target": synth_label,
    })

    result = evaluate_ml_utility(real_df, synth_df, target_column="target")

    assert result["metric"] == "ml_utility"
    assert result["status"] == "evaluated"
    assert result["task_type"] == "classification"
    assert result["target_column"] == "target"
    assert result["overall_score"] is not None
    assert result["overall_score"] > 60.0

    synth_metrics = result["synthetic_metrics"]
    baseline_metrics = result["baseline_metrics"]

    assert "accuracy" in synth_metrics
    assert "precision" in synth_metrics
    assert "recall" in synth_metrics
    assert "f1" in synth_metrics

    assert "accuracy" in baseline_metrics
    assert "f1" in baseline_metrics


def test_us025_regression_task():
    np.random.seed(42)
    n = 120

    x1 = np.random.uniform(1, 100, n)
    x2 = np.random.uniform(5, 50, n)
    y = 3.5 * x1 + 2.0 * x2 + np.random.normal(0, 5, n)

    real_df = pd.DataFrame({"quantity": x1, "unit_cost": x2, "total_cost": y})

    synth_x1 = np.random.uniform(1, 100, n)
    synth_x2 = np.random.uniform(5, 50, n)
    synth_y = 3.5 * synth_x1 + 2.0 * synth_x2 + np.random.normal(0, 5, n)

    synth_df = pd.DataFrame({
        "quantity": synth_x1,
        "unit_cost": synth_x2,
        "total_cost": synth_y,
    })

    result = evaluate_ml_utility(real_df, synth_df, target_column="total_cost")

    assert result["metric"] == "ml_utility"
    assert result["status"] == "evaluated"
    assert result["task_type"] == "regression"
    assert result["target_column"] == "total_cost"
    assert result["overall_score"] is not None
    assert result["overall_score"] > 60.0

    synth_metrics = result["synthetic_metrics"]
    baseline_metrics = result["baseline_metrics"]

    assert "r2" in synth_metrics
    assert "mae" in synth_metrics
    assert "rmse" in synth_metrics

    assert "r2" in baseline_metrics
    assert "mae" in baseline_metrics
    assert "rmse" in baseline_metrics


def test_us025_no_suitable_ml_task():
    # Only 1 column, cannot formulate ML task
    real_df = pd.DataFrame({
        "customer_id": ["ID-1", "ID-2", "ID-3", "ID-4", "ID-5"],
    })
    synth_df = pd.DataFrame({
        "customer_id": ["ID-10", "ID-20", "ID-30", "ID-40", "ID-50"],
    })

    configs = [{"column_name": "customer_id", "is_identifier": True}]

    result = evaluate_ml_utility(real_df, synth_df, column_configurations=configs)

    assert result["metric"] == "ml_utility"
    assert result["status"] == "not_applicable"
    assert result["overall_score"] is None
    assert "No suitable" in result["reason"]
