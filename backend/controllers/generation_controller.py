import logging

from celery.result import AsyncResult
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from backend.schemas.api_schema import (
    AutoTuneGenerationRequest,
    GenerationRequest,
)
from backend.services.auto_tuning_service import (
    auto_tune_generation,
)
from backend.services.generation_service import (
    generate_synthetic_dataset,
)
from backend.utils.auth_dependency import get_current_user
from backend.worker.celery_app import celery_app
from backend.worker.column_analysis_job import redis_is_available
from backend.worker.generation_job import (
    get_local_generation_job,
    start_local_generation,
)
from backend.worker.tasks import generate_dataset_task


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["Generation"],
)


def _enqueue_generation(
    dataset_id: int,
    model_name: str,
    user_id: int,
    parameters: dict | None,
) -> str:
    broker_url = celery_app.conf.broker_url or "redis://localhost:6379/0"

    if redis_is_available(broker_url):
        try:
            task = generate_dataset_task.delay(
                dataset_id,
                model_name,
                user_id,
                parameters,
            )
            return task.id
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
    )


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
        if request.background is False:
            return generate_synthetic_dataset(
                dataset_id=request.dataset_id,
                model_name=request.model_name,
                parameters=request.parameters,
                user_id=user_id,
            )

        job_id = _enqueue_generation(
            dataset_id=request.dataset_id,
            model_name=request.model_name,
            user_id=user_id,
            parameters=request.parameters,
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


@router.get(
    "/generation/status/{job_id}",
    summary="Get generation job status",
    description=(
        "Returns the current state of a generation job. "
        "States: PENDING, PROGRESS, SUCCESS, FAILURE."
    ),
)
def get_generation_status(job_id: str):
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


@router.post(
    "/generation/auto-tune",
    summary="Automatic tuning and regeneration workflow (US-022)",
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