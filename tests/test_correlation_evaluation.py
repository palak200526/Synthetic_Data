import numpy as np
import pandas as pd
import pytest

from backend.services.correlation_evaluation_service import (
    evaluate_correlation_covariance,
)


def test_us024_multiple_numerical_columns():
    np.random.seed(42)
    n = 100
    x = np.random.normal(50, 10, n)
    y = 2.5 * x + np.random.normal(0, 5, n)
    z = -1.2 * x + np.random.normal(0, 3, n)

    real_df = pd.DataFrame({"feat_x": x, "feat_y": y, "feat_z": z})

    # Synthetic with slight noise
    synth_df = pd.DataFrame({
        "feat_x": x + np.random.normal(0, 1, n),
        "feat_y": y + np.random.normal(0, 1, n),
        "feat_z": z + np.random.normal(0, 1, n),
    })

    result = evaluate_correlation_covariance(real_df, synth_df)

    assert result["metric"] == "correlation_covariance"
    assert result["status"] == "evaluated"
    assert result["overall_score"] is not None
    assert result["overall_score"] >= 80.0
    assert result["correlation_similarity"] is not None
    assert result["covariance_similarity"] is not None
    assert "feat_x" in result["source_correlation"]
    assert "feat_y" in result["synthetic_correlation"]
    assert "feat_z" in result["correlation_difference"]
    assert "source_covariance" in result
    assert "synthetic_covariance" in result
    assert "covariance_difference" in result


def test_us024_insufficient_numerical_columns():
    real_df = pd.DataFrame({
        "single_numeric": [10, 20, 30, 40, 50],
        "category": ["A", "B", "A", "B", "A"],
    })
    synth_df = pd.DataFrame({
        "single_numeric": [11, 19, 31, 39, 51],
        "category": ["A", "B", "A", "B", "A"],
    })

    result = evaluate_correlation_covariance(real_df, synth_df)

    assert result["status"] == "not_applicable"
    assert result["overall_score"] is None
    assert "minimum 2 required" in result["reason"]


def test_us024_constant_columns_handled_gracefully():
    real_df = pd.DataFrame({
        "constant_col": [5.0, 5.0, 5.0, 5.0, 5.0],
        "varying_col": [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    synth_df = pd.DataFrame({
        "constant_col": [5.0, 5.0, 5.0, 5.0, 5.0],
        "varying_col": [1.1, 1.9, 3.2, 3.8, 5.1],
    })

    # Should not crash with ZeroDivision or NaN
    result = evaluate_correlation_covariance(real_df, synth_df)

    assert result["status"] == "evaluated"
    assert result["overall_score"] is not None
    assert np.isfinite(result["overall_score"])


def test_us024_ignores_non_numerical_columns():
    real_df = pd.DataFrame({
        "user_id": ["U1", "U2", "U3", "U4", "U5"],
        "lead_time": [10.0, 15.0, 20.0, 25.0, 30.0],
        "delay_rate": [0.1, 0.2, 0.15, 0.25, 0.3],
        "text": ["review 1", "review 2", "review 3", "review 4", "review 5"],
    })
    synth_df = pd.DataFrame({
        "user_id": ["U9", "U8", "U7", "U6", "U5"],
        "lead_time": [11.0, 14.0, 21.0, 24.0, 29.0],
        "delay_rate": [0.12, 0.19, 0.16, 0.24, 0.28],
        "text": ["rev a", "rev b", "rev c", "rev d", "rev e"],
    })

    configs = [
        {"column_name": "user_id", "is_identifier": True, "action": "new_id"},
        {"column_name": "text", "action": "llm"},
    ]

    result = evaluate_correlation_covariance(real_df, synth_df, column_configurations=configs)

    assert result["status"] == "evaluated"
    assert set(result["numerical_columns"]) == {"lead_time", "delay_rate"}
    assert "user_id" not in result["numerical_columns"]
    assert "text" not in result["numerical_columns"]
