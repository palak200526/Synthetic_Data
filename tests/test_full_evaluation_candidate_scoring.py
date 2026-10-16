import pandas as pd

from backend.services import supply_chain_domain_service as service


def test_candidate_score_includes_full_evaluation_metrics(monkeypatch):
    real = pd.DataFrame({
        "quantity": [1, 2, 3, 4, 5, 6],
        "unit_price": [10, 20, 30, 40, 50, 60],
        "status": ["A", "A", "B", "B", "A", "B"],
    })
    candidate = real.copy()

    monkeypatch.setattr(
        service,
        "evaluate_statistical_similarity",
        lambda *args, **kwargs: {"overall_score": 88.0},
    )
    monkeypatch.setattr(
        service,
        "evaluate_correlation_covariance",
        lambda *args, **kwargs: {"overall_score": 82.0, "mean_correlation_difference": 0.18},
    )
    monkeypatch.setattr(
        service,
        "evaluate_ml_utility",
        lambda *args, **kwargs: {"status": "evaluated", "overall_score": 75.0},
    )
    monkeypatch.setattr(
        service,
        "evaluate_privacy",
        lambda *args, **kwargs: {
            "status": "evaluated", "overall_score": 91.0,
            "exact_match_rate": 0.0, "dcr_ratio": 1.2,
        },
    )

    result = service._score_quality_candidate(real, candidate, rules=[])

    assert result["valid"] is True
    assert result["metrics"]["statistical_similarity_score"] == 88.0
    assert result["metrics"]["correlation_score"] == 82.0
    assert result["metrics"]["ml_utility_score"] == 75.0
    assert result["metrics"]["privacy_score"] == 91.0
    component_names = {item["metric"] for item in result["metrics"]["scoring_components"]}
    assert {
        "statistical_similarity_score", "correlation_score",
        "ml_utility_score", "privacy_score",
    }.issubset(component_names)
