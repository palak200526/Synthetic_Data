from backend.services.feedback_loop_service import build_feedback_insights


def test_feedback_insights_flags_regression_and_low_column_score():
    result = build_feedback_insights(
        metrics_comparison=[
            {
                "metric": "correlation_error",
                "label": "Correlation error",
                "baseline": 0.10,
                "improved": 0.20,
                "status": "regressed",
                "direction": "lower_is_better",
            },
            {
                "metric": "statistical_similarity",
                "label": "Statistical similarity",
                "baseline": 65,
                "improved": 72,
                "status": "improved",
                "direction": "higher_is_better",
            },
        ],
        improved_evaluation={
            "statistical_similarity": {
                "columns": {
                    "Order_Quantity": {"score": 61.2, "column_type": "numeric"},
                    "Supplier_Name": {"score": 88.0, "column_type": "categorical"},
                }
            }
        },
    )

    metrics = {item["metric"] for item in result["findings"]}
    assert "correlation_error" in metrics
    assert "statistical_similarity" in metrics
    assert "column_level_statistical_similarity" in metrics
    assert result["has_high_priority"] is True


def test_feedback_insights_does_not_treat_missing_metrics_as_zero():
    result = build_feedback_insights(
        metrics_comparison=[
            {
                "metric": "ml_utility_score",
                "label": "ML utility",
                "baseline": None,
                "improved": None,
                "status": "not_evaluated",
            }
        ]
    )
    assert result["finding_count"] == 0
