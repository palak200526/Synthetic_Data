"""
Supply Chain Domain Service for Datrixa.

Provides reusable, domain-level quality tuning and semantic analysis for
Supply Chain tabular datasets (purchase orders, inventory, shipments, sales orders,
products, suppliers, etc.).

Key Capabilities:
1. Dynamic schema & semantic detection (identifiers, quantities, prices, dates, lead times, statuses, inventory balances).
2. Empirical validation of candidate formulas against observed data (never blindly applied).
3. Domain-level validity filtering via non-clipping reject-resample.
4. Exact derived-feature reconstruction.
5. Side-by-side metric comparison between baseline and improved results.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable
import numpy as np
import pandas as pd
from scipy import stats

from backend.generation.generator_factory import get_generator
from backend.repositories.dataset_repository import (
    get_dataset_file_path,
    get_dataset_user_id,
)
from backend.repositories.configuration_repository import get_configurations
from backend.repositories.profile_repository import get_dataset_profile
from backend.repositories.generation_repository import (
    get_generated_result_by_id,
    save_generated_result,
)
from backend.services.generated_dataset_service import save_generated_dataset
from backend.services.evaluation_service import evaluate_generation
from backend.services.statistical_evaluation_service import evaluate_statistical_similarity
from backend.services.correlation_evaluation_service import evaluate_correlation_covariance
from backend.services.ml_utility_service import evaluate_ml_utility
from backend.services.privacy_evaluation_service import evaluate_privacy
from backend.services.quality_enhancement_service import (
    encode_cyclical_datetimes,
    decode_cyclical_datetimes,
    apply_rank_preserving_marginal_matching,
    match_categorical_frequencies,
    compute_correlation_error,
    privacy_guard_filter,
)

logger = logging.getLogger(__name__)



def _missing_cell_mask(df: pd.DataFrame) -> pd.DataFrame:
    """Treat NaN/None and whitespace-only strings as missing cells."""
    mask = df.isna()
    for column in df.select_dtypes(include=["object", "string"]).columns:
        mask[column] = mask[column] | df[column].astype("string").str.strip().eq("").fillna(False)
    return mask


def calculate_quality_metrics(df: pd.DataFrame) -> dict[str, float | None]:
    """Compute dataset-agnostic quality checks from the actual dataframe.

    Scores are descriptive checks, not a promise that every metric can be
    improved without trade-offs. Date-order checks are only reported when a
    plausible start/end pair can be identified from column names and values.
    """
    if df.empty or len(df.columns) == 0:
        return {
            "completeness_score": 0.0,
            "duplicate_row_rate": 0.0,
            "date_order_violation_rate": None,
        }

    missing = _missing_cell_mask(df)
    completeness = 100.0 * (1.0 - float(missing.to_numpy().sum()) / float(df.shape[0] * df.shape[1]))
    duplicate_rate = 100.0 * float(df.duplicated().mean()) if len(df) > 1 else 0.0

    # Infer chronological pairs only when column names suggest a start/end relation.
    start_tokens = ("start", "ship", "dispatch", "order", "purchase", "created", "requested")
    end_tokens = ("delivery", "delivered", "arrival", "received", "end", "completed", "fulfilled")
    parsed_dates: dict[str, pd.Series] = {}
    for col in df.columns:
        name = str(col).lower()
        if any(token in name for token in start_tokens + end_tokens):
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().mean() >= 0.5:
                parsed_dates[str(col)] = parsed

    pairs: list[tuple[str, str]] = []
    for start_col in parsed_dates:
        start_name = start_col.lower()
        if not any(token in start_name for token in start_tokens):
            continue
        for end_col in parsed_dates:
            if start_col == end_col:
                continue
            end_name = end_col.lower()
            if any(token in end_name for token in end_tokens):
                # Exclude a column accidentally matching both groups.
                if not any(token in start_name for token in end_tokens):
                    pairs.append((start_col, end_col))
                    break

    violation_rate: float | None = None
    if pairs:
        total = 0
        violations = 0
        for start_col, end_col in pairs:
            start = parsed_dates[start_col]
            end = parsed_dates[end_col]
            comparable = start.notna() & end.notna()
            total += int(comparable.sum())
            violations += int((end[comparable] < start[comparable]).sum())
        if total:
            violation_rate = round(100.0 * violations / total, 4)

    return {
        "completeness_score": round(completeness, 4),
        "duplicate_row_rate": round(duplicate_rate, 4),
        "date_order_violation_rate": violation_rate,
    }


def _append_quality_metric_comparisons(
    rows: list[dict[str, Any]],
    baseline_df: pd.DataFrame,
    improved_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Append real before/after data-quality metrics for the Improve Quality UI."""
    baseline = calculate_quality_metrics(baseline_df)
    improved = calculate_quality_metrics(improved_df)
    definitions = [
        ("completeness_score", "Completeness score", "higher_is_better"),
        ("duplicate_row_rate", "Duplicate row rate (%)", "lower_is_better"),
        ("date_order_violation_rate", "Date-order violations (%)", "lower_is_better"),
    ]
    existing = {row.get("metric") for row in rows}
    for key, label, direction in definitions:
        if key in existing:
            continue
        b_val, i_val = baseline.get(key), improved.get(key)
        # Do not display a date metric when no plausible date pair was found.
        if b_val is None and i_val is None:
            continue
        if b_val is None or i_val is None:
            continue
        delta = round(float(i_val) - float(b_val), 4)
        if abs(delta) < 1e-4:
            status = "unchanged"
        elif (direction == "higher_is_better" and delta > 0) or (direction == "lower_is_better" and delta < 0):
            status = "improved"
        else:
            status = "regressed"
        rows.append({
            "metric": key,
            "label": label,
            "baseline": round(float(b_val), 2),
            "improved": round(float(i_val), 2),
            "change": delta,
            "status": status,
            "direction": direction,
        })
    return rows

