import pandas as pd

from backend.services.supply_chain_domain_service import (
    _score_quality_candidate,
    _select_best_quality_candidate,
)


def test_candidate_score_reports_quality_metrics_and_validity():
    real = pd.DataFrame({
        "quantity": [1, 2, 3, 4],
        "unit_price": [10.0, 20.0, 30.0, 40.0],
    })
    candidate = real.copy()

    result = _score_quality_candidate(real, candidate, rules=[])

    assert result["valid"] is True
    assert result["metrics"]["completeness_score"] == 100.0
    assert result["metrics"]["domain_validity_score"] == 100.0
    assert "candidate_score" in result["metrics"]


def test_selector_preserves_schema_and_row_count():
    real = pd.DataFrame({
        "quantity": [1, 2, 3, 4],
        "unit_price": [10.0, 20.0, 30.0, 40.0],
        "status": ["A", "A", "B", "B"],
    })
    baseline = pd.DataFrame({
        "quantity": [1, 2, 3, 4],
        "unit_price": [10.0, 20.0, 30.0, 40.0],
        "status": ["A", "A", "B", "B"],
    })
    enhanced = baseline.copy()

    selected, candidates, selected_name = _select_best_quality_candidate(
        real_df=real,
        baseline_df=baseline,
        enhanced_df=enhanced,
        rules=[],
        semantics={"statuses": [], "categories": []},
        derived_arithmetic=[],
    )

    assert len(selected) == len(baseline)
    assert list(selected.columns) == list(baseline.columns)
    assert candidates
    assert selected_name in {item["candidate"] for item in candidates}
    assert all("valid" in item for item in candidates)
