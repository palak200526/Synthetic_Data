import logging
import threading
import uuid
from typing import Any, Callable, Optional

from backend.repositories.dataset_repository import (
    get_dataset_file_path,
    get_dataset_user_id,
)
from backend.services.column_profile_service import (
    build_dataset_column_profiles,
)
from backend.services.dataset_loader import load_dataset
from backend.services.llm_column_analysis_service import (
    analyze_columns,
)


logger = logging.getLogger(__name__)

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def run_column_analysis(
    dataset_id: int,
    user_id: int,
    progress_update: Optional[Callable[[str, dict], None]] = None,
) -> dict:
    if get_dataset_user_id(dataset_id) != user_id:
        raise PermissionError("Access denied to this dataset.")

    file_path = get_dataset_file_path(dataset_id)
    dataframe = load_dataset(str(file_path))

    if progress_update:
        progress_update("PROGRESS", {"stage": "profiling", "percent": 10})

    profiles = build_dataset_column_profiles(dataframe)

    def progress_callback(current_batch, total_batches):
        percent = 10 + int((current_batch / max(total_batches, 1)) * 85)
        if progress_update:
            progress_update(
                "PROGRESS",
                {
                    "stage": "llm_analysis",
                    "current_batch": current_batch,
                    "total_batches": total_batches,
                    "percent": percent,
                },
            )

    analysis = analyze_columns(
        profiles,
        progress_callback=progress_callback,
    )

    return {
        "status": "success",
        "dataset_id": dataset_id,
        "columns_analyzed": len(analysis.columns),
        "data": analysis.model_dump(),
    }


def redis_is_available(url: str = "redis://localhost:6379/0") -> bool:
    try:
        import redis

        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        return bool(client.ping())
    except Exception:
        return False


def get_local_job(job_id: str) -> Optional[dict]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def _set_job(job_id: str, **kwargs) -> None:
    with _LOCK:
        _JOBS.setdefault(job_id, {})
        _JOBS[job_id].update(kwargs)


def start_local_analysis(dataset_id: int, user_id: int) -> str:
    job_id = str(uuid.uuid4())
    _set_job(job_id, state="PENDING", info=None, result=None)

    def _run() -> None:
        def progress_update(state: str, meta: dict) -> None:
            _set_job(job_id, state=state, info=meta)

        try:
            result = run_column_analysis(dataset_id, user_id, progress_update)
            _set_job(job_id, state="SUCCESS", result=result, info=None)
        except Exception as exc:
            logger.exception("In-process column analysis failed")
            _set_job(job_id, state="FAILURE", info=str(exc), result=None)

    threading.Thread(
        target=_run,
        daemon=True,
        name=f"column-analysis-{job_id[:8]}",
    ).start()
    return job_id