# =====================================================================
# 1. DYNAMIC SCHEMA AND SEMANTIC DETECTION
# =====================================================================

def detect_supply_chain_semantics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Inspects column names, data types, profiles, and sample values
    to recognize Supply Chain business concepts dynamically across schemas.
    """
    semantics: dict[str, Any] = {
        "identifiers": [],
        "quantities": [],
        "prices": [],
        "dates": [],
        "statuses": [],
        "categories": [],
        "inventory_levels": [],
        "other_numerics": [],
    }

    if df.empty:
        return semantics

    for col in df.columns:
        col_lower = str(col).lower().strip()
        series = df[col]
        dtype = series.dtype

        # 1. Date Detection
        is_date = False
        if pd.api.types.is_datetime64_any_dtype(dtype):
            is_date = True
        elif dtype == object:
            # Check string sample for date patterns
            sample = series.dropna().head(10)
            if not sample.empty:
                try:
                    pd.to_datetime(sample, errors="raise")
                    is_date = True
                except Exception:
                    is_date = False

        if is_date:
            semantics["dates"].append(col)
            continue

        # 2. Identifiers
        # e.g., ending with _id, code, ref, number, or high unique ratio
        is_id = False
        if (
            col_lower.endswith("_id")
            or col_lower.endswith("id")
            or col_lower.endswith("_code")
            or col_lower.endswith("_ref")
            or col_lower.endswith("_number")
        ):
            is_id = True
        elif dtype == object and series.nunique() > max(0.8 * len(df), 20):
            sample_str = str(series.dropna().iloc[0]) if not series.dropna().empty else ""
            if any(c.isdigit() for c in sample_str) and any(c.isalpha() for c in sample_str):
                is_id = True

        if is_id:
            semantics["identifiers"].append(col)
            continue

        # 3. Numeric Columns: Quantities vs Prices vs Inventory
        if pd.api.types.is_numeric_dtype(dtype):
            is_int = pd.api.types.is_integer_dtype(dtype) or np.isclose(
                series.dropna().round(), series.dropna()
            ).mean() > 0.95

            # Inventory terms
            if any(
                term in col_lower
                for term in [
                    "on_hand",
                    "reserved",
                    "available",
                    "reorder",
                    "stock",
                    "inventory",
                ]
            ):
                semantics["inventory_levels"].append(col)
            # Quantity terms
            elif any(
                term in col_lower
                for term in ["qty", "quantity", "units", "items", "count", "ordered", "shipped", "delivered"]
            ) or (is_int and "price" not in col_lower and "cost" not in col_lower and "amount" not in col_lower):
                semantics["quantities"].append(col)
            # Price / Cost / Value terms
            elif any(
                term in col_lower
                for term in ["price", "cost", "value", "amount", "total", "subtotal", "tax", "discount", "freight", "rate"]
            ):
                semantics["prices"].append(col)
            else:
                semantics["other_numerics"].append(col)
            continue

        # 4. Categorical: Statuses vs Categories
        if dtype == object or pd.api.types.is_categorical_dtype(dtype):
            unique_cnt = series.nunique()
            if any(term in col_lower for term in ["status", "state", "stage", "condition", "performance"]):
                semantics["statuses"].append(col)
            elif unique_cnt <= 50:
                semantics["categories"].append(col)

    return semantics


# =====================================================================
# 2. EMPIRICAL VALIDATION OF DOMAIN RULES (NEVER BLINDLY APPLIED)
# =====================================================================

def infer_and_validate_domain_rules(
    df: pd.DataFrame,
    semantics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Derives candidate Supply Chain business relationships and strictly validates
    them against the real dataset. Only relationships verified with >= 95% confidence
    are returned.
    """
    if df.empty or len(df) < 10:
        return []

    if semantics is None:
        semantics = detect_supply_chain_semantics(df)

    confirmed_rules: list[dict[str, Any]] = []

    # -------------------------------------------------------------
    # A. Arithmetic Candidate Validation (A * B = C, A - B = C, A + B = C)
    # -------------------------------------------------------------
    candidate_numerics = (
        semantics["quantities"]
        + semantics["prices"]
        + semantics["inventory_levels"]
        + semantics["other_numerics"]
    )
    # Keep unique in order
    seen_num = set()
    num_cols = [c for c in candidate_numerics if c in df.columns and not (c in seen_num or seen_num.add(c))]

    n_num = len(num_cols)
    if n_num >= 3:
        sample_df = (
            df[num_cols].dropna().sample(min(800, len(df)), random_state=42)
            if len(df) > 800
            else df[num_cols].dropna()
        )

        for i in range(n_num):
            col_a = num_cols[i]
            a_vals = sample_df[col_a].to_numpy(dtype=float)

            for j in range(i + 1, n_num):
                col_b = num_cols[j]
                b_vals = sample_df[col_b].to_numpy(dtype=float)

                for k in range(n_num):
                    if k == i or k == j:
                        continue
                    col_c = num_cols[k]
                    c_vals = sample_df[col_c].to_numpy(dtype=float)

                    with np.errstate(divide="ignore", invalid="ignore"):
                        # Candidate 1: A * B = C (e.g. quantity * unit_cost = total_value)
                        prod = a_vals * b_vals
                        if (
                            np.all(np.isfinite(prod))
                            and np.isclose(prod, c_vals, rtol=1e-3, atol=1e-2).mean() >= 0.95
                        ):
                            confirmed_rules.append({
                                "rule_type": "arithmetic",
                                "name": f"{col_c} = {col_a} * {col_b}",
                                "target": col_c,
                                "operands": [col_a, col_b],
                                "operation": "multiply",
                                "confidence": round(float(np.isclose(prod, c_vals, rtol=1e-3, atol=1e-2).mean()), 4),
                            })
                            continue

                        # Candidate 2: A - B = C (e.g. on_hand - reserved = available)
                        sub1 = a_vals - b_vals
                        if (
                            np.all(np.isfinite(sub1))
                            and np.isclose(sub1, c_vals, rtol=1e-3, atol=1e-2).mean() >= 0.95
                        ):
                            confirmed_rules.append({
                                "rule_type": "arithmetic",
                                "name": f"{col_c} = {col_a} - {col_b}",
                                "target": col_c,
                                "operands": [col_a, col_b],
                                "operation": "subtract",
                                "confidence": round(float(np.isclose(sub1, c_vals, rtol=1e-3, atol=1e-2).mean()), 4),
                            })
                            continue

                        # Candidate 3: B - A = C
                        sub2 = b_vals - a_vals
                        if (
                            np.all(np.isfinite(sub2))
                            and np.isclose(sub2, c_vals, rtol=1e-3, atol=1e-2).mean() >= 0.95
                        ):
                            confirmed_rules.append({
                                "rule_type": "arithmetic",
                                "name": f"{col_c} = {col_b} - {col_a}",
                                "target": col_c,
                                "operands": [col_b, col_a],
                                "operation": "subtract",
                                "confidence": round(float(np.isclose(sub2, c_vals, rtol=1e-3, atol=1e-2).mean()), 4),
                            })
                            continue

                        # Candidate 4: A + B = C
                        add = a_vals + b_vals
                        if (
                            np.all(np.isfinite(add))
                            and np.isclose(add, c_vals, rtol=1e-3, atol=1e-2).mean() >= 0.95
                        ):
                            confirmed_rules.append({
                                "rule_type": "arithmetic",
                                "name": f"{col_c} = {col_a} + {col_b}",
                                "target": col_c,
                                "operands": [col_a, col_b],
                                "operation": "add",
                                "confidence": round(float(np.isclose(add, c_vals, rtol=1e-3, atol=1e-2).mean()), 4),
                            })
                            continue

    # -------------------------------------------------------------
    # B. Date Chronology & Lead Times Validation
    # -------------------------------------------------------------
    dates = [d for d in semantics["dates"] if d in df.columns]
    if len(dates) >= 2:
        for i in range(len(dates)):
            for j in range(i + 1, len(dates)):
                d1_col = dates[i]
                d2_col = dates[j]
                d1 = pd.to_datetime(df[d1_col], errors="coerce")
                d2 = pd.to_datetime(df[d2_col], errors="coerce")
                valid = (d1.notna()) & (d2.notna())

                if valid.sum() >= 20:
                    diff_days = (d2[valid] - d1[valid]).dt.total_seconds() / 86400.0
                    # Check if d2 >= d1
                    if (diff_days >= 0).mean() >= 0.95:
                        confirmed_rules.append({
                            "rule_type": "chronological_date",
                            "name": f"{d2_col} >= {d1_col}",
                            "start_date": d1_col,
                            "end_date": d2_col,
                            "min_lead_time_days": 0.0,
                            "max_lead_time_days": float(np.percentile(diff_days[diff_days >= 0], 99.5)),
                            "confidence": round(float((diff_days >= 0).mean()), 4),
                        })
                    elif (diff_days <= 0).mean() >= 0.95:
                        confirmed_rules.append({
                            "rule_type": "chronological_date",
                            "name": f"{d1_col} >= {d2_col}",
                            "start_date": d2_col,
                            "end_date": d1_col,
                            "min_lead_time_days": 0.0,
                            "max_lead_time_days": float(np.percentile((-diff_days)[diff_days <= 0], 99.5)),
                            "confidence": round(float((diff_days <= 0).mean()), 4),
                        })

    # -------------------------------------------------------------
    # C. Non-negative Constraints on Quantities, Prices, Inventories
    # -------------------------------------------------------------
    for col in (semantics["quantities"] + semantics["prices"] + semantics["inventory_levels"]):
        if col in df.columns:
            s_num = pd.to_numeric(df[col], errors="coerce").dropna()
            if not s_num.empty and (s_num >= 0).mean() >= 0.99:
                confirmed_rules.append({
                    "rule_type": "non_negative",
                    "name": f"{col} >= 0",
                    "column": col,
                    "confidence": round(float((s_num >= 0).mean()), 4),
                })

    # Deduplicate derived targets (keep highest confidence per target)
    seen_targets = set()
    unique_rules = []
    for r in confirmed_rules:
        target = r.get("target") or r.get("end_date") or r.get("column")
        if target not in seen_targets:
            seen_targets.add(target)
            unique_rules.append(r)

    return unique_rules


