import json
import logging
from pathlib import Path

import pandas as pd
from celery.result import AsyncResult
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from backend.schemas.api_schema import (
    AutoTuneGenerationRequest,
    GenerationRequest,
    ImproveQualityRequest,
    QualityFeedbackRequest,
)
from backend.services.auto_tuning_service import (
    auto_tune_generation,
)
from backend.services.generation_service import (
    generate_synthetic_dataset,
)
from backend.services.supply_chain_domain_service import (
    improve_generation_result,
)
from backend.repositories.feedback_repository import save_quality_feedback
from backend.repositories.dataset_repository import (
    get_dataset_user_id,
)
from backend.repositories.generation_repository import (
    get_algorithm_timing_stats,
    get_generated_result_by_id,
)
import uuid
from backend.repositories.generation_job_repository import (
    claim_job_for_restart,
    claim_job_for_resume,
    clear_job_heartbeat,
    create_generation_job,
    delete_generation_job,
    get_generation_job,
    get_generation_job_for_user,
    list_generation_jobs_for_user,
    list_incomplete_jobs_for_user,
    pause_active_jobs_for_user,
    touch_job_heartbeat,
    touch_user_active_jobs,
    update_generation_job_status,
)
from backend.services.generated_dataset_service import (
    prepare_dataset_for_generation,
)
from backend.services.generation_checkpoint_service import (
    clear_job_control,
    delete_checkpoint,
    request_job_cancel,
    request_job_pause,
)
from backend.utils.auth_dependency import get_current_user
from backend.worker.celery_app import celery_app
from backend.worker.column_analysis_job import redis_is_available
from backend.worker.generation_job import (
    get_local_generation_job,
    start_local_generation,
)
from backend.worker.tasks import generate_dataset_task, generate_multi_table_task


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["Generation"],
)


def _best_effort(fn, *args) -> None:
    """Heartbeat bookkeeping must never break the request it rides on."""
    try:
        fn(*args)
    except Exception:
        logger.debug("Heartbeat update failed", exc_info=True)


def _enqueue_generation(
    dataset_id: int,
    model_name: str,
    user_id: int,
    parameters: dict | None,
    job_id: str | None = None,
    resume: bool = False,
) -> str:
    jid = job_id or str(uuid.uuid4())
    broker_url = celery_app.conf.broker_url or "redis://localhost:6379/0"

    if redis_is_available(broker_url):
        try:
            task = generate_dataset_task.apply_async(
                args=[dataset_id, model_name, user_id, parameters, jid, resume],
                task_id=jid,
            )
            return jid
        except Exception:
            logger.exception(
                "Celery enqueue failed; falling back to in-process generation"
            )
    else:
        logger.warning(
            "Redis is not reachable at %s; running generation in-process",
            broker_url,
        )

    return start_local_generation(
        dataset_id=dataset_id,
        model_name=model_name,
        user_id=user_id,
        parameters=parameters,
        job_id=jid,
        resume=resume,
    )



def _enqueue_multi_table_generation(
    *, group_id: int, model_name: str, user_id: int,
    parameters: dict | None, job_id: str, resume: bool = False,
) -> str:
    broker_url = celery_app.conf.broker_url or "redis://localhost:6379/0"
    if redis_is_available(broker_url):
        try:
            generate_multi_table_task.apply_async(
                args=[group_id, model_name, user_id, parameters, job_id, resume],
                task_id=job_id,
            )
            return job_id
        except Exception:
            logger.exception("Celery enqueue failed; falling back to in-process multi-table generation")
    from backend.worker.generation_job import start_local_multi_table_generation
    return start_local_multi_table_generation(
        group_id=group_id, model_name=model_name, user_id=user_id,
        parameters=parameters, job_id=job_id, resume=resume,
    )


