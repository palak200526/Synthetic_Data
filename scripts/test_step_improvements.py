"""
Comparison test for Step 1, 2, 3 enhancements vs Baseline.
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
from backend.services.quality_enhancement_service import (
    detect_derived_features,
    apply_derived_features,
    apply_rank_preserving_marginal_matching,
    match_categorical_frequencies,
    privacy_guard_filter,
    enhance_synthetic_dataset,
    compute_correlation_error,
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
from backend.services.business_rule_detector import detect_arithmetic_relationships
from scripts.benchmark_quality import check_rule_validity


def evaluate_df_pair(df_real, synthetic_df, configurations, target_col, rules):
    stat_eval = evaluate_statistical_similarity(
        real_dataframe=df_real,
        synthetic_dataframe=synthetic_df,
        column_configurations=configurations,
        dataset_profile=None,
    )
    corr_eval = evaluate_correlation_covariance(
        real_dataframe=df_real,
        synthetic_dataframe=synthetic_df,
        column_configurations=configurations,
        dataset_profile=None,
    )
    ml_eval = evaluate_ml_utility(
        real_dataframe=df_real,
        synthetic_dataframe=synthetic_df,
        column_configurations=configurations,
        dataset_profile=None,
        target_column=target_col,
    ) if target_col else {"overall_score": None}

    privacy_eval = evaluate_privacy(
        real_dataframe=df_real,
        synthetic_dataframe=synthetic_df,
        column_configurations=configurations,
        dataset_profile=None,
        random_state=42,
    )
    validity_score = check_rule_validity(synthetic_df, rules)

    return {
        "statistical_similarity": stat_eval.get("overall_score"),
        "correlation_score": corr_eval.get("overall_score"),
        "correlation_error": corr_eval.get("mean_correlation_difference"),
        "ml_utility_score": ml_eval.get("overall_score"),
        "business_rule_validity": validity_score,
        "exact_match_rate": privacy_eval.get("exact_match_rate", 0.0),
        "dcr_ratio": privacy_eval.get("dcr_ratio", 1.0),
        "privacy_score": privacy_eval.get("overall_score"),
    }


def main():
    dataset_path = str(PROJECT_ROOT / "data" / "sample_supply_chain" / "purchase_orders.csv")
    df_raw = pd.read_csv(dataset_path)
    df_real = df_raw.sample(n=1000, random_state=42).reset_index(drop=True)

    derived_rules = detect_derived_features(df_real)
    print(f"Detected derived features: {derived_rules}")

    rules = detect_arithmetic_relationships(df_real)
    print(f"Arithmetic rules: {rules}")

    configurations = [
        {"column_name": col, "action": "keep"}
        for col in df_real.columns
    ]
    for cfg in configurations:
        if cfg["column_name"].lower().endswith("_id"):
            cfg["action"] = "new_id"

    ml_candidates = list_ml_target_candidates(df_real, df_real, configurations, None)
    target_col = ml_candidates[0]["column"] if ml_candidates else None

    # Load baseline
    with open(PROJECT_ROOT / "artifacts" / "quality_baseline.json") as f:
        baseline = json.load(f)["models"]

    print("\n" + "=" * 60)
    print("RUNNING QUALITY ENHANCED GENERATION")
    print("=" * 60)

    enhanced_results = {}

    for model_name in ["gaussian_copula", "ctgan", "tvae"]:
        print(f"\nEvaluating enhanced pipeline for: {model_name}")

        # Training preparation (Step 1)
        cols_to_drop = [c["column_name"] for c in configurations if c["action"] == "new_id"]
        # Drop derived target from training if detected
        derived_targets = [r["target"] for r in derived_rules]
        train_df = df_real.drop(columns=cols_to_drop + derived_targets, errors="ignore")

        gen_params = {"random_state": 42}
        if model_name in ("ctgan", "tvae"):
            gen_params["epochs"] = 20
            gen_params["batch_size"] = 100

        generator = get_generator(model_name, **gen_params)
        generator.fit(train_df)

        # Step 2: Over-generate 1.5x
        raw_synth = generator.generate(num_rows=int(len(df_real) * 1.5))

        # Re-attach dummy/sequential IDs
        for col in cols_to_drop:
            if col in df_real.columns:
                prefix = df_real[col].iloc[0][:3] if isinstance(df_real[col].iloc[0], str) else "ID"
                raw_synth[col] = [f"{prefix}{i:05d}" for i in range(len(raw_synth))]

        # Step 3: Apply full enhancement
        enhanced_synth, meta = enhance_synthetic_dataset(
            real_df=df_real,
            synthetic_df=raw_synth,
            derived_rules=derived_rules,
            apply_marginal_matching=True,
            apply_categorical_matching=True,
            apply_privacy_guard=True,
        )
        # Select target size (len(df_real))
        enhanced_synth = enhanced_synth.head(len(df_real)).reset_index(drop=True)

        res = evaluate_df_pair(df_real, enhanced_synth, configurations, target_col, rules)
        enhanced_results[model_name] = res

    print("\n" + "=" * 80)
    print("COMPARISON: BASELINE vs ENHANCED")
    print("=" * 80)
    for model_name in ["gaussian_copula", "ctgan", "tvae"]:
        print(f"\n--- Model: {model_name} ---")
        b = baseline[model_name]
        e = enhanced_results[model_name]
        metrics = [
            "statistical_similarity",
            "correlation_score",
            "correlation_error",
            "ml_utility_score",
            "business_rule_validity",
            "exact_match_rate",
            "dcr_ratio",
            "privacy_score",
        ]
        print(f"{'Metric':<28} | {'Baseline':<12} | {'Enhanced':<12} | {'Change':<10}")
        print("-" * 70)
        for m in metrics:
            b_val = b.get(m, 0.0)
            e_val = e.get(m, 0.0)
            diff = (e_val - b_val) if (b_val is not None and e_val is not None) else 0.0
            diff_str = f"{diff:+.2f}" if isinstance(diff, (int, float)) else "N/A"
            print(f"{m:<28} | {str(b_val):<12} | {str(e_val):<12} | {diff_str:<10}")

    # Save enhanced results
    out_file = PROJECT_ROOT / "artifacts" / "quality_enhanced.json"
    with open(out_file, "w") as f:
        json.dump(enhanced_results, f, indent=2)
    print(f"\nSaved enhanced comparison to {out_file}")


if __name__ == "__main__":
    main()
