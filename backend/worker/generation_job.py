import logging
import threading
import uuid
from typing import Any, Callable, Optional

from backend.repositories.generation_job_repository import (
    get_generation_job,
    update_generation_job_status,
)
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
    job_id: Optional[str] = None,
    resume: bool = False,
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
        job_id=job_id,
        resume=resume,
    )


def get_local_generation_job(job_id: str) -> Optional[dict]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            return dict(job)

    # Fallback to database for persisted / recovered jobs after server restart
    try:
        db_job = get_generation_job(job_id)
        if db_job:
            status_map = {
                "pending": "PENDING",
                "running": "PROGRESS",
                "paused": "PAUSED",
                "interrupted": "INTERRUPTED",
                "completed": "SUCCESS",
                "failed": "FAILURE",
                "cancelled": "CANCELLED",
            }
            state = status_map.get(db_job.get("status", "").lower(), "PENDING")
            return {
                "state": state,
                "info": {
                    "stage": db_job.get("stage"),
                    "stage_label": db_job.get("stage_message") or db_job.get("stage"),
                    "percent": db_job.get("progress_percent", 0),
                    "message": db_job.get("stage_message"),
                    "generated_rows": db_job.get("generated_rows", 0),
                    "total_rows": db_job.get("total_rows", 0),
                    "current_batch": db_job.get("current_batch", 0),
                    "total_batches": db_job.get("total_batches", 0),
                },
                "result": {
                    "result_id": db_job.get("result_id"),
                    "file_name": db_job.get("file_name"),
                    "row_count": db_job.get("generated_rows"),
                }
                if state == "SUCCESS"
                else None,
                "error": db_job.get("error_message"),
            }
    except Exception as exc:
        logger.debug("Could not read job %s from DB: %s", job_id, exc)

    return None


def _set_job(job_id: str, **kwargs) -> None:
    with _LOCK:
        _JOBS.setdefault(job_id, {})
        _JOBS[job_id].update(kwargs)


def start_local_generation(
    dataset_id: int,
    model_name: str,
    user_id: int,
    parameters: Optional[dict] = None,
    job_id: Optional[str] = None,
    resume: bool = False,
) -> str:
    jid = job_id or str(uuid.uuid4())
    _set_job(jid, state="PENDING", info=None, result=None)

    def _run() -> None:
        def progress_update(state: str, meta: dict) -> None:
            _set_job(jid, state=state, info=meta)

        try:
            update_generation_job_status(
                job_id=jid,
                status="running",
                stage_message="Generation in progress",
            )
            result = run_generation(
                dataset_id=dataset_id,
                model_name=model_name,
                user_id=user_id,
                parameters=parameters,
                progress_update=progress_update,
                job_id=jid,
                resume=resume,
            )
            status_flag = result.get("status") if isinstance(result, dict) else None
            if status_flag == "paused":
                _set_job(jid, state="PAUSED", info=result, result=None)
            elif status_flag == "cancelled":
                _set_job(jid, state="CANCELLED", info=result, result=None)
            else:
                _set_job(jid, state="SUCCESS", result=result, info=None)
        except Exception as exc:
            logger.exception("In-process generation failed for job %s", jid)
            _set_job(jid, state="FAILURE", info=str(exc), result=None)
            try:
                update_generation_job_status(
                    job_id=jid,
                    status="failed",
                    error_message=str(exc),
                )
            except Exception:
                pass

    threading.Thread(
        target=_run,
        daemon=True,
        name=f"generation-{jid[:8]}",
    ).start()
    return jid


__all__ = [
    "get_local_generation_job",
    "redis_is_available",
    "run_generation",
    "start_local_generation",
]


def run_multi_table_generation(
    group_id: int,
    model_name: str,
    user_id: int,
    parameters: Optional[dict] = None,
    progress_update: Optional[Callable[[str, dict], None]] = None,
    job_id: Optional[str] = None,
    resume: bool = False,
) -> dict:
    """Run multi-table generation using the same pause/resume job lifecycle."""
    from backend.services.multi_table_generation_service import generate_linked_tables

    def progress_callback(meta: dict) -> None:
        if progress_update:
            progress_update("PROGRESS", meta)

    result = generate_linked_tables(
        group_id=group_id,
        model_name=model_name,
        parameters=parameters,
        job_id=job_id,
        resume=resume,
        progress_callback=progress_callback,
    )
    if result.get("status") in {"paused", "cancelled"}:
        return result

    # Celery's JSON serializer cannot serialize DataFrames. Return the same
    # public shape as the synchronous multi-table endpoint.
    return {
        "status": "success",
        "message": "Multi-table synthetic data generated successfully.",
        "group_id": result["group_id"],
        "model_name": result["model_name"],
        "tables": {
            str(dataset_id): {
                "dataset_id": table["dataset_id"],
                "source_filename": table.get("source_filename"),
                "file_name": table.get("file_name"),
                "file_path": table.get("file_path"),
                "row_count": table.get("row_count"),
                "column_count": table.get("column_count"),
                "result_id": table.get("result_id"),
                "run_id": table.get("run_id"),
            }
            for dataset_id, table in result["tables"].items()
        },
        "relationships": result.get("relationships", []),
        "referential_integrity": bool(result.get("integrity_report", {}).get("passed", False)),
        "integrity_report": result.get("integrity_report"),
    }


def start_local_multi_table_generation(
    group_id: int,
    model_name: str,
    user_id: int,
    parameters: Optional[dict] = None,
    job_id: Optional[str] = None,
    resume: bool = False,
) -> str:
    jid = job_id or str(uuid.uuid4())
    _set_job(jid, state="PENDING", info=None, result=None)

    def _run() -> None:
        def progress_update(state: str, meta: dict) -> None:
            _set_job(jid, state=state, info=meta)

        try:
            update_generation_job_status(job_id=jid, status="running", stage_message="Multi-table generation in progress")
            result = run_multi_table_generation(
                group_id=group_id,
                model_name=model_name,
                user_id=user_id,
                parameters=parameters,
                progress_update=progress_update,
                job_id=jid,
                resume=resume,
            )
            if result.get("status") == "paused":
                _set_job(jid, state="PAUSED", info=result, result=None)
                update_generation_job_status(job_id=jid, status="paused", stage_message="Paused after saving multi-table checkpoint")
            elif result.get("status") == "cancelled":
                _set_job(jid, state="CANCELLED", info=result, result=None)
                update_generation_job_status(job_id=jid, status="cancelled", stage_message="Multi-table generation cancelled")
            else:
                _set_job(jid, state="SUCCESS", result=result, info=None)
                first_result = next((t.get("result_id") for t in result.get("tables", {}).values() if t.get("result_id")), None)
                update_generation_job_status(job_id=jid, status="completed", result_id=first_result, stage_message="Multi-table generation completed")
            if result.get("status") not in {"paused", "cancelled"}:
                from backend.services.generation_checkpoint_service import delete_checkpoint
                delete_checkpoint(jid)
        except Exception as exc:
            logger.exception("Multi-table generation failed for job %s", jid)
            _set_job(jid, state="FAILURE", info=str(exc), result=None)
            try:
                update_generation_job_status(job_id=jid, status="failed", error_message=str(exc), stage_message="Multi-table generation failed")
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True, name=f"multi-generation-{jid[:8]}").start()
    return jid