def _status_from_local(job_id: str, job: dict) -> dict:
    response = {
        "job_id": job_id,
        "status": job.get("state", "PENDING"),
    }

    state = response["status"]
    if state in ("PROGRESS", "PAUSED", "INTERRUPTED", "CANCELLED"):
        response["progress"] = job.get("info")
    elif state == "SUCCESS":
        response["result"] = job.get("result")
    elif state == "FAILURE":
        response["error"] = str(job.get("info") or "Generation failed")

    return response


@router.post(
    "/generation",
    summary="Generate synthetic data",
    description=(
        "Queues synthetic data generation (tabular models plus local "
        "Ollama text columns). Returns a job_id immediately unless "
        "background=false. Poll /generation/status/{job_id} for progress."
    ),
)
def generate_synthetic_data(
    request: GenerationRequest,
    user_id: int = Depends(get_current_user),
):
    try:
        job_id = str(uuid.uuid4())

        # Ownership first: never create a job row for someone else's dataset.
        if get_dataset_user_id(request.dataset_id) != user_id:
            raise PermissionError(
                "You do not have permission to generate data for this dataset."
            )

        # The job row is what pause / resume / recovery depend on. If it cannot
        # be created, fail loudly instead of running an untracked generation.
        prep = prepare_dataset_for_generation(request.dataset_id)
        file_name = prep["filename"]
        df_len = len(prep["dataframe"])
        configs = prep["configurations"]
        total_rows = int((request.parameters or {}).get("num_rows", df_len))
        create_generation_job(
            job_id=job_id,
            user_id=user_id,
            dataset_id=request.dataset_id,
            file_name=file_name,
            model_name=request.model_name,
            total_rows=total_rows,
            parameters=request.parameters,
            column_configurations=configs,
            llm_model=(request.parameters or {}).get("llm_model"),
        )

        if request.background is False:
            # A synchronous run is not polled by the browser: opt it out of the
            # idle auto-pause (the HTTP request itself is the connection).
            _best_effort(clear_job_heartbeat, job_id)
            return generate_synthetic_dataset(
                dataset_id=request.dataset_id,
                model_name=request.model_name,
                parameters=request.parameters,
                user_id=user_id,
                job_id=job_id,
            )

        job_id = _enqueue_generation(
            dataset_id=request.dataset_id,
            model_name=request.model_name,
            user_id=user_id,
            parameters=request.parameters,
            job_id=job_id,
        )
        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Generation started in background.",
            "poll_url": f"/generation/status/{job_id}",
        }

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception as exc:
        logger.exception("Failed to start generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start generation: {exc}",
        )


# Rough starting estimates (seconds per 100 rows) used until the user has
# at least one completed run of that algorithm.
_ESTIMATED_SECONDS_PER_100_ROWS = {
    "gaussian_copula": 0.1,
    "ctgan": 2.5,
    "tvae": 2.0,
}


@router.get(
    "/generation/algorithm-stats",
    summary="Generation speed per algorithm",
    description=(
        "Seconds per 100 rows for each algorithm. Measured from the user's "
        "own completed runs when available, otherwise a rough estimate."
    ),
)
def get_algorithm_stats(user_id: int = Depends(get_current_user)):
    try:
        measured = get_algorithm_timing_stats(user_id)
    except Exception:
        logger.exception("Could not load algorithm timing stats")
        measured = {}

    models = {}
    for model_id, estimate in _ESTIMATED_SECONDS_PER_100_ROWS.items():
        stat = measured.get(model_id)
        if stat and stat["rows"] > 0 and stat["seconds"] > 0:
            models[model_id] = {
                "seconds_per_100_rows": round(
                    stat["seconds"] / stat["rows"] * 100, 2
                ),
                "source": "measured",
                "runs": stat["runs"],
            }
        else:
            models[model_id] = {
                "seconds_per_100_rows": estimate,
                "source": "estimate",
                "runs": 0,
            }

    return {"models": models}


