from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from backend.repositories.configuration_repository import (
    get_configurations,
)
from backend.repositories.dataset_repository import (
    get_dataset_file_path,
    get_dataset_user_id,
)
from backend.repositories.evaluation_repository import (
    get_evaluation_by_result_id,
    save_evaluation_result,
)
from backend.repositories.generation_repository import (
    get_generated_result_by_id,
)
from backend.repositories.profile_repository import (
    get_dataset_profile,
)
from backend.services.correlation_evaluation_service import (
    evaluate_correlation_covariance,
)
from backend.services.dataset_loader import load_dataset
from backend.services.ml_utility_service import (
    evaluate_ml_utility,
)
from backend.services.referential_integrity_service import (
    evaluate_referential_integrity,
)
from backend.services.statistical_evaluation_service import (
    evaluate_statistical_similarity,
)
from backend.services.text_evaluation_service import (
    evaluate_text_quality,
)

logger = logging.getLogger(__name__)


def evaluate_generation(
    result_id: int,
    user_id: int,
    force_recompute: bool = True,
) -> dict[str, Any]:
    """
    Complete evaluation pipeline across S4 user stories:
    - US-023: Statistical similarity evaluation and scoring (with exclusions)
    - US-024: Correlation/covariance utility evaluation
    - US-025: Synthetic-train / real-test ML utility evaluation
    - US-027: Cross-table referential integrity evaluation
    - US-026: Persistence and retrieval of utility and privacy evaluation results
    """
    # --------------------------------------------------
    # 1. Get generated result
    # --------------------------------------------------
    generated_result = get_generated_result_by_id(result_id)
    if not generated_result:
        raise ValueError(f"Generated result {result_id} does not exist.")

    # --------------------------------------------------
    # 2. Get dataset information & verify access
    # --------------------------------------------------
    dataset_id = generated_result["dataset_id"]
    dataset_user_id = get_dataset_user_id(dataset_id)
    if dataset_user_id != user_id:
        raise PermissionError(
            "You do not have permission to evaluate this generated dataset."
        )

    # --------------------------------------------------
    # 3. Load original dataset
    # --------------------------------------------------
    source_file_path = get_dataset_file_path(dataset_id)
    real_dataframe = load_dataset(str(source_file_path))

    # --------------------------------------------------
    # 4. Load synthetic dataset
    # --------------------------------------------------
    generated_file_path = Path(generated_result["file_path"])
    if not generated_file_path.is_absolute():
        generated_file_path = Path.cwd() / generated_file_path

    if not generated_file_path.exists():
        raise FileNotFoundError(
            f"Generated dataset file not found: {generated_file_path}"
        )

    synthetic_dataframe = load_dataset(str(generated_file_path))

    # --------------------------------------------------
    # 5. Fetch column configurations & dataset profile
    # --------------------------------------------------
    configurations = []
    try:
        configurations = get_configurations(dataset_id)
    except Exception as exc:
        logger.warning(
            "Could not fetch configurations for dataset %s: %s",
            dataset_id,
            exc,
        )

    profile_data = None
    try:
        profile_res = get_dataset_profile(dataset_id)
        if profile_res:
            profile_data = profile_res.get("profile_data")
    except Exception as exc:
        logger.info(
            "Profile not found or could not be loaded for dataset %s: %s",
            dataset_id,
            exc,
        )

    # --------------------------------------------------
    # 6. US-023: Statistical similarity evaluation
    # --------------------------------------------------
    statistical_result = evaluate_statistical_similarity(
        real_dataframe=real_dataframe,
        synthetic_dataframe=synthetic_dataframe,
        column_configurations=configurations,
        dataset_profile=profile_data,
    )

    # --------------------------------------------------
    # 7. US-024: Correlation & covariance evaluation
    # --------------------------------------------------
    correlation_result = evaluate_correlation_covariance(
        real_dataframe=real_dataframe,
        synthetic_dataframe=synthetic_dataframe,
        column_configurations=configurations,
        dataset_profile=profile_data,
    )

    # --------------------------------------------------
    # 8. US-025: ML utility evaluation (Synthetic-Train / Real-Test)
    # --------------------------------------------------
    ml_utility_result = evaluate_ml_utility(
        real_dataframe=real_dataframe,
        synthetic_dataframe=synthetic_dataframe,
        column_configurations=configurations,
        dataset_profile=profile_data,
    )

    # --------------------------------------------------
    # 9. US-027: Cross-table referential integrity evaluation
    # --------------------------------------------------
    referential_result = evaluate_referential_integrity(
        dataset_id=dataset_id,
        tables={dataset_id: synthetic_dataframe},
    )

    # --------------------------------------------------
    # 10. String / Free-Form Text Evaluation
    # --------------------------------------------------
    text_result = evaluate_text_quality(
        real_dataframe=real_dataframe,
        synthetic_dataframe=synthetic_dataframe,
        column_configurations=configurations,
        dataset_profile=profile_data,
    )

    # --------------------------------------------------
    # 11. Composite Score Calculation
    # --------------------------------------------------
    evaluated_scores = []
    stat_score = statistical_result.get("overall_score")
    if stat_score is not None:
        evaluated_scores.append(float(stat_score))

    corr_score = correlation_result.get("overall_score")
    if corr_score is not None:
        evaluated_scores.append(float(corr_score))

    ml_score = ml_utility_result.get("overall_score")
    if ml_score is not None:
        evaluated_scores.append(float(ml_score))

    ref_score = referential_result.get("overall_score")
    if ref_score is not None:
        evaluated_scores.append(float(ref_score))

    text_score = text_result.get("overall_score")
    if text_score is not None:
        evaluated_scores.append(float(text_score))

    if evaluated_scores:
        overall_composite_score = round(float(np.mean(evaluated_scores)), 2)
    else:
        overall_composite_score = None

    # --------------------------------------------------
    # 12. US-026: Persistence
    # --------------------------------------------------
    utility_metrics_payload = {
        "dataset_id": dataset_id,
        "run_id": generated_result["run_id"],
        "result_id": result_id,
        "status": "completed",
        "overall_score": overall_composite_score,
        "statistical_similarity": statistical_result,
        "correlation_covariance": correlation_result,
        "ml_utility": ml_utility_result,
        "relationship_integrity": referential_result,
        "text_evaluation": text_result,
    }

    saved_record = None
    try:
        saved_record = save_evaluation_result(
            result_id=result_id,
            utility_metrics=utility_metrics_payload,
            privacy_metrics=None,
            overall_score=overall_composite_score,
        )
    except Exception as exc:
        logger.error(
            "Failed to persist evaluation results for result %s: %s",
            result_id,
            exc,
        )

    # --------------------------------------------------
    # 13. Build response payload (flat + composite for frontend compatibility)
    # --------------------------------------------------
    evaluation_payload = {
        "metric": "statistical_similarity",
        "overall_score": stat_score if stat_score is not None else overall_composite_score,
        "composite_overall_score": overall_composite_score,
        "evaluated_columns": statistical_result.get("evaluated_columns", 0),
        "excluded_columns": statistical_result.get("excluded_columns", 0),
        "total_common_columns": statistical_result.get("total_common_columns", 0),
        "columns": statistical_result.get("columns", {}),
        "message": statistical_result.get("message", "Evaluation complete."),
        # Multi-category objects for dashboard and comparison tabs:
        "statistical_similarity": statistical_result,
        "correlation_covariance": correlation_result,
        "ml_utility": ml_utility_result,
        "relationship_integrity": referential_result,
        "text_evaluation": text_result,
    }

    return {
        "result_id": result_id,
        "dataset_id": dataset_id,
        "evaluation_id": saved_record.get("evaluation_id") if saved_record else None,
        "overall_score": overall_composite_score,
        "evaluation": evaluation_payload,
    }


def get_persisted_evaluation(result_id: int) -> dict[str, Any] | None:
    """Retrieve already computed evaluation from database."""
    return get_evaluation_by_result_id(result_id)