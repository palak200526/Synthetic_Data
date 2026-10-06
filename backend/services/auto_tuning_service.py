from __future__ import annotations

import logging
from typing import Any

from backend.services.evaluation_service import evaluate_generation
from backend.services.generation_service import generate_synthetic_dataset

logger = logging.getLogger(__name__)


def identify_weak_metrics(evaluation: dict[str, Any]) -> dict[str, Any]:
    """
    Inspect evaluation results and identify weak dimensions:
    - statistical similarity (low scoring columns)
    - correlation / covariance
    - machine learning utility
    """
    weak_areas = {
        "weak_columns": [],
        "low_statistical": False,
        "low_correlation": False,
        "low_ml_utility": False,
    }

    if not evaluation:
        return weak_areas

    # 1. Statistical similarity check
    stat = evaluation.get("statistical_similarity") or evaluation
    stat_score = stat.get("overall_score")
    if stat_score is not None and stat_score < 75.0:
        weak_areas["low_statistical"] = True

    columns = stat.get("columns", {})
    if isinstance(columns, dict):
        for col_name, col_data in columns.items():
            if isinstance(col_data, dict):
                col_score = col_data.get("score")
                if col_score is not None and col_score < 70.0:
                    weak_areas["weak_columns"].append(
                        {
                            "column": col_name,
                            "type": col_data.get("column_type"),
                            "score": col_score,
                        }
                    )

    # 2. Correlation / covariance check
    corr = evaluation.get("correlation_covariance")
    if isinstance(corr, dict):
        corr_score = corr.get("overall_score")
        if corr_score is not None and corr_score < 70.0:
            weak_areas["low_correlation"] = True

    # 3. ML utility check
    ml = evaluation.get("ml_utility")
    if isinstance(ml, dict):
        ml_score = ml.get("overall_score")
        if ml_score is not None and ml_score < 70.0:
            weak_areas["low_ml_utility"] = True

    return weak_areas


def tune_generation_parameters(
    model_name: str,
    current_params: dict[str, Any] | None,
    evaluation: dict[str, Any],
    attempt: int,
) -> dict[str, Any]:
    """
    Adjust applicable generation settings based on identified weak metrics.

    IMPORTANT:
    Only adjusts parameters that are supported by the selected generator:
    - Gaussian Copula: random_state
    - CTGAN: epochs, batch_size, learning_rate, random_state
    - TVAE: latent_dim, epochs, batch_size, learning_rate, random_state
    - LLM text: llm_text_similarity_threshold, llm_text_batch_size
    """
    params = dict(current_params or {})
    model_key = model_name.lower().strip()
    weak = identify_weak_metrics(evaluation)

    if model_key in ("gaussian_copula", "gaussian copula", "gaussiancopula"):
        # Gaussian Copula supports random_state
        base_seed = int(params.get("random_state", 42))
        params["random_state"] = base_seed + (attempt * 13)

    elif model_key == "ctgan":
        # CTGAN supports: epochs, batch_size, learning_rate, random_state
        epochs = int(params.get("epochs", 100))
        lr = float(params.get("learning_rate", 0.0002))
        bs = int(params.get("batch_size", 32))
        seed = int(params.get("random_state", 42))

        # If overall statistical or correlation is low, increase epochs
        if weak["low_statistical"] or weak["low_correlation"]:
            params["epochs"] = epochs + 25
            params["learning_rate"] = round(max(0.00005, lr * 0.85), 6)
        else:
            params["epochs"] = epochs + 15

        params["random_state"] = seed + attempt

    elif model_key == "tvae":
        # TVAE supports: latent_dim, epochs, batch_size, learning_rate, random_state
        latent_dim = int(params.get("latent_dim", 16))
        epochs = int(params.get("epochs", 100))
        lr = float(params.get("learning_rate", 0.001))
        seed = int(params.get("random_state", 42))

        # If correlation is low, TVAE benefits from wider latent space
        if weak["low_correlation"]:
            params["latent_dim"] = min(64, latent_dim * 2)

        if weak["low_statistical"]:
            params["epochs"] = epochs + 25
            params["learning_rate"] = round(max(0.0001, lr * 0.8), 6)
        else:
            params["epochs"] = epochs + 15

        params["random_state"] = seed + attempt

    # If text columns exist and LLM parameters present
    if "llm_text_similarity_threshold" in params:
        sim = float(params["llm_text_similarity_threshold"])
        params["llm_text_similarity_threshold"] = min(0.95, round(sim + 0.05, 2))

    return params


