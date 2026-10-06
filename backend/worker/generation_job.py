import logging
import threading
import uuid
from typing import Any, Callable, Optional

from backend.services.generation_service import generate_synthetic_dataset
from backend.worker.column_analysis_job import redis_is_available

logger = logging.getLogger(__name__)

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def run_generation(
    dataset_id: int,
    model_name: str,
    user_id: int,
    parameters: Optional[dict] = None,
    progress_update: Optional[Callable[[str, dict], None]] = None,
) -> dict:
    def progress_callback(meta: dict) -> None:
        if progress_update:
            progress_update("PROGRESS", meta)

    return generate_synthetic_dataset(
        dataset_id=dataset_id,
        model_name=model_name,
        user_id=user_id,
        parameters=parameters,
        progress_callback=progress_callback,
    )


def get_local_generation_job(job_id: str) -> Optional[dict]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def _set_job(job_id: str, **kwargs) -> None:
    with _LOCK:
        _JOBS.setdefault(job_id, {})
        _JOBS[job_id].update(kwargs)


def start_local_generation(
    dataset_id: int,
    model_name: str,
    user_id: int,
    parameters: Optional[dict] = None,
) -> str:
    job_id = str(uuid.uuid4())
    _set_job(job_id, state="PENDING", info=None, result=None)

    def _run() -> None:
        def progress_update(state: str, meta: dict) -> None:
            _set_job(job_id, state=state, info=meta)

        try:
            result = run_generation(
                dataset_id,
                model_name,
                user_id,
                parameters,
                progress_update,
            )
            _set_job(job_id, state="SUCCESS", result=result, info=None)
        except Exception as exc:
            logger.exception("In-process generation failed")
            _set_job(job_id, state="FAILURE", info=str(exc), result=None)

    threading.Thread(
        target=_run,
        daemon=True,
        name=f"generation-{job_id[:8]}",
    ).start()
    return job_id


__all__ = [
    "get_local_generation_job",
    "redis_is_available",
    "run_generation",
    "start_local_generation",
]
