"""
Service for managing durable generation checkpoints and job control (pause, resume, cancel).
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

CHECKPOINT_BASE_DIR = Path("data/checkpoints")

_CONTROL_LOCK = threading.Lock()
# {job_id: "pause" | "cancel" | None}
_JOB_CONTROLS: dict[str, str] = {}
# {job_id: "idle"} - why the worker paused itself (read once by the pipeline)
_AUTO_PAUSE_REASONS: dict[str, str] = {}


def get_checkpoint_dir(job_id: str) -> Path:
    directory = CHECKPOINT_BASE_DIR / str(job_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_checkpoint_file(job_id: str) -> Path:
    return get_checkpoint_dir(job_id) / "checkpoint.csv"


def load_checkpoint_rows(job_id: str) -> Optional[pd.DataFrame]:
    """Load already generated rows from the checkpoint file if present."""
    file_path = get_checkpoint_file(job_id)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(file_path)
        return df
    except Exception as exc:
        logger.warning("Could not read checkpoint file for job %s: %s", job_id, exc)
        return None


def save_checkpoint_rows(job_id: str, dataframe: pd.DataFrame) -> str:
    """Write accumulated generated rows to durable checkpoint file."""
    file_path = get_checkpoint_file(job_id)
    dataframe.to_csv(file_path, index=False)
    return str(file_path)


def delete_checkpoint(job_id: str) -> None:
    """Remove checkpoint directory and files for a discarded or completed job."""
    directory = CHECKPOINT_BASE_DIR / str(job_id)
    if directory.exists():
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except Exception as exc:
            logger.warning("Could not delete checkpoint dir %s: %s", directory, exc)


def _persist_control(job_id: str, request: str) -> None:
    """Best effort write to the DB so a worker in ANOTHER process sees it."""
    try:
        from backend.repositories.generation_job_repository import (
            set_job_control_request,
        )

        set_job_control_request(job_id, request)
    except Exception as exc:  # DB hiccup must not break the in-process path
        logger.warning("Could not persist %s request for job %s: %s", request, job_id, exc)


def request_job_pause(job_id: str) -> None:
    with _CONTROL_LOCK:
        _JOB_CONTROLS[job_id] = "pause"
    _persist_control(job_id, "pause")


def request_job_cancel(job_id: str) -> None:
    with _CONTROL_LOCK:
        _JOB_CONTROLS[job_id] = "cancel"
    _persist_control(job_id, "cancel")


def clear_local_job_control(job_id: str) -> None:
    """Drop only the in-process flag (leaves a DB request, e.g. an early pause, intact)."""
    with _CONTROL_LOCK:
        _JOB_CONTROLS.pop(job_id, None)


def clear_job_control(job_id: str) -> None:
    with _CONTROL_LOCK:
        _JOB_CONTROLS.pop(job_id, None)
    try:
        from backend.repositories.generation_job_repository import (
            clear_job_control_request,
        )

        clear_job_control_request(job_id)
    except Exception as exc:
        logger.warning("Could not clear control request for job %s: %s", job_id, exc)


def check_job_control(job_id: str, idle_pause: bool = False) -> Optional[str]:
    """Return 'pause' | 'cancel' | None. Memory first, then the database.

    With idle_pause=True a job whose browser stopped checking in (tab closed,
    signed out, token expired, ...) also yields 'pause'. Callers only pass it
    AFTER a batch has been checkpointed, so the trained model is never thrown
    away for nothing and no finished rows are ever lost.
    """
    with _CONTROL_LOCK:
        local = _JOB_CONTROLS.get(job_id)
    if local:
        return local
    try:
        from backend.repositories.generation_job_repository import (
            get_job_control_request,
        )

        db_request = get_job_control_request(job_id)
    except Exception as exc:
        logger.warning("Could not read control request for job %s: %s", job_id, exc)
        return None

    if db_request:
        return db_request

    if idle_pause:
        try:
            from backend.config.settings import GENERATION_IDLE_PAUSE_SECONDS

            if GENERATION_IDLE_PAUSE_SECONDS > 0:
                from backend.repositories.generation_job_repository import (
                    is_job_presence_stale,
                )

                if is_job_presence_stale(job_id, GENERATION_IDLE_PAUSE_SECONDS):
                    with _CONTROL_LOCK:
                        _AUTO_PAUSE_REASONS[job_id] = "idle"
                    return "pause"
        except Exception as exc:
            logger.warning("Idle check failed for job %s: %s", job_id, exc)
    return None


def pop_auto_pause_reason(job_id: str) -> Optional[str]:
    """Why the worker paused itself ('idle'), or None for a user-requested pause."""
    with _CONTROL_LOCK:
        return _AUTO_PAUSE_REASONS.pop(job_id, None)
