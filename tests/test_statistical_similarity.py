import numpy as np
import pandas as pd
import pytest

from backend.services.statistical_evaluation_service import (
    determine_column_eligibility,
    evaluate_statistical_similarity,
)


def test_us023_numerical_columns_evaluated():
    real_df = pd.DataFrame({
        "revenue": [100.0, 150.0, 200.0, 250.0, 300.0],
        "cost": [50.0, 70.0, 90.0, 110.0, 130.0],
    })
    synth_df = pd.DataFrame({
        "revenue": [105.0, 148.0, 198.0, 252.0, 295.0],
        "cost": [52.0, 68.0, 92.0, 108.0, 132.0],
    })

    result = evaluate_statistical_similarity(real_df, synth_df)

    assert result["metric"] == "statistical_similarity"
    assert result["evaluated_columns"] == 2
    assert result["excluded_columns"] == 0
    assert result["overall_score"] is not None
    assert result["overall_score"] > 80.0

    for col in ["revenue", "cost"]:
        col_res = result["columns"][col]
        assert col_res["column_type"] == "numerical"
        assert col_res["status"] == "evaluated"
        assert "mean_similarity" in col_res["metrics"]
        assert "std_similarity" in col_res["metrics"]
        assert "ks_similarity" in col_res["metrics"]
        assert col_res["score"] is not None


def test_us023_categorical_columns_evaluated():
    real_df = pd.DataFrame({
        "status": ["active", "active", "pending", "closed", "active"],
        "tier": ["gold", "silver", "bronze", "silver", "gold"],
    })
    synth_df = pd.DataFrame({
        "status": ["active", "active", "pending", "closed", "active"],
        "tier": ["gold", "silver", "bronze", "gold", "silver"],
    })

    result = evaluate_statistical_similarity(real_df, synth_df)

    assert result["evaluated_columns"] == 2
    for col in ["status", "tier"]:
        col_res = result["columns"][col]
        assert col_res["column_type"] == "categorical"
        assert col_res["status"] == "evaluated"
        assert "js_distance" in col_res["metrics"]
        assert "distribution_similarity" in col_res["metrics"]
        assert col_res["score"] is not None


def test_us023_free_form_text_excluded():
    real_df = pd.DataFrame({
        "review": [
            "This product exceeded all my expectations, will buy again!",
            "Completely broken on arrival, very disappointed with shipping.",
            "Average quality for the price, customer support was decent.",
            "Fantastic battery life and screen resolution is remarkable.",
            "Terrible experience, would not recommend to anyone at all.",
        ],
        "score": [5, 1, 3, 5, 1],
    })
    synth_df = pd.DataFrame({
        "review": [
            "Great product, highly recommend purchasing this.",
            "Poor quality and arrived damaged.",
            "Fair experience, could be better.",
            "Wonderful display and long battery.",
            "Horrible experience, never again.",
        ],
        "score": [5, 1, 3, 4, 1],
    })

    result = evaluate_statistical_similarity(real_df, synth_df)

    assert result["columns"]["review"]["status"] == "excluded"
    assert result["columns"]["review"]["reason"] == "free_form_text"
    assert result["columns"]["review"]["score"] is None
    assert result["evaluated_columns"] == 1
    assert result["excluded_columns"] == 1


