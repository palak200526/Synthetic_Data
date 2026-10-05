import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from backend.utils.auth_dependency import get_current_user

from backend.repositories.dataset_repository import (
    get_dataset_user_id,
)

from backend.worker.celery_app import celery_app
from backend.worker.column_analysis_job import (
    get_local_job,
    redis_is_available,
    start_local_analysis,
)
from backend.worker.tasks import (
    analyze_columns_task,
)

from celery.result import AsyncResult


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["LLM Column Analysis"],
)


def _enqueue_analysis(dataset_id: int, user_id: int) -> str:
    broker_url = celery_app.conf.broker_url or "redis://localhost:6379/0"

    if redis_is_available(broker_url):
        try:
            task = analyze_columns_task.delay(dataset_id, user_id)
            return task.id
        except Exception:
            logger.exception(
                "Celery enqueue failed; falling back to in-process analysis"
            )
    else:
        logger.warning(
            "Redis is not reachable at %s; running column analysis in-process",
            broker_url,
        )

    return start_local_analysis(dataset_id, user_id)


def _status_from_local(job_id: str, job: dict) -> dict:
    response = {
        "job_id": job_id,
        "status": job.get("state", "PENDING"),
    }

    state = response["status"]
    if state == "PROGRESS":
        response["progress"] = job.get("info")
    elif state == "SUCCESS":
        response["result"] = job.get("result")
    elif state == "FAILURE":
        response["error"] = str(job.get("info") or "Analysis failed")

    return response


# =========================================================
# 1. Start Analysis (returns job_id immediately)
# =========================================================

@router.post(
    "/column-analysis/{dataset_id}",
    summary="Start column analysis in background",
    description=(
        "Queues an LLM-based column analysis job for the dataset. "
        "Returns a job_id immediately. Poll /column-analysis/status/{job_id} "
        "for progress and final results."
    ),
)
def analyze_dataset_columns_controller(
    dataset_id: int,
    user_id: int = Depends(get_current_user),
):
    try:
        dataset_user_id = get_dataset_user_id(dataset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if dataset_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this dataset.",
        )

    try:
        job_id = _enqueue_analysis(dataset_id, user_id)
    except Exception as exc:
        logger.exception("Failed to start column analysis")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start column analysis: {exc}",
        )

    return {
        "status": "queued",
        "job_id": job_id,
        "message": "Column analysis started in background.",
        "poll_url": f"/column-analysis/status/{job_id}",
    }


# =========================================================
# 2. Poll Analysis Status
# =========================================================

@router.get(
    "/column-analysis/status/{job_id}",
    summary="Get column analysis job status",
    description=(
        "Returns the current state of a column analysis job. "
        "States: PENDING, PROGRESS, SUCCESS, FAILURE."
    ),
)
def get_analysis_status(job_id: str):
    local = get_local_job(job_id)
    if local:
        return _status_from_local(job_id, local)

    try:
        task = AsyncResult(job_id, app=analyze_columns_task.app)
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
        logger.exception("Failed to read analysis job status")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not read job status: {exc}",
        )
