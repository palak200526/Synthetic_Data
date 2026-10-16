"""
Unit tests for quality enhancements:
- Derived feature recalculation
- Cyclical encoding/decoding round-trip
- Reject-resample never clips
- Marginal quantile matching preserves Spearman rank order
- Privacy guard detects and drops exact duplicate rows
- generate_rows integration
"""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from backend.services.quality_enhancement_service import (
    detect_derived_features,
    apply_derived_features,
    encode_cyclical_datetimes,
    decode_cyclical_datetimes,
    apply_rank_preserving_marginal_matching,
    match_categorical_frequencies,
    compute_correlation_error,
    privacy_guard_filter,
    overgenerate_and_reject_resample,
)
from backend.services.generation_service import generate_rows


def test_derived_column_recalculation():
    """Verify derived columns (multiplication and date diff) are detected and recalculated exactly."""
    np.random.seed(42)
    n = 200
    qty = np.random.randint(1, 100, size=n)
    cost = np.round(np.random.uniform(5.0, 50.0, size=n), 2)
    total = np.round(qty * cost, 2)

    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    lead_days = np.random.randint(1, 15, size=n)
    delivery_dates = dates + pd.to_timedelta(lead_days, unit="D")

    df = pd.DataFrame({
        "quantity": qty,
        "unit_cost": cost,
        "total_value": total,
        "shipment_date": dates.strftime("%Y-%m-%d"),
        "delivery_date": delivery_dates.strftime("%Y-%m-%d"),
    })

    rules = detect_derived_features(df)
    assert len(rules) >= 1

    # Verify arithmetic rule detected for total_value
    arith_rules = [r for r in rules if r.get("target") == "total_value"]
    assert len(arith_rules) == 1
    assert arith_rules[0]["operation"] == "multiply"

    # Perturb total_value to simulate imperfect synthetic generation
    perturbed_df = df.copy()
    perturbed_df["total_value"] = perturbed_df["total_value"] + 999.0

    # Apply derived features recomputation
    fixed_df = apply_derived_features(perturbed_df, rules)
    diff = np.abs(fixed_df["total_value"] - (fixed_df["quantity"] * fixed_df["unit_cost"]))
    assert np.all(diff < 1e-2)


def test_cyclical_round_trip():
    """Verify sin/cos cyclical encoding and decoding restores dates accurately."""
    dates_str = [
        "2026-01-15",
        "2026-04-20",
        "2026-07-04",
        "2026-10-31",
        "2026-12-25",
    ]
    df = pd.DataFrame({"order_date": dates_str})

    encoded_df, meta = encode_cyclical_datetimes(df, ["order_date"])
    assert "order_date" not in encoded_df.columns
    assert "order_date__ts" in encoded_df.columns
    assert "order_date__m_sin" in encoded_df.columns
    assert "order_date__m_cos" in encoded_df.columns

    decoded_df = decode_cyclical_datetimes(encoded_df, meta)
    assert "order_date" in decoded_df.columns
    for orig, restored in zip(dates_str, decoded_df["order_date"]):
        assert orig == restored


def test_reject_resample_never_clips():
    """Verify that rows failing validation are discarded and resampled, never clipped."""
    np.random.seed(42)

    # Generator producing values including negatives
    def mock_generator(count):
        vals = np.random.normal(loc=5, scale=10, size=count)
        return pd.DataFrame({"val": vals})

    # Constraint: val must be > 0 (e.g. positive quantity)
    def validator(df):
        return df["val"] > 0

    target_count = 50
    valid_df, total_rejected = overgenerate_and_reject_resample(
        generate_batch_fn=mock_generator,
        target_count=target_count,
        validation_filter_fn=validator,
        overgenerate_factor=1.5,
    )

    assert len(valid_df) == target_count
    # All values must strictly satisfy condition
    assert (valid_df["val"] > 0).all()
    # No clipped zeros exist (none should be exactly 0.0)
    assert not (valid_df["val"] == 0.0).any()
    assert total_rejected > 0


def test_marginal_matching_keeps_rank_order():
    """Verify rank-preserving quantile mapping preserves Spearman rank correlation identically."""
    np.random.seed(42)
    n = 200

    # Real data: skewed distribution
    x_real = np.random.exponential(scale=2.0, size=n)
    y_real = x_real * 1.5 + np.random.normal(0, 0.5, size=n)
    real_df = pd.DataFrame({"x": x_real, "y": y_real})

    # Synthetic data: poorly scaled gaussian from an early GAN epoch
    x_synth = np.random.normal(loc=10.0, scale=3.0, size=n)
    y_synth = x_synth * 1.2 + np.random.normal(0, 0.5, size=n)
    synth_df = pd.DataFrame({"x": x_synth, "y": y_synth})

    # Record Spearman correlation prior to marginal matching
    spearman_before, _ = stats.spearmanr(synth_df["x"], synth_df["y"])

    # Apply rank-preserving marginal matching
    matched_df = apply_rank_preserving_marginal_matching(real_df, synth_df, ks_threshold=0.01)

    spearman_after, _ = stats.spearmanr(matched_df["x"], matched_df["y"])

    # Spearman rank correlation must remain unchanged
    assert np.isclose(spearman_before, spearman_after, atol=1e-5)

    # But the marginal KS statistic vs real data must improve
    ks_before, _ = stats.ks_2samp(real_df["x"], synth_df["x"])
    ks_after, _ = stats.ks_2samp(real_df["x"], matched_df["x"])
    assert ks_after < ks_before


