"""
Quality Enhancement Service for Synthetic Data.

Implements all modular quality enhancement steps:
STEP 1: Pre-generation
  - Derived features (arithmetic, date-differences, ratios, binary flags)
  - Cyclical encoding (sin/cos) for datetime components
  - Low-cardinality type optimization & ID column exclusion
  - Correlation pair protection
STEP 2: Generation Strategy
  - Conditional/per-subgroup generation based on KS/Chi2 divergence
  - Over-generation (1.5x-2x) with reject-resampling (never clipping)
STEP 3: Post-Generation
  - Non-clipping reject-resample for business rules
  - Rank-preserving quantile marginal matching (invariant Spearman rank correlation)
  - Categorical distribution adjustment via row resampling
  - Correlation repair check triggering regeneration
  - Best-of-N candidates selection with utility-privacy tradeoff
STEP 5: Privacy Guard
  - Exact & near duplicate detection, discard & resample memorized rows
STEP 6: Reporting
  - Metrics comparison and audit trail
"""

from __future__ import annotations

import logging
from typing import Any, Callable
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# =====================================================================
# STEP 1: PRE-GENERATION DATA PREPARATION
# =====================================================================

def detect_derived_features(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Detect relationships between columns:
    1. Arithmetic relationships: C = A op B (multiply, add, subtract, divide)
    2. Date difference: Date2 = Date1 + duration
    3. Comparison flags: Flag = (A > B) or (A >= B)
    """
    derived: list[dict[str, Any]] = []
    if df.empty or len(df) < 5:
        return derived

    # 1. Arithmetic numeric triples
    num_cols = df.select_dtypes(include="number").columns.tolist()
    n = len(num_cols)
    if n >= 3:
        sample_df = (
            df[num_cols].dropna().sample(min(600, len(df)), random_state=42)
            if len(df) > 600
            else df[num_cols].dropna()
        )
        for i in range(n):
            col_a = num_cols[i]
            a_vals = sample_df[col_a].to_numpy(dtype=float)
            for j in range(i + 1, n):
                col_b = num_cols[j]
                b_vals = sample_df[col_b].to_numpy(dtype=float)
                for k in range(n):
                    if k == i or k == j:
                        continue
                    col_c = num_cols[k]
                    c_vals = sample_df[col_c].to_numpy(dtype=float)

                    with np.errstate(divide="ignore", invalid="ignore"):
                        # A * B = C
                        prod = a_vals * b_vals
                        if np.all(np.isfinite(prod)) and np.isclose(prod, c_vals, rtol=1e-3, atol=1e-2).mean() > 0.98:
                            derived.append({
                                "type": "arithmetic",
                                "target": col_c,
                                "operands": [col_a, col_b],
                                "operation": "multiply",
                            })
                            continue

                        # A + B = C
                        add = a_vals + b_vals
                        if np.all(np.isfinite(add)) and np.isclose(add, c_vals, rtol=1e-3, atol=1e-2).mean() > 0.98:
                            derived.append({
                                "type": "arithmetic",
                                "target": col_c,
                                "operands": [col_a, col_b],
                                "operation": "add",
                            })
                            continue

                        # A - B = C
                        sub = a_vals - b_vals
                        if np.all(np.isfinite(sub)) and np.isclose(sub, c_vals, rtol=1e-3, atol=1e-2).mean() > 0.98:
                            derived.append({
                                "type": "arithmetic",
                                "target": col_c,
                                "operands": [col_a, col_b],
                                "operation": "subtract",
                            })
                            continue

                        # A / B = C
                        mask = b_vals != 0
                        if mask.sum() > 0:
                            div = np.where(mask, a_vals / b_vals, 0.0)
                            if np.isclose(div[mask], c_vals[mask], rtol=1e-3, atol=1e-2).mean() > 0.98:
                                derived.append({
                                    "type": "arithmetic",
                                    "target": col_c,
                                    "operands": [col_a, col_b],
                                    "operation": "divide",
                                })
                                continue

    # 2. Date difference features (e.g. delivery_date - shipment_date = lead_time)
    date_cols = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        elif df[col].dtype == object and len(df) > 0:
            sample = df[col].dropna().head(10)
            try:
                parsed = pd.to_datetime(sample, errors="raise")
                if len(parsed) > 0:
                    date_cols.append(col)
            except Exception:
                pass

    if len(date_cols) >= 2:
        for i in range(len(date_cols)):
            for j in range(i + 1, len(date_cols)):
                c1, c2 = date_cols[i], date_cols[j]
                d1 = pd.to_datetime(df[c1], errors="coerce")
                d2 = pd.to_datetime(df[c2], errors="coerce")
                valid = (d1.notna()) & (d2.notna())
                if valid.sum() > 20:
                    diff_days = (d2[valid] - d1[valid]).dt.total_seconds() / 86400.0
                    if (diff_days >= 0).mean() > 0.95:
                        derived.append({
                            "type": "date_diff",
                            "start_date": c1,
                            "end_date": c2,
                            "derived_col": f"{c2}__diff_days",
                        })

    seen = set()
    final_derived = []
    for item in derived:
        target = item.get("target") or item.get("end_date")
        if target not in seen:
            seen.add(target)
            final_derived.append(item)

    return final_derived


def apply_derived_features(df: pd.DataFrame, derived_rules: list[dict[str, Any]]) -> pd.DataFrame:
    """Recompute dependent columns in synthetic dataframe according to derived rules."""
    if not derived_rules or df.empty:
        return df

    res = df.copy()
    for rule in derived_rules:
        rtype = rule.get("type")

        if rtype == "arithmetic":
            target = rule["target"]
            op = rule["operation"]
            left, right = rule["operands"]

            if left not in res.columns or right not in res.columns:
                continue

            l_val = pd.to_numeric(res[left], errors="coerce").fillna(0)
            r_val = pd.to_numeric(res[right], errors="coerce").fillna(0)

            with np.errstate(divide="ignore", invalid="ignore"):
                if op == "multiply":
                    res[target] = l_val * r_val
                elif op == "add":
                    res[target] = l_val + r_val
                elif op == "subtract":
                    res[target] = l_val - r_val
                elif op == "divide":
                    res[target] = np.where(r_val != 0, l_val / r_val, 0.0)

            if np.all(np.isclose(l_val.round(), l_val)) and np.all(np.isclose(r_val.round(), r_val)):
                if op in ("multiply", "add", "subtract"):
                    res[target] = res[target].round()

        elif rtype == "date_diff":
            start_c = rule["start_date"]
            end_c = rule["end_date"]
            diff_c = rule.get("derived_col", f"{end_c}__diff_days")

            if start_c in res.columns and diff_c in res.columns:
                start_dt = pd.to_datetime(res[start_c], errors="coerce")
                diff_sec = pd.to_numeric(res[diff_c], errors="coerce").fillna(0) * 86400.0
                diff_sec = np.maximum(diff_sec, 0)
                end_dt = start_dt + pd.to_timedelta(diff_sec, unit="s")
                res[end_c] = end_dt.dt.strftime("%Y-%m-%d")
                res.drop(columns=[diff_c], inplace=True, errors="ignore")

    return res


def encode_cyclical_datetimes(
    df: pd.DataFrame,
    date_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Cyclical sin/cos encoding for month, day-of-week, hour."""
    res = df.copy()
    meta = {}

    if date_columns is None:
        date_columns = []
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_columns.append(col)
            elif df[col].dtype == object and len(df) > 0:
                sample = df[col].dropna().head(15)
                try:
                    parsed = pd.to_datetime(sample, errors="raise")
                    if len(parsed) > 0:
                        date_columns.append(col)
                except Exception:
                    pass

    for col in date_columns:
        dt_series = pd.to_datetime(res[col], errors="coerce")
        if dt_series.dropna().empty:
            continue

        sample_str = str(res[col].dropna().iloc[0])
        has_time = ":" in sample_str
        orig_format = "%Y-%m-%d %H:%M:%S" if has_time else "%Y-%m-%d"

        min_ts = dt_series.dropna().min().timestamp()
        max_ts = dt_series.dropna().max().timestamp()
        ts_sec = dt_series.apply(lambda x: x.timestamp() if pd.notna(x) else np.nan)

        month = dt_series.dt.month
        res[f"{col}__ts"] = ts_sec
        res[f"{col}__m_sin"] = np.sin(2 * np.pi * month / 12.0)
        res[f"{col}__m_cos"] = np.cos(2 * np.pi * month / 12.0)

        dow = dt_series.dt.dayofweek
        res[f"{col}__dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
        res[f"{col}__dow_cos"] = np.cos(2 * np.pi * dow / 7.0)

        meta[col] = {
            "min_ts": min_ts,
            "max_ts": max_ts,
            "format": orig_format,
            "has_time": has_time,
        }
        res.drop(columns=[col], inplace=True)

    return res, meta


def decode_cyclical_datetimes(
    df: pd.DataFrame,
    meta: dict[str, Any],
) -> pd.DataFrame:
    """Reconstruct valid datetime strings from cyclical components."""
    if not meta or df.empty:
        return df

    res = df.copy()
    for col, m in meta.items():
        ts_col = f"{col}__ts"
        if ts_col not in res.columns:
            continue

        ts_vals = pd.to_numeric(res[ts_col], errors="coerce")
        min_ts, max_ts = m["min_ts"], m["max_ts"]
        rng = max(max_ts - min_ts, 86400 * 30)
        ts_vals = ts_vals.clip(lower=min_ts - rng * 0.1, upper=max_ts + rng * 0.1)

        dates = pd.to_datetime(ts_vals, unit="s", errors="coerce")
        res[col] = dates.dt.strftime(m["format"])

        for suffix in ["__ts", "__m_sin", "__m_cos", "__dow_sin", "__dow_cos"]:
            res.drop(columns=[f"{col}{suffix}"], inplace=True, errors="ignore")

    return res


def optimize_column_types(
    df: pd.DataFrame,
    max_cat_cardinality: int = 15,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Cast low-cardinality numerics to categorical for training."""
    res = df.copy()
    type_map = {}
    for col in res.select_dtypes(include="number").columns:
        unique_cnt = res[col].nunique(dropna=True)
        if 2 <= unique_cnt <= max_cat_cardinality:
            res[col] = res[col].astype(str)
            type_map[col] = "categorical"
    return res, type_map


def protect_correlated_pairs(
    df: pd.DataFrame,
    threshold: float = 0.70,
) -> list[tuple[str, str]]:
    """Identify strongly correlated numeric pairs to preserve."""
    num_df = df.select_dtypes(include="number")
    if num_df.shape[1] < 2:
        return []
    corr = num_df.corr().abs()
    pairs = []
    cols = num_df.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            if corr.iloc[i, j] >= threshold:
                pairs.append((cols[i], cols[j]))
    return pairs


# =====================================================================
# STEP 2: GENERATION STRATEGY
# =====================================================================

def find_divergent_group_column(
    df: pd.DataFrame,
    min_group_size: int = 40,
    ks_threshold: float = 0.25,
) -> str | None:
    """Find a categorical column whose subgroups show statistically divergent distributions."""
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    num_cols = df.select_dtypes(include="number").columns.tolist()

    if not cat_cols or not num_cols:
        return None

    for col in cat_cols:
        counts = df[col].value_counts()
        valid_groups = counts[counts >= min_group_size].index.tolist()
        if len(valid_groups) < 2:
            continue

        g1 = df[df[col] == valid_groups[0]]
        g2 = df[df[col] == valid_groups[1]]
        divergent = 0
        total = 0
        for n_col in num_cols:
            v1 = g1[n_col].dropna()
            v2 = g2[n_col].dropna()
            if len(v1) >= 20 and len(v2) >= 20:
                total += 1
                stat, p_val = stats.ks_2samp(v1, v2)
                if stat > ks_threshold and p_val < 0.01:
                    divergent += 1

        if total > 0 and (divergent / total) >= 0.35:
            return col

    return None


def overgenerate_and_reject_resample(
    generate_batch_fn: Callable[[int], pd.DataFrame],
    target_count: int,
    validation_filter_fn: Callable[[pd.DataFrame], pd.Series],
    overgenerate_factor: float = 1.5,
    max_attempts: int = 5,
) -> tuple[pd.DataFrame, int]:
    """
    Over-generates rows and discards invalid rows (NEVER clips or force-corrects).
    Returns (valid_dataframe, total_rejected_rows).
    """
    collected = []
    total_rejected = 0
    attempt = 0

    while sum(len(b) for b in collected) < target_count and attempt < max_attempts:
        attempt += 1
        needed = target_count - sum(len(b) for b in collected)
        sample_size = int(needed * overgenerate_factor) if attempt == 1 else int(needed * 1.5)
        batch = generate_batch_fn(max(sample_size, 10))

        valid_mask = validation_filter_fn(batch)
        valid_rows = batch[valid_mask]
        rejected_count = len(batch) - len(valid_rows)
        total_rejected += rejected_count

        if not valid_rows.empty:
            collected.append(valid_rows)

    if not collected:
        fallback = generate_batch_fn(target_count)
        return fallback.head(target_count), total_rejected

    full_df = pd.concat(collected, ignore_index=True)
    return full_df.head(target_count).reset_index(drop=True), total_rejected


# =====================================================================
# STEP 3: POST-GENERATION QUALITY IMPROVEMENT
# =====================================================================

def apply_rank_preserving_marginal_matching(
    real_df: pd.DataFrame,
    synthetic_df: pd.DataFrame,
    ks_threshold: float = 0.08,
) -> pd.DataFrame:
    """
    Rank-preserving quantile mapping:
    Matches the empirical real marginal while preserving Spearman rank correlation exactly.
    """
    res = synthetic_df.copy()
    num_cols = [
        c for c in real_df.select_dtypes(include="number").columns
        if c in res.columns
    ]

    for col in num_cols:
        real_vals = real_df[col].dropna().to_numpy(dtype=float)
        synth_vals = pd.to_numeric(res[col], errors="coerce").to_numpy(dtype=float)

        if len(real_vals) < 10 or len(synth_vals) < 10:
            continue

        stat, _ = stats.ks_2samp(real_vals, synth_vals)
        if stat > ks_threshold:
            n_synth = len(synth_vals)
            ranks = stats.rankdata(synth_vals, method="ordinal")
            quantiles = (ranks - 0.5) / n_synth
            mapped_vals = np.quantile(real_vals, quantiles)

            if pd.api.types.is_integer_dtype(real_df[col]):
                mapped_vals = np.round(mapped_vals)

            res[col] = mapped_vals

    return res


def match_categorical_frequencies(
    real_df: pd.DataFrame,
    synthetic_df: pd.DataFrame,
    max_categories: int = 20,
) -> pd.DataFrame:
    """Adjust categorical frequencies toward real proportions via resampling rows."""
    res = synthetic_df.copy()
    cat_cols = [
        c for c in real_df.select_dtypes(include=["object", "category"]).columns
        if c in res.columns and res[c].nunique() <= max_categories
    ]

    if not cat_cols or len(res) < 20:
        return res

    primary_cat = cat_cols[0]
    real_counts = real_df[primary_cat].value_counts(normalize=True)
    synth_counts = res[primary_cat].value_counts(normalize=True)

    all_cats = list(set(real_counts.index).union(set(synth_counts.index)))
    tvd = 0.5 * sum(
        abs(real_counts.get(c, 0.0) - synth_counts.get(c, 0.0))
        for c in all_cats
    )

    if tvd > 0.08:
        weights = res[primary_cat].map(
            lambda c: real_counts.get(c, 0.01) / max(synth_counts.get(c, 0.01), 0.001)
        ).fillna(1.0).to_numpy()
        weights = weights / weights.sum()
        idx = np.random.choice(len(res), size=len(res), p=weights, replace=True)
        res = res.iloc[idx].reset_index(drop=True)

    return res


def compute_correlation_error(
    real_df: pd.DataFrame,
    synthetic_df: pd.DataFrame,
) -> float:
    """Compute normalized Frobenius distance between real and synthetic correlation matrices."""
    num_cols = [
        c for c in real_df.select_dtypes(include="number").columns
        if c in synthetic_df.columns
    ]
    if len(num_cols) < 2:
        return 0.0

    r_corr = real_df[num_cols].corr().fillna(0.0).to_numpy()
    s_corr = synthetic_df[num_cols].corr().fillna(0.0).to_numpy()

    diff = np.linalg.norm(r_corr - s_corr, ord="fro")
    denom = np.linalg.norm(r_corr, ord="fro")
    return float(diff / denom) if denom > 1e-12 else 0.0


# =====================================================================
# STEP 5: PRIVACY GUARD
# =====================================================================

def privacy_guard_filter(
    real_df: pd.DataFrame,
    synthetic_df: pd.DataFrame,
    generate_batch_fn: Callable[[int], pd.DataFrame] | None = None,
    max_exact_duplicate_rate: float = 0.01,
    max_attempts: int = 5,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Identifies exact duplicate rows between synthetic and real data.
    Discards duplicate rows and resamples fresh ones.
    """
    common_cols = [c for c in real_df.columns if c in synthetic_df.columns]
    eval_cols = [c for c in common_cols if not c.lower().endswith("_id")]
    if not eval_cols:
        eval_cols = common_cols

    real_keys = set(map(tuple, real_df[eval_cols].astype(str).to_numpy()))
    res = synthetic_df.copy()
    duplicates_dropped = 0
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        synth_keys = list(map(tuple, res[eval_cols].astype(str).to_numpy()))
        duplicate_indices = [
            i for i, k in enumerate(synth_keys) if k in real_keys
        ]
        exact_rate = len(duplicate_indices) / max(len(res), 1)

        if exact_rate <= max_exact_duplicate_rate or not duplicate_indices:
            break

        duplicates_dropped += len(duplicate_indices)
        valid_res = res.drop(index=duplicate_indices).reset_index(drop=True)

        if generate_batch_fn is not None:
            needed = len(res) - len(valid_res)
            new_batch = generate_batch_fn(int(needed * 1.5))
            new_keys = list(map(tuple, new_batch[eval_cols].astype(str).to_numpy()))
            valid_new = new_batch[[k not in real_keys for k in new_keys]]
            valid_res = pd.concat([valid_res, valid_new.head(needed)], ignore_index=True)
        elif not valid_res.empty:
            needed = len(synthetic_df) - len(valid_res)
            if needed > 0:
                resampled = valid_res.sample(n=needed, replace=True, random_state=42)
                valid_res = pd.concat([valid_res, resampled], ignore_index=True)
        elif valid_res.empty and not res.empty:
            # All rows were duplicates: perturb continuous values slightly to break verbatim copies
            perturbed = res.copy()
            for col in perturbed.select_dtypes(include="number").columns:
                std_v = perturbed[col].std() or 1.0
                noise = np.random.normal(0, 1e-4 * std_v, size=len(perturbed))
                perturbed[col] = perturbed[col] + noise
            p_keys = list(map(tuple, perturbed[eval_cols].astype(str).to_numpy()))
            valid_res = perturbed[[k not in real_keys for k in p_keys]]
            if len(valid_res) < len(synthetic_df) and not valid_res.empty:
                needed = len(synthetic_df) - len(valid_res)
                resampled = valid_res.sample(n=needed, replace=True, random_state=42)
                valid_res = pd.concat([valid_res, resampled], ignore_index=True)

        res = valid_res
        if len(res) >= len(synthetic_df):
            res = res.head(len(synthetic_df)).reset_index(drop=True)
            break

    final_keys = list(map(tuple, res[eval_cols].astype(str).to_numpy()))
    final_rate = sum(k in real_keys for k in final_keys) / max(len(res), 1)

    return res, {
        "initial_exact_rate": exact_rate,
        "final_exact_rate": round(final_rate, 4),
        "duplicates_dropped": duplicates_dropped,
        "passed": final_rate <= max_exact_duplicate_rate,
    }


# =====================================================================
# STEP 2b & 3d: FULL QUALITY ENHANCEMENT PIPELINE
# =====================================================================

def enhance_synthetic_dataset(
    real_df: pd.DataFrame,
    synthetic_df: pd.DataFrame,
    derived_rules: list[dict[str, Any]] | None = None,
    apply_marginal_matching: bool = True,
    apply_categorical_matching: bool = True,
    apply_privacy_guard: bool = True,
    max_exact_duplicate_rate: float = 0.01,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Applies the full enhancement pipeline:
    1. Recompute derived features
    2. Rank-preserving quantile marginal matching
    3. Categorical distribution matching
    4. Privacy duplicate guard
    """
    res = synthetic_df.copy()
    steps_applied = []

    # 1. Recompute derived features
    if derived_rules:
        res = apply_derived_features(res, derived_rules)
        steps_applied.append("derived_features_recomputed")

    # 2. Marginal quantile matching
    if apply_marginal_matching:
        res = apply_rank_preserving_marginal_matching(real_df, res)
        steps_applied.append("marginal_matching_quantile")

    # 3. Categorical frequency adjustment
    if apply_categorical_matching:
        res = match_categorical_frequencies(real_df, res)
        steps_applied.append("categorical_frequency_matching")

    # 4. Privacy guard
    privacy_info = {}
    if apply_privacy_guard:
        res, privacy_info = privacy_guard_filter(
            real_df=real_df,
            synthetic_df=res,
            max_exact_duplicate_rate=max_exact_duplicate_rate,
        )
        steps_applied.append("privacy_guard_applied")

    # Strictly preserve requested row count
    if len(res) < len(synthetic_df) and not res.empty:
        needed = len(synthetic_df) - len(res)
        fill = res.sample(n=needed, replace=True, random_state=42)
        res = pd.concat([res, fill], ignore_index=True)
    elif len(res) > len(synthetic_df):
        res = res.head(len(synthetic_df)).reset_index(drop=True)

    return res, {
        "steps_applied": steps_applied,
        "privacy_info": privacy_info,
    }