def auto_tune_generation(
    dataset_id: int,
    model_name: str,
    user_id: int,
    initial_parameters: dict[str, Any] | None = None,
    max_attempts: int = 3,
    min_score: float = 80.0,
    improvement_threshold: float = 1.0,
) -> dict[str, Any]:
    """
    US-022: Automatic Tuning and Regeneration Workflow.

    Workflow:
    1. Generate synthetic data.
    2. Evaluate generated data.
    3. Identify weak metrics.
    4. Tune supported generation parameters.
    5. Regenerate.
    6. Re-evaluate.
    7. Stop when quality criteria are met or max attempts are reached.
    8. Retain the best result.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    current_params = dict(initial_parameters or {})
    history = []
    best_result = None
    best_score = -1.0
    stop_reason = ""
    prev_score: float | None = None

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Auto-tune attempt %d/%d for dataset %s with %s",
            attempt,
            max_attempts,
            dataset_id,
            model_name,
        )

        # 1. Run generation
        gen_res = generate_synthetic_dataset(
            dataset_id=dataset_id,
            model_name=model_name,
            parameters=current_params,
            user_id=user_id,
        )
        result_id = gen_res["result_id"]

        # 2. Run evaluation
        eval_res = evaluate_generation(
            result_id=result_id,
            user_id=user_id,
            force_recompute=True,
        )

        # Determine score
        curr_score = (
            eval_res.get("overall_score")
            or eval_res.get("evaluation", {}).get("overall_score")
            or 0.0
        )
        curr_score = float(curr_score)

        attempt_info = {
            "attempt": attempt,
            "result_id": result_id,
            "run_id": gen_res.get("run_id"),
            "parameters": dict(current_params),
            "score": curr_score,
            "weak_metrics": identify_weak_metrics(eval_res.get("evaluation", {})),
        }
        history.append(attempt_info)

        # Track best
        if curr_score > best_score:
            best_score = curr_score
            best_result = {
                **attempt_info,
                "file_name": gen_res.get("file_name"),
                "file_path": gen_res.get("file_path"),
                "evaluation": eval_res.get("evaluation"),
            }

        # Check stopping criteria
        # Criterion 1: Met target score
        if curr_score >= min_score:
            stop_reason = (
                f"Target score satisfied: {curr_score:.2f} >= {min_score:.2f}"
            )
            break

        # Criterion 2: Improvement below threshold (from 2nd attempt onwards)
        if prev_score is not None:
            improvement = curr_score - prev_score
            if improvement < improvement_threshold:
                stop_reason = (
                    f"Improvement below threshold: {improvement:.2f} < {improvement_threshold:.2f}"
                )
                break

        # Criterion 3: Reached max attempts
        if attempt >= max_attempts:
            stop_reason = f"Maximum attempts reached: {max_attempts}"
            break

        # If continuing, tune parameters for next attempt
        current_params = tune_generation_parameters(
            model_name=model_name,
            current_params=current_params,
            evaluation=eval_res.get("evaluation", {}),
            attempt=attempt,
        )
        prev_score = curr_score

    return {
        "status": "success",
        "dataset_id": dataset_id,
        "model_name": model_name,
        "total_attempts": len(history),
        "best_score": best_score,
        "best_result_id": best_result.get("result_id") if best_result else None,
        "stop_reason": stop_reason,
        "stopping_criteria": {
            "max_attempts": max_attempts,
            "min_score": min_score,
            "improvement_threshold": improvement_threshold,
        },
        "history": history,
        "best_result": best_result,
    }