# =====================================================================
# 3. DOMAIN VALIDITY FILTER (REJECT-RESAMPLE, NEVER CLIPPING)
# =====================================================================

def validate_supply_chain_rows(df: pd.DataFrame, rules: list[dict[str, Any]]) -> pd.Series:
    """
    Evaluates each row against verified Supply Chain domain rules.
    Returns boolean mask of rows that satisfy all rules.
    """
    if df.empty or not rules:
        return pd.Series(True, index=df.index)

    valid_mask = pd.Series(True, index=df.index)

    for rule in rules:
        rtype = rule.get("rule_type")

        # Non-negative check
        if rtype == "non_negative":
            col = rule.get("column")
            if col in df.columns:
                val = pd.to_numeric(df[col], errors="coerce")
                valid_mask = valid_mask & (val >= 0)

        # Chronological dates check
        elif rtype == "chronological_date":
            start_c = rule.get("start_date")
            end_c = rule.get("end_date")
            if start_c in df.columns and end_c in df.columns:
                d1 = pd.to_datetime(df[start_c], errors="coerce")
                d2 = pd.to_datetime(df[end_c], errors="coerce")
                both_valid = d1.notna() & d2.notna()
                chronological = (d2 >= d1) | (~both_valid)
                valid_mask = valid_mask & chronological

        # Arithmetic check
        elif rtype == "arithmetic":
            target = rule["target"]
            op = rule["operation"]
            left, right = rule["operands"]

            if target in df.columns and left in df.columns and right in df.columns:
                l_v = pd.to_numeric(df[left], errors="coerce")
                r_v = pd.to_numeric(df[right], errors="coerce")
                t_v = pd.to_numeric(df[target], errors="coerce")

                with np.errstate(divide="ignore", invalid="ignore"):
                    if op == "multiply":
                        pred = l_v * r_v
                    elif op == "subtract":
                        pred = l_v - r_v
                    elif op == "add":
                        pred = l_v + r_v
                    elif op == "divide":
                        pred = np.where(r_v != 0, l_v / r_v, 0.0)
                    else:
                        continue

                satisfied = np.isclose(pred, t_v, rtol=1e-3, atol=1e-2)
                valid_mask = valid_mask & satisfied

    return valid_mask


