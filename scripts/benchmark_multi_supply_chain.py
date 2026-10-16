"""
Evaluation script benchmarking baseline vs improved across multiple Supply Chain datasets:
1. purchase_orders.csv (reference benchmark)
2. inventory.csv (inventory balance & reorder points)
3. shipments.csv (chronological dates & lead times)
"""

import os
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.generation.generator_factory import get_generator
from backend.services.supply_chain_domain_service import (
    detect_supply_chain_semantics,
    infer_and_validate_domain_rules,
    calculate_domain_validity_score,
    reconstruct_supply_chain_features,
    validate_supply_chain_rows,
)
from backend.services.quality_enhancement_service import (
    apply_rank_preserving_marginal_matching,
    match_categorical_frequencies,
    privacy_guard_filter,
)
from backend.services.statistical_evaluation_service import (
    evaluate_statistical_similarity,
)
from backend.services.correlation_evaluation_service import (
    evaluate_correlation_covariance,
)
from backend.services.ml_utility_service import (
    evaluate_ml_utility,
    list_ml_target_candidates,
)
from backend.services.privacy_evaluation_service import evaluate_privacy


def evaluate_dataset_pair(df_real, df_synth, configurations, target_col, rules):
    stat = evaluate_statistical_similarity(
        real_dataframe=df_real,
        synthetic_dataframe=df_synth,
        column_configurations=configurations,
        dataset_profile=None,
    )
    corr = evaluate_correlation_covariance(
        real_dataframe=df_real,
        synthetic_dataframe=df_synth,
        column_configurations=configurations,
        dataset_profile=None,
    )
    ml = evaluate_ml_utility(
        real_dataframe=df_real,
        synthetic_dataframe=df_synth,
        column_configurations=configurations,
        dataset_profile=None,
        target_column=target_col,
    ) if target_col else {"overall_score": None}

    priv = evaluate_privacy(
        real_dataframe=df_real,
        synthetic_dataframe=df_synth,
        column_configurations=configurations,
        dataset_profile=None,
        random_state=42,
    )
    validity = calculate_domain_validity_score(df_synth, rules)

    return {
        "statistical_similarity": stat.get("overall_score"),
        "correlation_score": corr.get("overall_score"),
        "correlation_error": corr.get("mean_correlation_difference"),
        "ml_utility_score": ml.get("overall_score"),
        "business_rule_validity": validity,
        "exact_match_rate": priv.get("exact_match_rate", 0.0),
        "dcr_ratio": priv.get("dcr_ratio", 1.0),
        "privacy_score": priv.get("overall_score"),
    }