@router.get(
    "/generation/status/{job_id}",
    summary="Get generation job status",
    description=(
        "Returns the current state of a generation job. "
        "States: PENDING, PROGRESS, SUCCESS, FAILURE."
    ),
)
def get_generation_status(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    if not get_generation_job_for_user(job_id=job_id, user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found.",
        )

    # A signed-in browser is watching this job.
    _best_effort(touch_job_heartbeat, job_id, user_id)

    local = get_local_generation_job(job_id)
    if local:
        return _status_from_local(job_id, local)

    try:
        task = AsyncResult(job_id, app=generate_dataset_task.app)
        response = {
            "job_id": job_id,
            "status": task.state,
        }

        if task.state == "PROGRESS":
            response["progress"] = task.info
        elif task.state == "SUCCESS":
            response["result"] = task.result
        elif task.state == "FAILURE":
            response["error"] = str(task.info)

        return response
    except Exception as exc:
        logger.exception("Failed to read generation job status")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not read job status: {exc}",
        )


@router.get(
    "/generation/jobs",
    summary="List generation jobs",
    description="Lists generation jobs for the authenticated user.",
)
def list_generation_jobs(
    status: str | None = Query(None, description="Optional status filter"),
    dataset_id: int | None = Query(None, description="Optional dataset ID filter"),
    limit: int = Query(50, ge=1, le=200),
    user_id: int = Depends(get_current_user),
):
    _best_effort(touch_user_active_jobs, user_id)
    try:
        jobs = list_generation_jobs_for_user(
            user_id=user_id,
            status=status,
            dataset_id=dataset_id,
            limit=limit,
        )
        return {"status": "success", "jobs": jobs}
    except Exception as exc:
        logger.exception("Failed to list generation jobs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {exc}",
        )


@router.get(
    "/generation/jobs/active",
    summary="List active / incomplete generation jobs",
    description="Returns incomplete jobs (running, pending, paused, interrupted) for the user to resume.",
)
def list_active_jobs(user_id: int = Depends(get_current_user)):
    _best_effort(touch_user_active_jobs, user_id)
    try:
        jobs = list_incomplete_jobs_for_user(user_id=user_id)
        return {"status": "success", "jobs": jobs}
    except Exception as exc:
        logger.exception("Failed to list active generation jobs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list active jobs: {exc}",
        )


@router.get(
    "/generation/jobs/{job_id}",
    summary="Get generation job details",
)
def get_job_details(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    job = get_generation_job_for_user(job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found.",
        )
    return {"status": "success", "job": job}


@router.post(
    "/generation/jobs/pause-active",
    summary="Pause every running generation job of the current user",
    description=(
        "Called when the user signs out. Each running job stops after its "
        "current batch; all finished batches stay checkpointed for Resume."
    ),
)
def pause_all_active_jobs(user_id: int = Depends(get_current_user)):
    try:
        job_ids = pause_active_jobs_for_user(user_id)
    except Exception as exc:
        logger.exception("Failed to pause active generation jobs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause active jobs: {exc}",
        )
    return {"status": "success", "paused_job_ids": job_ids}


@router.post(
    "/generation/jobs/{job_id}/pause",
    summary="Pause a running generation job",
)
def pause_generation_job(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    job = get_generation_job_for_user(job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found.",
        )
    if str(job.get("status", "")).lower() not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only a running job can be paused (current status: {job.get('status')}).",
        )
    request_job_pause(job_id)
    return {"status": "success", "message": "Pause request sent to generation job.", "job_id": job_id}


@router.post(
    "/generation/jobs/{job_id}/resume",
    summary="Resume an interrupted or paused generation job",
)
def resume_generation_job(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    job = get_generation_job_for_user(job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found.",
        )
    if job.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is already completed.",
        )

    # Atomic claim: only one concurrent resume can win (double-click safe).
    if not claim_job_for_resume(job_id=job_id, user_id=user_id):
        current = get_generation_job_for_user(job_id=job_id, user_id=user_id) or {}
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job cannot be resumed from status '{current.get('status')}'.",
        )
    clear_job_control(job_id)  # drop any stale in-process flag before the worker starts

    try:
        job_parameters = job.get("parameters") or {}
        multi_group_id = job_parameters.get("_multi_table_group_id")
        if multi_group_id:
            _enqueue_multi_table_generation(
                group_id=int(multi_group_id), model_name=job["model_name"],
                user_id=user_id, parameters=job_parameters, job_id=job_id, resume=True,
            )
        else:
            _enqueue_generation(
                dataset_id=job["dataset_id"],
                model_name=job["model_name"],
                user_id=user_id,
                parameters=job_parameters,
                job_id=job_id,
                resume=True,
            )
    except Exception as exc:
        logger.exception("Could not enqueue resume for job %s", job_id)
        update_generation_job_status(
            job_id=job_id,
            status="interrupted",
            stage_message="Resume could not be started. Please try again.",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not start resume: {exc}",
        )
    return {
        "status": "success",
        "message": "Job resumed successfully.",
        "job_id": job_id,
        "poll_url": f"/generation/status/{job_id}",
    }