def test_privacy_guard_rejects_duplicates():
    """Verify privacy guard identifies rows copied verbatim from source and removes them."""
    real_df = pd.DataFrame({
        "item": ["A", "B", "C", "D", "E"],
        "cost": [10, 20, 30, 40, 50],
    })

    # Synthetic df contains 2 exact copies of real rows
    synth_df = pd.DataFrame({
        "item": ["A", "B", "X", "Y", "Z"],
        "cost": [10, 20, 99, 88, 77],
    })

    # Check exact duplicates: items A and B copy real rows
    guarded_df, meta = privacy_guard_filter(
        real_df=real_df,
        synthetic_df=synth_df,
        max_exact_duplicate_rate=0.0,
        max_attempts=3,
    )

    assert meta["duplicates_dropped"] == 2
    assert meta["final_exact_rate"] == 0.0
    # Guarded df should not contain (A, 10) or (B, 20)
    for row in guarded_df.itertuples():
        assert not (row.item == "A" and row.cost == 10)
        assert not (row.item == "B" and row.cost == 20)


def test_generate_rows_with_quality_enhancements():
    """Test full integration of quality enhancements inside generate_rows."""
    df = pd.DataFrame({
        "quantity": [10, 20, 30, 40, 50, 60],
        "unit_cost": [2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
        "total_value": [20.0, 60.0, 120.0, 200.0, 300.0, 420.0],
        "category": ["X", "Y", "X", "Y", "X", "Y"],
    })
    configurations = [{"column_name": c, "action": "keep"} for c in df.columns]

    synth = generate_rows(
        original_dataframe=df,
        configurations=configurations,
        model_name="gaussian_copula",
        num_rows=10,
        parameters={
            "enable_quality_enhancements": True,
            "enable_derived_features": True,
            "enable_marginal_matching": True,
            "enable_privacy_guard": True,
        },
    )

    assert len(synth) == 10
    assert "total_value" in synth.columns
    # Arithmetic rule must hold
    diff = np.abs(synth["total_value"] - (synth["quantity"] * synth["unit_cost"]))
    assert np.all(diff < 1e-2)


def test_supply_chain_semantics_and_rules_different_datasets():
    """Verify semantic detection and rule validation across structurally different Supply Chain schemas."""
    from backend.services.supply_chain_domain_service import (
        detect_supply_chain_semantics,
        infer_and_validate_domain_rules,
        reconstruct_supply_chain_features,
        calculate_domain_validity_score,
    )

    # 1. Inventory dataset: on_hand - reserved = available
    n = 100
    on_hand = np.random.randint(50, 500, size=n)
    reserved = np.random.randint(0, 50, size=n)
    available = on_hand - reserved
    reorder_pt = np.random.randint(10, 100, size=n)

    inv_df = pd.DataFrame({
        "inventory_id": [f"INV{i:04d}" for i in range(n)],
        "warehouse": ["WH_A" if i % 2 == 0 else "WH_B" for i in range(n)],
        "quantity_on_hand": on_hand,
        "quantity_reserved": reserved,
        "quantity_available": available,
        "reorder_point": reorder_pt,
        "inventory_status": ["Healthy" if a > r else "Low" for a, r in zip(available, reorder_pt)],
    })

    inv_semantics = detect_supply_chain_semantics(inv_df)
    assert "inventory_id" in inv_semantics["identifiers"]
    assert "quantity_on_hand" in inv_semantics["inventory_levels"]
    assert "quantity_available" in inv_semantics["inventory_levels"]
    assert "inventory_status" in inv_semantics["statuses"]

    inv_rules = infer_and_validate_domain_rules(inv_df, inv_semantics)
    # Must infer available = on_hand - reserved
    sub_rules = [r for r in inv_rules if r.get("operation") == "subtract"]
    assert len(sub_rules) >= 1
    assert sub_rules[0]["target"] == "quantity_available"
    assert set(sub_rules[0]["operands"]) == {"quantity_on_hand", "quantity_reserved"}

    # Test reconstruction on perturbed synthetic data
    bad_inv = inv_df.copy()
    bad_inv["quantity_available"] = 99999
    fixed_inv = reconstruct_supply_chain_features(bad_inv, inv_rules)
    assert np.all(fixed_inv["quantity_available"] == (fixed_inv["quantity_on_hand"] - fixed_inv["quantity_reserved"]))
    assert calculate_domain_validity_score(fixed_inv, inv_rules) == 100.0

    # 2. Shipments dataset: chronological dates and lead time
    ship_dates = pd.date_range("2026-03-01", periods=n, freq="D")
    lead_time = np.random.randint(2, 10, size=n)
    delivery_dates = ship_dates + pd.to_timedelta(lead_time, unit="D")

    ship_df = pd.DataFrame({
        "shipment_id": [f"SH{i:05d}" for i in range(n)],
        "destination": ["Port_A", "Port_B"] * (n // 2),
        "shipment_date": ship_dates.strftime("%Y-%m-%d"),
        "delivery_date": delivery_dates.strftime("%Y-%m-%d"),
        "shipment_status": ["Delivered"] * n,
    })

    ship_semantics = detect_supply_chain_semantics(ship_df)
    assert "shipment_date" in ship_semantics["dates"]
    assert "delivery_date" in ship_semantics["dates"]

    ship_rules = infer_and_validate_domain_rules(ship_df, ship_semantics)
    date_rules = [r for r in ship_rules if r.get("rule_type") == "chronological_date"]
    assert len(date_rules) >= 1
    assert date_rules[0]["start_date"] == "shipment_date"
    assert date_rules[0]["end_date"] == "delivery_date"

    # 3. Different column naming: Sales orders (qty_ordered * unit_rate = net_amount)
    sales_df = pd.DataFrame({
        "order_num": [f"ORD{i:04d}" for i in range(n)],
        "qty_ordered": np.random.randint(1, 50, size=n),
        "unit_rate": np.round(np.random.uniform(10.0, 100.0, size=n), 2),
    })
    sales_df["net_amount"] = sales_df["qty_ordered"] * sales_df["unit_rate"]

    sales_semantics = detect_supply_chain_semantics(sales_df)
    assert "order_num" in sales_semantics["identifiers"]
    assert "qty_ordered" in sales_semantics["quantities"]
    assert "unit_rate" in sales_semantics["prices"]
    assert "net_amount" in sales_semantics["prices"]

    sales_rules = infer_and_validate_domain_rules(sales_df, sales_semantics)
    assert any(r.get("target") == "net_amount" and r.get("operation") == "multiply" for r in sales_rules)

    # 4. Unrecognized or ambiguous columns without arithmetic relations (Safe fallback)
    noise_df = pd.DataFrame({
        "feature_x": np.random.normal(0, 1, size=n),
        "feature_y": np.random.normal(5, 2, size=n),
        "feature_z": np.random.exponential(1, size=n),
    })
    noise_rules = infer_and_validate_domain_rules(noise_df)
    # Must safely infer NO arithmetic rules (no false positives)
    assert len([r for r in noise_rules if r.get("rule_type") == "arithmetic"]) == 0


def test_side_by_side_comparison_builder():
    """Verify build_comparison_summary correctly reports metrics and delta directions."""
    from backend.services.supply_chain_domain_service import build_comparison_summary

    baseline_eval = {
        "statistical_similarity": {"overall_score": 64.3},
        "correlation_covariance": {"overall_score": 67.0, "mean_correlation_difference": 0.4468},
        "ml_utility": {"overall_score": 12.24},
        "privacy": {"exact_match_rate": 0.0, "dcr_ratio": 1.5, "overall_score": 100.0},
    }

    improved_eval = {
        "statistical_similarity": {"overall_score": 97.3},
        "correlation_covariance": {"overall_score": 90.94, "mean_correlation_difference": 0.1203},
        "ml_utility": {"overall_score": 39.9},
        "privacy": {"exact_match_rate": 0.0, "dcr_ratio": 1.48, "overall_score": 100.0},
    }

    rows, explanation = build_comparison_summary(
        baseline_eval=baseline_eval,
        improved_eval=improved_eval,
        baseline_validity=100.0,
        improved_validity=100.0,
    )

    row_map = {r["metric"]: r for r in rows}

    # Statistical similarity increased -> improved
    assert row_map["statistical_similarity"]["status"] == "improved"
    assert np.isclose(row_map["statistical_similarity"]["change"], 33.0)

    # Correlation error decreased -> improved (since lower is better!)
    assert row_map["correlation_error"]["status"] == "improved"
    assert row_map["correlation_error"]["change"] < 0

    # ML utility increased -> improved
    assert row_map["ml_utility_score"]["status"] == "improved"

    # Business rule validity unchanged
    assert row_map["business_rule_validity"]["status"] == "unchanged"

    assert "improved significantly" in explanation


def test_row_count_preservation_and_privacy_guard():
    """Verify exact target row count is strictly preserved under reject-resample and deduplication."""
    from backend.services.quality_enhancement_service import enhance_synthetic_dataset

    n = 100
    real_df = pd.DataFrame({
        "item_code": [f"ITM_{i}" for i in range(n)],
        "val": np.arange(n, dtype=float),
    })

    # Synthetic has exact copy of first 10 rows
    synth_df = real_df.copy()

    enhanced, meta = enhance_synthetic_dataset(
        real_df=real_df,
        synthetic_df=synth_df,
        apply_marginal_matching=True,
        apply_categorical_matching=False,
        apply_privacy_guard=True,
        max_exact_duplicate_rate=0.05,
    )

    # Must preserve row count
    assert len(enhanced) == len(synth_df)
    # Exact duplicate rate must be <= 0.05
    assert meta["privacy_info"]["final_exact_rate"] <= 0.05

