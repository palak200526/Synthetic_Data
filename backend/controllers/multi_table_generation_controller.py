import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from backend.schemas.api_schema import MultiTableGenerationRequest
from backend.services.multi_table_generation_service import (
    generate_linked_tables, load_group_datasets,
)
from backend.repositories.dataset_repository import get_dataset_user_id
from backend.repositories.generation_job_repository import create_generation_job
from backend.worker.celery_app import celery_app
from backend.worker.column_analysis_job import redis_is_available
from backend.worker.tasks import generate_multi_table_task
from backend.worker.generation_job import start_local_multi_table_generation
from backend.services.referential_integrity_service import (
    validate_referential_integrity,
)
from backend.utils.auth_dependency import get_current_user


router = APIRouter(
    prefix="",
    tags=["Generation"],
)


@router.post(
    "/generation/multi-table",
    summary="Generate multi-table synthetic data",
    description=(
        "Generates synthetic data for multiple related tables while preserving "
        "the configured relationships between datasets. This endpoint is used "
        "for relational datasets such as supply-chain data."
    ),
)
def generate_multi_table_data(
    request: MultiTableGenerationRequest,
    current_user=Depends(get_current_user),
):
    """Queue multi-table generation as a resumable job."""
    user_id = int(current_user)
    try:
        group_data = load_group_datasets(request.group_id)
        dataset_ids = list(group_data["datasets"].keys())
        if not dataset_ids:
            raise ValueError(f"No datasets found for group {request.group_id}.")
        for dataset_id in dataset_ids:
            if get_dataset_user_id(dataset_id) != user_id:
                raise PermissionError("You do not have permission to generate this dataset group.")

        job_id = str(uuid.uuid4())
        total_rows = sum(len(info["dataframe"]) for info in group_data["datasets"].values())
        first_dataset_id = int(dataset_ids[0])
        parameters = dict(request.parameters or {})
        # Reserved metadata lets the shared Resume/Restart endpoints dispatch
        # this job back to the multi-table worker rather than single-table code.
        parameters["_multi_table_group_id"] = int(request.group_id)
        parameters["_multi_table_dataset_ids"] = [int(x) for x in dataset_ids]
        create_generation_job(
            job_id=job_id,
            user_id=user_id,
            dataset_id=first_dataset_id,
            file_name=f"Multi-table group {request.group_id}",
            model_name=request.model_name,
            total_rows=total_rows,
            parameters=parameters,
            column_configurations=[],
        )

        broker_url = celery_app.conf.broker_url or "redis://localhost:6379/0"
        if redis_is_available(broker_url):
            try:
                generate_multi_table_task.apply_async(
                    args=[request.group_id, request.model_name, user_id, parameters, job_id, False],
                    task_id=job_id,
                )
            except Exception:
                logging.getLogger(__name__).exception("Celery enqueue failed; using in-process multi-table worker")
                start_local_multi_table_generation(
                    group_id=request.group_id, model_name=request.model_name,
                    user_id=user_id, parameters=parameters, job_id=job_id,
                )
        else:
            start_local_multi_table_generation(
                group_id=request.group_id, model_name=request.model_name,
                user_id=user_id, parameters=parameters, job_id=job_id,
            )

        return {
            "status": "queued",
            "job_id": job_id,
            "group_id": request.group_id,
            "message": "Multi-table generation started in background. Progress is checkpointed after each table.",
            "poll_url": f"/generation/status/{job_id}",
        }
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logging.getLogger(__name__).exception("Failed to start multi-table generation")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start multi-table generation: {exc}")