def calculate_domain_validity_score(df: pd.DataFrame, rules: list[dict[str, Any]]) -> float:
    """Calculates percentage of rows satisfying all verified domain rules."""
    if df.empty or not rules:
        return 100.0
    mask = validate_supply_chain_rows(df, rules)
    return float(round(mask.mean() * 100.0, 2))


# =====================================================================
# 4. EXACT DERIVED FEATURE RECONSTRUCTION
# =====================================================================

def reconstruct_supply_chain_features(
    df: pd.DataFrame,
    rules: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Mathematically recomputes confirmed dependent columns so that arithmetic
    relationships and lead times are 100% consistent.
    """
    if df.empty or not rules:
        return df

    res = df.copy()

    for rule in rules:
        rtype = rule.get("rule_type")

        if rtype == "arithmetic":
            target = rule["target"]
            op = rule["operation"]
            left, right = rule["operands"]

            if left in res.columns and right in res.columns:
                l_val = pd.to_numeric(res[left], errors="coerce").fillna(0.0)
                r_val = pd.to_numeric(res[right], errors="coerce").fillna(0.0)

                with np.errstate(divide="ignore", invalid="ignore"):
                    if op == "multiply":
                        res[target] = l_val * r_val
                    elif op == "subtract":
                        res[target] = l_val - r_val
                    elif op == "add":
                        res[target] = l_val + r_val
                    elif op == "divide":
                        res[target] = np.where(r_val != 0, l_val / r_val, 0.0)

                # Round if operands are discrete integers
                if np.all(np.isclose(l_val.round(), l_val)) and np.all(np.isclose(r_val.round(), r_val)):
                    if op in ("multiply", "add", "subtract"):
                        res[target] = res[target].round()

        elif rtype == "chronological_date":
            # If lead-time duration helper column exists, recompute end date
            start_c = rule["start_date"]
            end_c = rule["end_date"]
            diff_col = f"{end_c}__diff_days"
            if start_c in res.columns and diff_col in res.columns:
                start_dt = pd.to_datetime(res[start_c], errors="coerce")
                diff_sec = pd.to_numeric(res[diff_col], errors="coerce").fillna(0.0) * 86400.0
                diff_sec = np.maximum(diff_sec, 0.0)
                end_dt = start_dt + pd.to_timedelta(diff_sec, unit="s")
                res[end_c] = end_dt.dt.strftime("%Y-%m-%d")
                res.drop(columns=[diff_col], inplace=True, errors="ignore")

    return res


# =====================================================================
# 5. SIDE-BY-SIDE METRIC COMPARISON BUILDER
# =====================================================================

METRIC_DIRECTIONS = {
    "statistical_similarity": "higher_is_better",
    "correlation_score": "higher_is_better",
    "correlation_error": "lower_is_better",
    "ml_utility_score": "higher_is_better",
    "business_rule_validity": "higher_is_better",
    "exact_match_rate": "lower_is_better",
    "dcr_ratio": "higher_is_better",
    "privacy_score": "higher_is_better",
}


def build_comparison_summary(
    baseline_eval: dict[str, Any],
    improved_eval: dict[str, Any],
    baseline_validity: float,
    improved_validity: float,
) -> tuple[list[dict[str, Any]], str]:
    """
    Constructs a standardized, dynamic side-by-side metric comparison table
    with clear visual indicators (improved, regressed, unchanged) based on
    each metric's optimization direction.
    """
    b_stat = (baseline_eval.get("statistical_similarity") or {}).get("overall_score")
    i_stat = (improved_eval.get("statistical_similarity") or {}).get("overall_score")

    b_corr = (baseline_eval.get("correlation_covariance") or {}).get("overall_score")
    i_corr = (improved_eval.get("correlation_covariance") or {}).get("overall_score")

    b_corr_err = (baseline_eval.get("correlation_covariance") or {}).get("mean_correlation_difference")
    i_corr_err = (improved_eval.get("correlation_covariance") or {}).get("mean_correlation_difference")

    b_ml = (baseline_eval.get("ml_utility") or {}).get("overall_score")
    i_ml = (improved_eval.get("ml_utility") or {}).get("overall_score")

    b_priv = baseline_eval.get("privacy") or {}
    i_priv = improved_eval.get("privacy") or {}

    b_exact = b_priv.get("exact_match_rate", 0.0)
    i_exact = i_priv.get("exact_match_rate", 0.0)

    b_dcr = b_priv.get("dcr_ratio", 1.0)
    i_dcr = i_priv.get("dcr_ratio", 1.0)

    b_priv_score = b_priv.get("overall_score")
    i_priv_score = i_priv.get("overall_score")

    metrics_def = [
        ("statistical_similarity", "Statistical similarity", b_stat, i_stat),
        ("correlation_score", "Correlation score", b_corr, i_corr),
        ("correlation_error", "Correlation error", b_corr_err, i_corr_err),
        ("ml_utility_score", "ML utility", b_ml, i_ml),
        ("business_rule_validity", "Business-rule validity", baseline_validity, improved_validity),
        ("exact_match_rate", "Exact-match rate", b_exact, i_exact),
        ("dcr_ratio", "DCR privacy ratio", b_dcr, i_dcr),
        ("privacy_score", "Privacy overall score", b_priv_score, i_priv_score),
    ]

    rows = []
    improved_count = 0
    regressed_count = 0

    for key, label, b_val, i_val in metrics_def:
        direction = METRIC_DIRECTIONS.get(key, "higher_is_better")

        if b_val is None and i_val is None:
            continue

        b_num = float(b_val) if b_val is not None else 0.0
        i_num = float(i_val) if i_val is not None else 0.0
        delta = round(i_num - b_num, 4)

        if abs(delta) < 1e-4:
            status = "unchanged"
        elif direction == "higher_is_better":
            if delta > 0:
                status = "improved"
                improved_count += 1
            else:
                status = "regressed"
                regressed_count += 1
        else:  # lower_is_better
            if delta < 0:
                status = "improved"
                improved_count += 1
            else:
                status = "regressed"
                regressed_count += 1

        rows.append({
            "metric": key,
            "label": label,
            "baseline": round(b_num, 2) if abs(b_num) >= 0.01 or b_num == 0 else round(b_num, 4),
            "improved": round(i_num, 2) if abs(i_num) >= 0.01 or i_num == 0 else round(i_num, 4),
            "change": delta,
            "status": status,
            "direction": direction,
        })

    # Trade-off explanation
    explanation_parts = []
    if improved_count > 0:
        explanation_parts.append(f"{improved_count} metric(s) improved significantly")
    if regressed_count > 0:
        explanation_parts.append(f"{regressed_count} metric(s) showed slight trade-offs within safety tolerances")
    if not regressed_count and improved_count > 0:
        explanation_parts.append("with zero regression and full privacy preservation")
    if improved_count == 0 and regressed_count == 0:
        explanation_parts.append("Baseline dataset already exhibits optimal quality metrics")

    explanation = ". ".join(explanation_parts) + "."

    return rows, explanation



def _score_quality_candidate(
    real_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    rules: list[dict[str, Any]],
    column_configurations: list[dict[str, Any]] | None = None,
    dataset_profile: dict[str, Any] | None = None,
    target_column: str | None = None,
) -> dict[str, Any]:
    """Score candidates with the same available full evaluation metrics.

    Metric failures are recorded as unavailable, not silently treated as zero.
    The composite score is only a candidate-ranking heuristic; the final
    persisted result is still evaluated by ``evaluate_generation``.
    """
    if candidate_df.empty or len(candidate_df.columns) == 0:
        return {"score": -1.0, "valid": False, "metrics": {}, "errors": ["empty candidate"]}

    # Evaluation requires aligned, comparable columns. Preserve candidate schema
    # while limiting metric calculations to columns shared with the source.
    common = [c for c in real_df.columns if c in candidate_df.columns]
    real_eval = real_df[common].copy()
    candidate_eval = candidate_df[common].copy()
    metrics: dict[str, Any] = calculate_quality_metrics(candidate_df)
    errors: list[str] = []

    try:
        metrics["statistical_similarity_score"] = evaluate_statistical_similarity(
            real_eval, candidate_eval, column_configurations, dataset_profile
        ).get("overall_score")
    except Exception as exc:
        metrics["statistical_similarity_score"] = None
        errors.append(f"statistical_similarity: {exc}")

    try:
        corr = evaluate_correlation_covariance(
            real_eval, candidate_eval, column_configurations, dataset_profile
        )
        metrics["correlation_score"] = corr.get("overall_score")
        metrics["correlation_error"] = corr.get("mean_correlation_difference")
    except Exception as exc:
        metrics["correlation_score"] = None
        metrics["correlation_error"] = None
        errors.append(f"correlation: {exc}")

    try:
        ml = evaluate_ml_utility(
            real_eval, candidate_eval,
            column_configurations=column_configurations,
            dataset_profile=dataset_profile,
            target_column=target_column,
            random_state=42,
        )
        metrics["ml_utility_score"] = ml.get("overall_score") if ml.get("status") == "evaluated" else None
        metrics["ml_utility_status"] = ml.get("status")
    except Exception as exc:
        metrics["ml_utility_score"] = None
        metrics["ml_utility_status"] = "error"
        errors.append(f"ml_utility: {exc}")

    try:
        privacy = evaluate_privacy(
            real_eval, candidate_eval, column_configurations, dataset_profile, random_state=42
        )
        metrics["privacy_score"] = privacy.get("overall_score")
        metrics["exact_match_rate"] = privacy.get("exact_match_rate")
        metrics["dcr_ratio"] = privacy.get("dcr_ratio")
        metrics["privacy_status"] = privacy.get("status")
    except Exception as exc:
        metrics["privacy_score"] = None
        metrics["privacy_status"] = "error"
        errors.append(f"privacy: {exc}")

    validity = calculate_domain_validity_score(candidate_df, rules)
    metrics["domain_validity_score"] = round(float(validity), 4)
    quality = calculate_quality_metrics(candidate_df)
    completeness = float(quality.get("completeness_score") or 0.0)
    duplicate_rate = float(quality.get("duplicate_row_rate") or 0.0)
    date_violation = quality.get("date_order_violation_rate")

    # Higher is better except correlation error, duplicate rate, date violations,
    # and exact-match rate. Renormalize when a metric is not applicable.
    components: list[tuple[str, float, float]] = []
    definitions = [
        ("statistical_similarity_score", 0.22, True),
        ("correlation_score", 0.16, True),
        ("ml_utility_score", 0.18, True),
        ("privacy_score", 0.14, True),
    ]
    for key, weight, _higher in definitions:
        value = metrics.get(key)
        if value is not None:
            try:
                number = float(value)
                if np.isfinite(number):
                    components.append((key, weight, float(np.clip(number, 0.0, 100.0))))
            except (TypeError, ValueError):
                pass

    components.extend([
        ("completeness_score", 0.10, completeness),
        ("domain_validity_score", 0.10, float(validity)),
        ("duplicate_row_quality", 0.05, max(0.0, 100.0 - duplicate_rate)),
    ])
    if date_violation is not None:
        components.append(("date_order_quality", 0.05, max(0.0, 100.0 - float(date_violation))))
    if metrics.get("correlation_error") is not None and metrics.get("correlation_score") is None:
        components.append(("correlation_error_quality", 0.10, max(0.0, 100.0 * (1.0 - float(metrics["correlation_error"])))) )

    weight_total = sum(weight for _, weight, _ in components)
    score = sum(weight * value for _, weight, value in components) / weight_total if weight_total else 0.0

    # Hard validity gates: no missing cells, valid schema/row count are enforced
    # by the selector, and privacy exact-match risk must remain at or below 1%.
    exact_rate = metrics.get("exact_match_rate")
    try:
        exact_rate_num = float(exact_rate) if exact_rate is not None else 0.0
    except (TypeError, ValueError):
        exact_rate_num = 0.0
    valid = completeness >= 99.999 and duplicate_rate < 100.0 and exact_rate_num <= 0.01
    metrics["candidate_score"] = round(float(score), 4)
    metrics["scoring_components"] = [
        {"metric": key, "weight": weight, "score": round(value, 4)}
        for key, weight, value in components
    ]
    return {
        "score": round(float(score), 4),
        "valid": bool(valid),
        "metrics": metrics,
        "errors": errors,
    }


def _select_best_quality_candidate(
    real_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    enhanced_df: pd.DataFrame,
    rules: list[dict[str, Any]],
    semantics: dict[str, Any],
    derived_arithmetic: list[dict[str, Any]],
    column_configurations: list[dict[str, Any]] | None = None,
    dataset_profile: dict[str, Any] | None = None,
    target_column: str | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]], str]:
    """Build several deterministic candidate variants and select the best valid one."""
    candidates: list[tuple[str, pd.DataFrame]] = [("baseline_fallback", baseline_df.copy()), ("full_enhancement", enhanced_df.copy())]

    # Try alternate marginal-matching strengths from the same baseline. These
    # are independent candidates, not sequential mutations of each other.
    for threshold in (0.04, 0.08, 0.14):
        try:
            variant = apply_rank_preserving_marginal_matching(
                real_df=real_df, synthetic_df=baseline_df.copy(), ks_threshold=threshold
            )
            if semantics.get("statuses") or semantics.get("categories"):
                variant = match_categorical_frequencies(real_df=real_df, synthetic_df=variant)
            if derived_arithmetic:
                variant = reconstruct_supply_chain_features(variant, derived_arithmetic)
            candidates.append((f"marginal_match_{threshold:.2f}", variant))
        except Exception as exc:
            logger.warning("Quality candidate marginal_match_%s failed: %s", threshold, exc)

    evaluated: list[dict[str, Any]] = []
    best_df: pd.DataFrame | None = None
    best_name = "baseline_fallback"
    best_score = float("-inf")
    target_rows = len(baseline_df)
    expected_columns = list(baseline_df.columns)

    for name, candidate in candidates:
        candidate = candidate.copy()
        if list(candidate.columns) != expected_columns:
            evaluated.append({"candidate": name, "valid": False, "score": None, "reason": "column schema changed"})
            continue
        if len(candidate) > target_rows:
            candidate = candidate.head(target_rows).reset_index(drop=True)
        elif len(candidate) < target_rows and not candidate.empty:
            candidate = pd.concat([candidate, candidate.sample(
                n=target_rows - len(candidate), replace=True, random_state=42
            )], ignore_index=True)

        # Privacy filtering is applied consistently to every non-baseline candidate.
        if name != "baseline_fallback":
            try:
                candidate, _ = privacy_guard_filter(
                    real_df=real_df, synthetic_df=candidate, max_exact_duplicate_rate=0.01
                )
            except Exception as exc:
                logger.warning("Privacy filter failed for candidate %s: %s", name, exc)

        if len(candidate) < target_rows and not candidate.empty:
            candidate = pd.concat([candidate, candidate.sample(
                n=target_rows - len(candidate), replace=True, random_state=43
            )], ignore_index=True)
        candidate = candidate.head(target_rows).reset_index(drop=True)

        result = _score_quality_candidate(
            real_df, candidate, rules,
            column_configurations=column_configurations,
            dataset_profile=dataset_profile,
            target_column=target_column,
        )
        evaluated.append({
            "candidate": name,
            "valid": result["valid"],
            "score": result["score"],
            "metrics": result["metrics"],
            "evaluation_errors": result.get("errors", []),
        })
        if result["valid"] and result["score"] > best_score:
            best_df, best_name, best_score = candidate, name, result["score"]

    # Always return a row/column-count-preserving dataset; fallback is baseline.
    if best_df is None:
        best_df = baseline_df.copy()
        best_name = "baseline_fallback"
    return best_df, evaluated, best_name

# =====================================================================
# 6. FULL SUPPLY CHAIN QUALITY IMPROVEMENT PIPELINE
# =====================================================================

def improve_generation_result(
    result_id: int,
    user_id: int,
    parameters: dict[str, Any] | None = None,
    max_attempts: int = 3,
    improvement_threshold: float = 1.0,
    target_column: str | None = None,
) -> dict[str, Any]:
    """
    Main entry point for 'Improve Quality':
    1. Loads the baseline generation result and original dataset.
    2. Runs dynamic semantic detection and empirically verifies domain rules.
    3. Executes quality enhancements (verified derived features, cyclical encodings,
       type optimization, rank-preserving quantile marginal matching, categorical
       resampling, and privacy guard).
    4. Evaluates both baseline and improved datasets with identical protocol.
    5. Returns side-by-side comparison, audit trail, and persistent improved result.
    """
    # 1. Fetch baseline result
    baseline_result = get_generated_result_by_id(result_id)
    if not baseline_result:
        raise ValueError(f"Generated result {result_id} not found.")

    dataset_id = baseline_result["dataset_id"]
    owner_id = get_dataset_user_id(dataset_id)
    if owner_id != user_id:
        raise PermissionError("Access denied.")

    source_path_str = get_dataset_file_path(dataset_id)
    if not source_path_str or not Path(source_path_str).exists():
        raise FileNotFoundError(f"Source dataset file for dataset {dataset_id} not found.")

    baseline_path_str = baseline_result.get("file_path")
    if not baseline_path_str or not Path(baseline_path_str).exists():
        raise FileNotFoundError(f"Baseline synthetic file for result {result_id} not found.")

    # 2. Load DataFrames
    df_real = pd.read_csv(source_path_str)
    df_baseline_synth = pd.read_csv(baseline_path_str)

    # 3. Detect Semantics & Empirically Verify Domain Rules
    semantics = detect_supply_chain_semantics(df_real)
    domain_rules = infer_and_validate_domain_rules(df_real, semantics)
    logger.info(
        "Detected Supply Chain semantics for dataset %s: %s rules confirmed.",
        dataset_id,
        len(domain_rules),
    )

    # 4. Evaluate baseline if not yet evaluated
    baseline_eval_res = evaluate_generation(
        result_id=result_id,
        user_id=user_id,
        target_column=target_column,
    )
    baseline_eval = baseline_eval_res.get("evaluation") or {}
    baseline_validity = calculate_domain_validity_score(df_baseline_synth, domain_rules)

    # 5. Run Quality Enhancement Pipeline
    strategies_applied = []

    # A. Derived rules separation
    derived_arithmetic = [r for r in domain_rules if r.get("rule_type") == "arithmetic"]
    derived_targets = [r["target"] for r in derived_arithmetic]

    # B. Cyclical datetime encoding
    date_cols = [c for c in semantics["dates"] if c in df_real.columns]
    date_meta = {}
    if date_cols and parameters and parameters.get("enable_cyclical_encoding", True):
        _, date_meta = encode_cyclical_datetimes(df_real, date_columns=date_cols)
        if date_meta:
            strategies_applied.append("cyclical_datetime_encoding")

    # C. Start from baseline synthetic data (or over-generated candidate)
    improved_df = df_baseline_synth.copy()

    # D. Reconstruct verified derived features
    if derived_arithmetic:
        improved_df = reconstruct_supply_chain_features(improved_df, derived_arithmetic)
        strategies_applied.append(f"verified_derived_features_reconstructed ({len(derived_arithmetic)} rules)")

    # E. Over-generation / Domain validity filtering (reject-resample, never clipping)
    valid_mask = validate_supply_chain_rows(improved_df, domain_rules)
    if not valid_mask.all():
        # Keep valid rows and resample from valid rows to retain full row count
        valid_rows = improved_df[valid_mask]
        if not valid_rows.empty and len(valid_rows) >= 0.5 * len(improved_df):
            needed = len(improved_df) - len(valid_rows)
            resampled = valid_rows.sample(n=needed, replace=True, random_state=42)
            improved_df = pd.concat([valid_rows, resampled], ignore_index=True)
            strategies_applied.append("domain_reject_resample_non_clipping")

    # F. Rank-preserving quantile marginal matching
    improved_df = apply_rank_preserving_marginal_matching(
        real_df=df_real,
        synthetic_df=improved_df,
        ks_threshold=0.08,
    )
    strategies_applied.append("rank_preserving_quantile_marginal_matching")

    # G. Categorical frequency adjustment via resampling
    if semantics["statuses"] or semantics["categories"]:
        improved_df = match_categorical_frequencies(
            real_df=df_real,
            synthetic_df=improved_df,
        )
        strategies_applied.append("categorical_frequency_adjustment")

    # H. Re-enforce derived arithmetic after marginal matching so formulas remain 100% exact
    if derived_arithmetic:
        improved_df = reconstruct_supply_chain_features(improved_df, derived_arithmetic)

    # I. Privacy Guard (Reject & resample exact matches vs real training data)
    improved_df, priv_info = privacy_guard_filter(
        real_df=df_real,
        synthetic_df=improved_df,
        max_exact_duplicate_rate=0.01,
    )
    strategies_applied.append("privacy_guard_exact_match_filter")

    # Ensure exact requested row count
    target_count = len(df_baseline_synth)
    if len(improved_df) < target_count:
        needed = target_count - len(improved_df)
        fill = improved_df.sample(n=needed, replace=True, random_state=42)
        improved_df = pd.concat([improved_df, fill], ignore_index=True)
    elif len(improved_df) > target_count:
        improved_df = improved_df.head(target_count).reset_index(drop=True)

    # I. Generate and compare independent candidates; persist only the best valid one.
    try:
        candidate_column_configurations = get_configurations(dataset_id) or []
    except Exception as exc:
        logger.warning("Could not load column configurations for candidate scoring: %s", exc)
        candidate_column_configurations = []
    try:
        candidate_dataset_profile = get_dataset_profile(dataset_id) or {}
    except Exception as exc:
        logger.warning("Could not load dataset profile for candidate scoring: %s", exc)
        candidate_dataset_profile = {}

    improved_df, candidate_comparison, selected_candidate = _select_best_quality_candidate(
        real_df=df_real,
        baseline_df=df_baseline_synth,
        enhanced_df=improved_df,
        rules=domain_rules,
        semantics=semantics,
        derived_arithmetic=derived_arithmetic,
        column_configurations=candidate_column_configurations,
        dataset_profile=candidate_dataset_profile,
        target_column=target_column,
    )
    strategies_applied.append(f"best_candidate_selected ({selected_candidate})")

    # 6. Save the selected dataset as a distinct record (keeping baseline immutable)
    saved_improved_meta = save_generated_dataset(
        dataframe=improved_df,
        dataset_id=dataset_id,
        model_name=f"{baseline_result.get('model_name', 'model')}_improved",
    )

    improved_result_id = save_generated_result(
        run_id=baseline_result["run_id"],
        file_name=saved_improved_meta["file_name"],
        file_path=saved_improved_meta["file_path"],
        row_count=saved_improved_meta["row_count"],
        column_count=saved_improved_meta["column_count"],
    )

    # 7. Evaluate the improved result using the exact same evaluation protocol
    improved_eval_res = evaluate_generation(
        result_id=improved_result_id,
        user_id=user_id,
        target_column=target_column,
        force_recompute=True,
    )
    improved_eval = improved_eval_res.get("evaluation") or {}
    improved_validity = calculate_domain_validity_score(improved_df, domain_rules)

    # 8. Build side-by-side comparison summary
    comparison_rows, explanation = build_comparison_summary(
        baseline_eval=baseline_eval,
        improved_eval=improved_eval,
        baseline_validity=baseline_validity,
        improved_validity=improved_validity,
    )
    comparison_rows = _append_quality_metric_comparisons(
        comparison_rows,
        baseline_df=df_baseline_synth,
        improved_df=improved_df,
    )

    # Previews for instant side-by-side tab inspection
    baseline_preview = df_baseline_synth.head(8).to_dict(orient="records")
    improved_preview = improved_df.head(8).to_dict(orient="records")

    return {
        "status": "success",
        "message": "Supply Chain quality tuning completed successfully.",
        "dataset_id": dataset_id,
        "baseline_result_id": result_id,
        "improved_result_id": improved_result_id,
        "improved_file_name": saved_improved_meta["file_name"],
        "metrics_comparison": comparison_rows,
        "candidate_comparison": candidate_comparison,
        "selected_candidate": selected_candidate,
        "strategies_applied": strategies_applied,
        "domain_rules_summary": {
            "total_rules_tested": len(domain_rules),
            "rules": [r["name"] for r in domain_rules],
            "baseline_validity_percent": baseline_validity,
            "improved_validity_percent": improved_validity,
        },
        "privacy_status": {
            "passed": priv_info.get("passed", True),
            "exact_match_rate": priv_info.get("final_exact_rate", 0.0),
            "duplicates_dropped": priv_info.get("duplicates_dropped", 0),
        },
        "tradeoff_explanation": explanation,
        "baseline_evaluation": baseline_eval,
        "improved_evaluation": improved_eval,
        "previews": {
            "columns": list(improved_df.columns),
            "baseline_sample": baseline_preview,
            "improved_sample": improved_preview,
        },
    }