def benchmark_single_dataset(file_path: str, model_name: str = "gaussian_copula", sample_size: int = 500):
    df_raw = pd.read_csv(file_path)
    if len(df_raw) > sample_size:
        df_real = df_raw.sample(n=sample_size, random_state=42).reset_index(drop=True)
    else:
        df_real = df_raw.copy().reset_index(drop=True)

    filename = os.path.basename(file_path)
    print(f"\n=======================================================")
    print(f"BENCHMARKING: {filename} ({len(df_real)} rows, {len(df_real.columns)} cols)")
    print(f"=======================================================")

    # 1. Semantics and domain rules
    semantics = detect_supply_chain_semantics(df_real)
    domain_rules = infer_and_validate_domain_rules(df_real, semantics)
    print(f"Inferred & Confirmed {len(domain_rules)} domain rules: {[r['name'] for r in domain_rules]}")

    configurations = [{"column_name": c, "action": "keep"} for c in df_real.columns]
    for c in configurations:
        if c["column_name"] in semantics["identifiers"]:
            c["action"] = "new_id"

    ml_cands = list_ml_target_candidates(df_real, df_real, configurations, None)
    target_col = ml_cands[0]["column"] if ml_cands else None
    print(f"ML Utility target column: {target_col}")

    # 2. BASELINE GENERATION
    train_cols = [c["column_name"] for c in configurations if c["action"] != "new_id"]
    train_df = df_real[train_cols]

    generator = get_generator(model_name, random_state=42)
    generator.fit(train_df)
    baseline_synth = generator.generate(num_rows=len(df_real))

    # Add id columns back
    for col in semantics["identifiers"]:
        if col in df_real.columns:
            prefix = str(df_real[col].iloc[0])[:3]
            baseline_synth[col] = [f"{prefix}{i:05d}" for i in range(len(baseline_synth))]

    baseline_metrics = evaluate_dataset_pair(df_real, baseline_synth, configurations, target_col, domain_rules)

    # 3. IMPROVED GENERATION
    improved_synth = baseline_synth.copy()

    # Reconstruct derived arithmetic
    derived_arithmetic = [r for r in domain_rules if r.get("rule_type") == "arithmetic"]
    if derived_arithmetic:
        improved_synth = reconstruct_supply_chain_features(improved_synth, derived_arithmetic)

    # Over-generation reject-resample validity
    valid_mask = validate_supply_chain_rows(improved_synth, domain_rules)
    if not valid_mask.all():
        valid_rows = improved_synth[valid_mask]
        if not valid_rows.empty:
            needed = len(improved_synth) - len(valid_rows)
            resampled = valid_rows.sample(n=needed, replace=True, random_state=42)
            improved_synth = pd.concat([valid_rows, resampled], ignore_index=True)

    # Quantile marginal matching
    improved_synth = apply_rank_preserving_marginal_matching(df_real, improved_synth, ks_threshold=0.08)

    # Re-apply derived arithmetic
    if derived_arithmetic:
        improved_synth = reconstruct_supply_chain_features(improved_synth, derived_arithmetic)

    # Categorical matching
    if semantics["statuses"] or semantics["categories"]:
        improved_synth = match_categorical_frequencies(df_real, improved_synth)

    # Privacy guard
    improved_synth, _ = privacy_guard_filter(df_real, improved_synth, max_exact_duplicate_rate=0.01)

    improved_metrics = evaluate_dataset_pair(df_real, improved_synth, configurations, target_col, domain_rules)

    # Output comparison
    print(f"\nResults for {filename}:")
    print(f"{'Metric':<28} | {'Baseline':<10} | {'Improved':<10} | {'Change':<10}")
    print("-" * 65)
    metrics_to_show = [
        "statistical_similarity",
        "correlation_score",
        "correlation_error",
        "ml_utility_score",
        "business_rule_validity",
        "exact_match_rate",
        "privacy_score",
    ]
    for m in metrics_to_show:
        b_val = baseline_metrics.get(m, 0.0)
        i_val = improved_metrics.get(m, 0.0)
        diff = (i_val - b_val) if (b_val is not None and i_val is not None) else 0.0
        diff_str = f"{diff:+.2f}" if isinstance(diff, (int, float)) else "N/A"
        print(f"{m:<28} | {str(b_val):<10} | {str(i_val):<10} | {diff_str:<10}")

    return {
        "dataset": filename,
        "baseline": baseline_metrics,
        "improved": improved_metrics,
        "rules_count": len(domain_rules),
    }


def main():
    datasets = [
        str(PROJECT_ROOT / "data" / "sample_supply_chain" / "purchase_orders.csv"),
        str(PROJECT_ROOT / "data" / "sample_supply_chain" / "inventory.csv"),
        str(PROJECT_ROOT / "data" / "sample_supply_chain" / "shipments.csv"),
    ]

    all_results = {}
    for dpath in datasets:
        if os.path.exists(dpath):
            res = benchmark_single_dataset(dpath)
            all_results[res["dataset"]] = res

    out_file = PROJECT_ROOT / "artifacts" / "multi_supply_chain_benchmark.json"
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll benchmark results saved to: {out_file}")


if __name__ == "__main__":
    main()
