import pandas as pd

from backend.services.supply_chain_domain_service import (
    calculate_quality_metrics,
    _append_quality_metric_comparisons,
)


def test_completeness_counts_nan_and_blank_strings():
    df = pd.DataFrame({"amount": [10, None], "status": ["ok", "   "]})
    metrics = calculate_quality_metrics(df)
    assert metrics["completeness_score"] == 50.0


def test_duplicate_row_rate_is_calculated():
    df = pd.DataFrame({"order_id": [1, 1, 2], "status": ["A", "A", "B"]})
    metrics = calculate_quality_metrics(df)
    assert metrics["duplicate_row_rate"] == round(100 / 3, 4)


def test_date_order_violation_rate_is_calculated():
    df = pd.DataFrame({
        "shipment_date": ["2026-01-10", "2026-01-12", "2026-01-13", "2026-01-14"],
        "delivery_date": ["2026-01-11", "2026-01-11", "2026-01-14", "2026-01-15"],
    })
    metrics = calculate_quality_metrics(df)
    assert metrics["date_order_violation_rate"] == 25.0


def test_comparison_reports_improved_completeness():
    baseline = pd.DataFrame({"value": [1, None]})
    improved = pd.DataFrame({"value": [1, 2]})
    rows = _append_quality_metric_comparisons([], baseline, improved)
    completeness = next(row for row in rows if row["metric"] == "completeness_score")
    assert completeness["baseline"] == 50.0
    assert completeness["improved"] == 100.0
    assert completeness["status"] == "improved"