def test_us023_identifier_excluded():
    real_df = pd.DataFrame({
        "user_id": ["USR-001", "USR-002", "USR-003", "USR-004", "USR-005"],
        "order_id": ["ORD-101", "ORD-102", "ORD-103", "ORD-104", "ORD-105"],
        "amount": [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    synth_df = pd.DataFrame({
        "user_id": ["USR-991", "USR-992", "USR-993", "USR-994", "USR-995"],
        "order_id": ["ORD-901", "ORD-902", "ORD-903", "ORD-904", "ORD-905"],
        "amount": [12.0, 19.0, 31.0, 39.0, 52.0],
    })

    result = evaluate_statistical_similarity(real_df, synth_df)

    assert result["columns"]["user_id"]["status"] == "excluded"
    assert result["columns"]["user_id"]["reason"] == "identifier"
    assert result["columns"]["user_id"]["score"] is None

    assert result["columns"]["order_id"]["status"] == "excluded"
    assert result["columns"]["order_id"]["reason"] == "identifier"
    assert result["columns"]["order_id"]["score"] is None

    assert result["columns"]["amount"]["status"] == "evaluated"
    assert result["evaluated_columns"] == 1
    assert result["excluded_columns"] == 2


def test_us023_datetime_excluded():
    real_df = pd.DataFrame({
        "created_at": [
            "2026-01-01 10:00:00",
            "2026-01-02 11:30:00",
            "2026-01-03 14:15:00",
            "2026-01-04 16:45:00",
            "2026-01-05 09:20:00",
        ],
        "category": ["A", "B", "A", "B", "A"],
    })
    synth_df = pd.DataFrame({
        "created_at": [
            "2026-01-01 10:05:00",
            "2026-01-02 11:25:00",
            "2026-01-03 14:10:00",
            "2026-01-04 16:50:00",
            "2026-01-05 09:15:00",
        ],
        "category": ["A", "B", "A", "A", "B"],
    })

    result = evaluate_statistical_similarity(real_df, synth_df)

    assert result["columns"]["created_at"]["status"] == "excluded"
    assert result["columns"]["created_at"]["reason"] == "datetime_not_supported"
    assert result["columns"]["created_at"]["score"] is None

    assert result["columns"]["category"]["status"] == "evaluated"
    assert result["evaluated_columns"] == 1
    assert result["excluded_columns"] == 1


def test_us023_overall_score_uses_only_evaluated_columns():
    real_df = pd.DataFrame({
        "User ID": ["U1", "U2", "U3", "U4", "U5"],
        "Sentiment": ["Positive", "Negative", "Positive", "Negative", "Positive"],
        "Text": ["text 1", "text 2", "text 3", "text 4", "text 5"],
        "Confidence Score": [0.8, 0.6, 0.9, 0.7, 0.85],
    })
    synth_df = pd.DataFrame({
        "User ID": ["U10", "U20", "U30", "U40", "U50"],
        "Sentiment": ["Positive", "Negative", "Positive", "Negative", "Positive"],
        "Text": ["synth text 1", "synth text 2", "synth text 3", "synth text 4", "synth text 5"],
        "Confidence Score": [0.81, 0.59, 0.89, 0.72, 0.84],
    })

    configs = [
        {"column_name": "User ID", "action": "new_id", "is_identifier": True},
        {"column_name": "Text", "action": "llm", "is_identifier": False},
        {"column_name": "Sentiment", "action": "keep", "column_type": "string"},
        {"column_name": "Confidence Score", "action": "keep", "column_type": "numeric"},
    ]

    result = evaluate_statistical_similarity(
        real_dataframe=real_df,
        synthetic_dataframe=synth_df,
        column_configurations=configs,
    )

    assert result["columns"]["User ID"]["status"] == "excluded"
    assert result["columns"]["Text"]["status"] == "excluded"
    assert result["columns"]["Sentiment"]["status"] == "evaluated"
    assert result["columns"]["Confidence Score"]["status"] == "evaluated"

    assert result["evaluated_columns"] == 2
    assert result["excluded_columns"] == 2

    sent_score = result["columns"]["Sentiment"]["score"]
    conf_score = result["columns"]["Confidence Score"]["score"]
    expected_overall = round((sent_score + conf_score) / 2.0, 2)
    assert result["overall_score"] == expected_overall


def test_us023_no_evaluable_columns_returns_null_score():
    real_df = pd.DataFrame({
        "user_id": ["U1", "U2", "U3"],
        "comments": ["long text review 1", "long text review 2", "long text review 3"],
        "timestamp": ["2026-01-01", "2026-01-02", "2026-01-03"],
    })
    synth_df = pd.DataFrame({
        "user_id": ["U10", "U20", "U30"],
        "comments": ["synth review 1", "synth review 2", "synth review 3"],
        "timestamp": ["2026-01-01", "2026-01-02", "2026-01-03"],
    })

    result = evaluate_statistical_similarity(real_df, synth_df)

    assert result["evaluated_columns"] == 0
    assert result["excluded_columns"] == 3
    assert result["overall_score"] is None
    assert "No applicable" in result["message"]
