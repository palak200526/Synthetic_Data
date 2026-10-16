from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.services.statistical_evaluation_service import (
    determine_column_eligibility,
)

logger = logging.getLogger(__name__)

MAX_SYNTH_SAMPLE = 500
MAX_REAL_SAMPLE = 2000


def _gower_min_distances(
    query: pd.DataFrame,
    reference: pd.DataFrame,
    numeric_cols: list[str],
    cat_cols: list[str],
    ranges: dict[str, float],
    exclude_self: bool = False,
) -> np.ndarray:
    """Distance from every query row to its closest reference row (Gower)."""
    n_q, n_r = len(query), len(reference)
    total = np.zeros((n_q, n_r), dtype=float)
    n_feat = len(numeric_cols) + len(cat_cols)
    for c in numeric_cols:
        q = pd.to_numeric(query[c], errors="coerce").to_numpy(dtype=float)
        r = pd.to_numeric(reference[c], errors="coerce").to_numpy(dtype=float)
        q = np.nan_to_num(q, nan=np.nanmedian(r) if np.isfinite(r).any() else 0.0)
        r = np.nan_to_num(r, nan=np.nanmedian(r) if np.isfinite(r).any() else 0.0)
        total += np.minimum(np.abs(q[:, None] - r[None, :]) / ranges[c], 1.0)
    for c in cat_cols:
        q = query[c].astype(str).to_numpy()
        r = reference[c].astype(str).to_numpy()
        total += (q[:, None] != r[None, :]).astype(float)
    total /= max(n_feat, 1)
    if exclude_self:
        np.fill_diagonal(total, np.inf)
    return total.min(axis=1)


def evaluate_privacy(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    column_configurations: list[dict] | None = None,
    dataset_profile: dict | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Privacy risk of the synthetic data:
    - exact_match_rate : share of synthetic rows copied verbatim from real rows
    - DCR (distance to closest real record) vs. the real data's own
      nearest-neighbour distance. Synthetic rows much closer to real rows than
      real rows are to each other indicate memorisation / leakage.
    """
    config_map = {
        c["column_name"]: c
        for c in (column_configurations or [])
        if isinstance(c, dict) and "column_name" in c
    }
    profile_map: dict = {}
    if isinstance(dataset_profile, dict):
        info = dataset_profile.get("column_information") or dataset_profile.get("columns") or []
        if isinstance(info, list):
            profile_map = {
                p["column_name"]: p
                for p in info
                if isinstance(p, dict) and "column_name" in p
            }
        elif isinstance(info, dict):
            profile_map = info

    common = [c for c in real_dataframe.columns if c in synthetic_dataframe.columns]
    numeric_cols: list[str] = []
    cat_cols: list[str] = []
    for col in common:
        status, _, col_type = determine_column_eligibility(
            column_name=col,
            real_series=real_dataframe[col],
            configuration=config_map.get(col),
            profile_column=profile_map.get(col),
        )
        if status != "evaluated":
            continue
        if col_type == "numerical":
            numeric_cols.append(col)
        elif col_type == "categorical":
            cat_cols.append(col)

    cols = numeric_cols + cat_cols
    if not cols or len(real_dataframe) < 5 or len(synthetic_dataframe) < 5:
        return {
            "metric": "privacy",
            "status": "not_applicable",
            "reason": "Not enough comparable columns/rows for a privacy check.",
            "overall_score": None,
            "risk_level": None,
        }

    real = real_dataframe[cols].reset_index(drop=True)
    synth = synthetic_dataframe[cols].reset_index(drop=True)

    # --- exact matches (full row, over comparable columns) ---
    real_keys = set(map(tuple, real.astype(str).to_numpy()))
    synth_keys = list(map(tuple, synth.astype(str).to_numpy()))
    exact_rate = sum(k in real_keys for k in synth_keys) / len(synth_keys)

    # --- DCR ---
    synth_s = synth.sample(min(MAX_SYNTH_SAMPLE, len(synth)), random_state=random_state)
    real_s = real.sample(min(MAX_REAL_SAMPLE, len(real)), random_state=random_state)
    ranges = {}
    for c in numeric_cols:
        vals = pd.to_numeric(real[c], errors="coerce")
        rng = float(vals.max() - vals.min())
        ranges[c] = rng if rng > 1e-12 else 1.0

    dcr_synth = _gower_min_distances(synth_s, real_s, numeric_cols, cat_cols, ranges)
    probe = real_s.head(min(MAX_SYNTH_SAMPLE, len(real_s)))
    dcr_real = _gower_min_distances(
        probe, real_s, numeric_cols, cat_cols, ranges, exclude_self=True
    )

    med_s = float(np.median(dcr_synth))
    med_r = float(np.median(dcr_real))
    ratio = med_s / med_r if med_r > 1e-12 else (1.0 if med_s > 1e-12 else 0.0)

    exact_score = (1.0 - exact_rate) * 100.0
    dcr_score = min(1.0, ratio) * 100.0
    score = round(0.5 * exact_score + 0.5 * dcr_score, 2)

    if exact_rate > 0.05 or ratio < 0.5:
        risk = "HIGH"
    elif exact_rate > 0.01 or ratio < 0.8:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "metric": "privacy",
        "status": "evaluated",
        "overall_score": score,
        "risk_level": risk,
        "exact_match_rate": round(exact_rate, 4),
        "dcr_median": round(med_s, 4),
        "dcr_baseline_median": round(med_r, 4),
        "dcr_ratio": round(ratio, 4),
        "dcr_score": round(dcr_score, 2),
        "evaluated_columns": cols,
        "sampled_synthetic_rows": int(len(synth_s)),
    }