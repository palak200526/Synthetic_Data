"""
Benchmark baseline script for Synthetic_Data_Project.
Evaluates algorithms (Gaussian Copula, CTGAN, TVAE) on sample supply chain data.
Computes:
- Statistical similarity (KS / distribution similarity)
- Correlation error (Frobenius / mean abs difference)
- ML utility (synthetic-train / real-test accuracy/R2)
- Business-rule validity (% rows satisfying arithmetic rules)
- Privacy (exact-match rate & DCR ratio)
"""

import os
import sys
import json
import logging
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.generation.generator_factory import get_generator
from backend.services.business_rule_detector import (
    detect_arithmetic_relationships,
    apply_business_rules,
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")


def check_rule_validity(df: pd.DataFrame, rules: list) -> float:
    """Calculate the percentage of rows that satisfy all arithmetic business rules."""
    if not rules or df.empty:
        return 100.0

    valid_mask = pd.Series(True, index=df.index)
    for rule in rules:
        target = rule["target"]
        op = rule["operation"]
        left, right = rule["operands"]
        if target not in df.columns or left not in df.columns or right not in df.columns:
            continue

        l_val = pd.to_numeric(df[left], errors="coerce").fillna(0)
        r_val = pd.to_numeric(df[right], errors="coerce").fillna(0)
        t_val = pd.to_numeric(df[target], errors="coerce").fillna(0)

        with np.errstate(divide="ignore", invalid="ignore"):
            if op == "add":
                pred = l_val + r_val
            elif op == "subtract":
                pred = l_val - r_val
            elif op == "multiply":
                pred = l_val * r_val
            elif op == "divide":
                pred = np.where(r_val != 0, l_val / r_val, 0)
            else:
                continue

        satisfied = np.isclose(pred, t_val, rtol=1e-3, atol=1e-2)
        valid_mask = valid_mask & satisfied

    return float(round(valid_mask.mean() * 100.0, 2))


def run_benchmark(
    dataset_path: str,
    models: list[str] = ["gaussian_copula", "ctgan", "tvae"],
    sample_size: int = 1000,
    random_state: int = 42,
    generator_kwargs_map: dict | None = None,
) -> dict:
    df_raw = pd.read_csv(dataset_path)
    if len(df_raw) > sample_size:
        df_real = df_raw.sample(n=sample_size, random_state=random_state).reset_index(drop=True)
    else:
        df_real = df_raw.copy().reset_index(drop=True)

    rules = detect_arithmetic_relationships(df_real)
    logger.info(f"Detected {len(rules)} business rules on dataset {dataset_path}")

    # Prepare configurations placeholder
    configurations = [
        {"column_name": col, "action": "keep"}
        for col in df_real.columns
    ]
    # Mark ID columns as new_id if name ends with _id
    for cfg in configurations:
        if cfg["column_name"].lower().endswith("_id"):
            cfg["action"] = "new_id"

    # Identify ML target candidate
    ml_candidates = list_ml_target_candidates(df_real, df_real, configurations, None)
    target_col = ml_candidates[0]["column"] if ml_candidates else None
    logger.info(f"Benchmark ML target chosen: {target_col}")

    results = {}
    generator_kwargs_map = generator_kwargs_map or {}

    for model_name in models:
        logger.info(f"--- Running baseline for {model_name} ---")
        try:
            extra_kwargs = generator_kwargs_map.get(model_name, {})
            # Use small epochs for benchmark if neural
            gen_params = {"random_state": random_state}
            if model_name in ("ctgan", "tvae"):
                gen_params["epochs"] = extra_kwargs.get("epochs", 20)
                gen_params["batch_size"] = extra_kwargs.get("batch_size", 100)
            gen_params.update(extra_kwargs)

            generator = get_generator(model_name, **gen_params)

            # Columns used for training
            cols_to_drop = [c["column_name"] for c in configurations if c["action"] == "new_id"]
            train_df = df_real.drop(columns=cols_to_drop, errors="ignore")

            generator.fit(train_df)
            synthetic_df = generator.generate(num_rows=len(df_real))

            # Re-attach dummy/sequential IDs for fair schema matching
            for col in cols_to_drop:
                if col in df_real.columns:
                    prefix = df_real[col].iloc[0][:3] if isinstance(df_real[col].iloc[0], str) else "ID"
                    synthetic_df[col] = [f"{prefix}{i:05d}" for i in range(len(synthetic_df))]

            # Compute evaluations
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
                random_state=random_state,
            )

            validity_score = check_rule_validity(synthetic_df, rules)

            results[model_name] = {
                "statistical_similarity": stat_eval.get("overall_score"),
                "correlation_score": corr_eval.get("overall_score"),
                "correlation_error": corr_eval.get("mean_correlation_difference"),
                "ml_utility_score": ml_eval.get("overall_score"),
                "business_rule_validity": validity_score,
                "exact_match_rate": privacy_eval.get("exact_match_rate", 0.0),
                "dcr_ratio": privacy_eval.get("dcr_ratio", 1.0),
                "privacy_score": privacy_eval.get("overall_score"),
            }
        except Exception as e:
            logger.error(f"Failed benchmark for {model_name}: {e}", exc_info=True)
            results[model_name] = {"error": str(e)}

    return {
        "dataset": os.path.basename(dataset_path),
        "sample_size": len(df_real),
        "random_state": random_state,
        "rules_count": len(rules),
        "ml_target": target_col,
        "models": results,
    }


if __name__ == "__main__":
    out_dir = PROJECT_ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "quality_baseline.json"

    dataset_path = str(PROJECT_ROOT / "data" / "sample_supply_chain" / "purchase_orders.csv")
    print(f"Running baseline benchmark on {dataset_path}...")
    baseline_data = run_benchmark(dataset_path=dataset_path, models=["gaussian_copula", "ctgan", "tvae"])

    with open(out_file, "w") as f:
        json.dump(baseline_data, f, indent=2)

    print("\n================== BASELINE RESULTS ==================")
    print(json.dumps(baseline_data, indent=2))
    print(f"\nSaved baseline to: {out_file}")