@router.post(
    "/generation/jobs/{job_id}/restart",
    summary="Restart a generation job from the beginning",
)
def restart_generation_job(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    job = get_generation_job_for_user(job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found.",
        )

    if not claim_job_for_restart(job_id=job_id, user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job cannot be restarted while it is {job.get('status')}.",
        )
    clear_job_control(job_id)
    delete_checkpoint(job_id)
    job_parameters = job.get("parameters") or {}
    multi_group_id = job_parameters.get("_multi_table_group_id")
    if multi_group_id:
        _enqueue_multi_table_generation(
            group_id=int(multi_group_id), model_name=job["model_name"],
            user_id=user_id, parameters=job_parameters, job_id=job_id, resume=False,
        )
    else:
        _enqueue_generation(
            dataset_id=job["dataset_id"],
            model_name=job["model_name"],
            user_id=user_id,
            parameters=job_parameters,
            job_id=job_id,
            resume=False,
        )
    return {
        "status": "success",
        "message": "Job restarted from beginning.",
        "job_id": job_id,
        "poll_url": f"/generation/status/{job_id}",
    }


@router.post(
    "/generation/jobs/{job_id}/cancel",
    summary="Cancel a generation job",
)
def cancel_generation_job(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    job = get_generation_job_for_user(job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found.",
        )
    state = str(job.get("status", "")).lower()
    if state == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A completed job cannot be cancelled.",
        )
    if state in ("pending", "running"):
        # Tell the live worker first (DB flag + in-process flag), then mark it.
        request_job_cancel(job_id)
    else:
        delete_checkpoint(job_id)
    update_generation_job_status(
        job_id=job_id,
        status="cancelled",
        stage_message="Job cancelled by user.",
    )
    return {"status": "success", "message": "Generation job cancelled.", "job_id": job_id}


@router.delete(
    "/generation/jobs/{job_id}",
    summary="Discard/delete a generation job and its checkpoints",
)
def discard_generation_job(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    job = get_generation_job_for_user(job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found.",
        )
    if str(job.get("status", "")).lower() in ("pending", "running"):
        request_job_cancel(job_id)
    delete_checkpoint(job_id)
    delete_generation_job(job_id, user_id)
    return {"status": "success", "message": "Generation job discarded.", "job_id": job_id}


@router.get(
    "/generation/preview",
    summary="Preview sample rows of a generated dataset",
    description=(
        "Returns the first rows of a generated synthetic dataset so the "
        "user can inspect sample values right after generation."
    ),
)
def preview_generated_dataset(
    result_id: int = Query(..., description="Generated result ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of rows to return"),
    user_id: int = Depends(get_current_user),
):
    target = get_generated_result_by_id(result_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generated result {result_id} not found.",
        )

    if get_dataset_user_id(target["dataset_id"]) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    file_path_str = target.get("file_path")
    if not file_path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File path not recorded.",
        )

    file_path = Path(file_path_str)
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated file is missing on the server.",
        )

    try:
        dataframe = pd.read_csv(file_path, nrows=limit)
    except Exception as exc:
        logger.exception("Failed to read generated dataset preview")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read generated dataset: {exc}",
        )

    # to_json turns NaN into null and numpy types into plain JSON values.
    rows = json.loads(
        dataframe.to_json(orient="records", date_format="iso")
    )

    return {
        "result_id": target["result_id"],
        "file_name": target.get("file_name"),
        "columns": [str(c) for c in dataframe.columns],
        "rows": rows,
        "shown": len(rows),
        "total_rows": target.get("row_count"),
    }


@router.post(
    "/generation/auto-tune",
    summary="Automatic tuning and regeneration workflow",
    description=(
        "Iteratively generates, evaluates, tunes supported parameters based on "
        "identified weak metrics, and regenerates until quality criteria or max attempts are met."
    ),
)
def auto_tune_generation_endpoint(
    request: AutoTuneGenerationRequest,
    user_id: int = Depends(get_current_user),
):
    try:
        return auto_tune_generation(
            dataset_id=request.dataset_id,
            model_name=request.model_name,
            user_id=user_id,
            initial_parameters=request.parameters,
            max_attempts=request.max_attempts,
            min_score=request.min_score,
            improvement_threshold=request.improvement_threshold,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as exc:
        logger.exception("Auto-tune generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto-tune generation failed: {exc}",
        )


@router.post(
    "/generation/improve-quality",
    summary="Improve synthetic data quality with supply chain domain tuning",
    description=(
        "Applies dynamic supply chain domain tuning, verified derived feature reconstruction, "
        "quantile marginal matching, and privacy guard to improve a baseline generated result. "
        "Returns side-by-side metric comparison and persistent improved dataset."
    ),
)
def improve_quality_endpoint(
    request: ImproveQualityRequest,
    user_id: int = Depends(get_current_user),
):
    try:
        return improve_generation_result(
            result_id=request.result_id,
            user_id=user_id,
            parameters=request.parameters,
            max_attempts=request.max_attempts or 3,
            improvement_threshold=request.improvement_threshold or 1.0,
            target_column=request.target_column,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as exc:
        logger.exception("Improve quality failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Improve quality failed: {exc}",
        )



@router.post(
    "/generation/quality-feedback",
    summary="Save user feedback on an Improve Quality result",
)
def save_quality_feedback_endpoint(
    request: QualityFeedbackRequest,
    user_id: int = Depends(get_current_user),
):
    """Persist feedback only after verifying ownership of the referenced result."""
    allowed_feedback = {"helpful", "not_helpful", "partially_helpful"}
    allowed_focus = {
        None, "statistical_similarity", "correlation", "ml_utility",
        "privacy", "business_rules", "other",
    }
    if request.feedback not in allowed_feedback:
        raise HTTPException(status_code=400, detail="Invalid feedback value.")
    if request.focus_area not in allowed_focus:
        raise HTTPException(status_code=400, detail="Invalid feedback focus area.")

    try:
        baseline = get_generated_result_by_id(request.result_id)
        if not baseline:
            raise HTTPException(status_code=404, detail="Generation result not found.")
        dataset_id = baseline["dataset_id"]
        if get_dataset_user_id(dataset_id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied.")

        if request.improved_result_id is not None:
            improved = get_generated_result_by_id(request.improved_result_id)
            if not improved or improved.get("dataset_id") != dataset_id:
                raise HTTPException(status_code=400, detail="Improved result does not belong to the same dataset.")

        saved = save_quality_feedback(
            user_id=user_id,
            dataset_id=dataset_id,
            result_id=request.result_id,
            improved_result_id=request.improved_result_id,
            feedback=request.feedback,
            focus_area=request.focus_area,
            comment=(request.comment or "").strip()[:2000] or None,
        )
        return {"status": "success", "message": "Feedback saved.", **saved}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not save quality feedback")
        raise HTTPException(status_code=500, detail="Could not save feedback right now.") from exc
