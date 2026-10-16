"""
Repository for persistent generation jobs and checkpoints.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import Json

from backend.config.database import get_db_connection

logger = logging.getLogger(__name__)


_TABLE_READY = False


def ensure_generation_jobs_table() -> None:
    """Ensure the generation_jobs table and indexes exist (DDL runs once per process)."""
    global _TABLE_READY
    if _TABLE_READY:
        return
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS generation_jobs (
                job_id VARCHAR(100) PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
                file_name VARCHAR(255) NOT NULL,
                model_name VARCHAR(100) NOT NULL,
                llm_model VARCHAR(100),
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                total_rows INTEGER NOT NULL,
                generated_rows INTEGER NOT NULL DEFAULT 0,
                current_batch INTEGER NOT NULL DEFAULT 0,
                total_batches INTEGER NOT NULL DEFAULT 0,
                progress_percent INTEGER NOT NULL DEFAULT 0,
                stage VARCHAR(100) DEFAULT 'prepare',
                stage_message TEXT,
                parameters JSONB,
                column_configurations JSONB,
                checkpoint_path TEXT,
                result_id INTEGER REFERENCES generated_results(result_id) ON DELETE SET NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checkpoint_at TIMESTAMP,
                completed_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_gen_jobs_user ON generation_jobs(user_id);
            CREATE INDEX IF NOT EXISTS idx_gen_jobs_status ON generation_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_gen_jobs_dataset ON generation_jobs(dataset_id);
            ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS control_request VARCHAR(20);
            ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMP;
            """
        )
        conn.commit()
        _TABLE_READY = True
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.exception("Failed to ensure generation_jobs table: %s", exc)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def create_generation_job(
    *,
    job_id: str,
    user_id: int,
    dataset_id: int,
    file_name: str,
    model_name: str,
    total_rows: int,
    parameters: Optional[dict] = None,
    column_configurations: Optional[list] = None,
    llm_model: Optional[str] = None,
) -> dict[str, Any]:
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO generation_jobs (
                job_id,
                user_id,
                dataset_id,
                file_name,
                model_name,
                llm_model,
                status,
                total_rows,
                generated_rows,
                current_batch,
                total_batches,
                progress_percent,
                stage,
                stage_message,
                parameters,
                column_configurations,
                created_at,
                updated_at,
                last_heartbeat_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, 0, 0, 0, 0, 'prepare',
                    'Queued for generation', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP)
            RETURNING job_id
            """,
            (
                job_id,
                user_id,
                dataset_id,
                file_name,
                model_name,
                llm_model,
                total_rows,
                Json(parameters or {}),
                Json(column_configurations or []),
            ),
        )
        conn.commit()
        return get_generation_job(job_id)
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _row_to_job_dict(row: tuple, cols: list[str]) -> dict[str, Any]:
    data = dict(zip(cols, row))
    total = data.get("total_rows") or 0
    generated = data.get("generated_rows") or 0
    data["remaining_rows"] = max(0, total - generated)

    # Format datetimes
    for k in ("created_at", "updated_at", "last_checkpoint_at", "completed_at"):
        val = data.get(k)
        if isinstance(val, datetime):
            # Stored as naive UTC; mark it explicitly so browsers convert
            # to the viewer's local timezone instead of showing UTC as-is.
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            data[k] = val.isoformat()

    return data


_SELECT_COLS = (
    "job_id, user_id, dataset_id, file_name, model_name, llm_model, status, "
    "total_rows, generated_rows, current_batch, total_batches, progress_percent, "
    "stage, stage_message, parameters, column_configurations, checkpoint_path, "
    "result_id, error_message, created_at, updated_at, last_checkpoint_at, completed_at"
)
_COL_LIST = [c.strip() for c in _SELECT_COLS.split(",")]


def get_generation_job(job_id: str) -> Optional[dict[str, Any]]:
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {_SELECT_COLS} FROM generation_jobs WHERE job_id = %s",
            (job_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_job_dict(row, _COL_LIST)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_generation_job_for_user(job_id: str, user_id: int) -> Optional[dict[str, Any]]:
    job = get_generation_job(job_id)
    if job and job.get("user_id") == user_id:
        return job
    return None


def list_generation_jobs_for_user(
    user_id: int,
    status: Optional[str] = None,
    dataset_id: Optional[int] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        conditions = ["user_id = %s"]
        params: list[Any] = [user_id]

        if status:
            conditions.append("LOWER(status) = LOWER(%s)")
            params.append(status)

        if dataset_id is not None:
            conditions.append("dataset_id = %s")
            params.append(dataset_id)

        where_clause = " AND ".join(conditions)
        query = (
            f"SELECT {_SELECT_COLS} FROM generation_jobs "
            f"WHERE {where_clause} ORDER BY updated_at DESC LIMIT %s"
        )
        params.append(limit)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [_row_to_job_dict(r, _COL_LIST) for r in rows]
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def list_incomplete_jobs_for_user(user_id: int) -> list[dict[str, Any]]:
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT {_SELECT_COLS} FROM generation_jobs
            WHERE user_id = %s AND LOWER(status) IN ('pending', 'running', 'paused', 'interrupted')
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return [_row_to_job_dict(r, _COL_LIST) for r in rows]
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def update_generation_job_progress(
    *,
    job_id: str,
    generated_rows: int,
    current_batch: int,
    total_batches: int,
    progress_percent: int,
    stage: str,
    stage_message: str,
    checkpoint_path: Optional[str] = None,
) -> None:
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE generation_jobs
            SET
                generated_rows = %s,
                current_batch = %s,
                total_batches = %s,
                progress_percent = %s,
                stage = %s,
                stage_message = %s,
                checkpoint_path = COALESCE(%s, checkpoint_path),
                last_checkpoint_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = %s
            """,
            (
                generated_rows,
                current_batch,
                total_batches,
                progress_percent,
                stage,
                stage_message,
                checkpoint_path,
                job_id,
            ),
        )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def update_generation_job_status(
    *,
    job_id: str,
    status: str,
    error_message: Optional[str] = None,
    result_id: Optional[int] = None,
    stage_message: Optional[str] = None,
) -> None:
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        completed_clause = (
            ", completed_at = CURRENT_TIMESTAMP"
            if status.lower() == "completed"
            else ""
        )
        cur.execute(
            f"""
            UPDATE generation_jobs
            SET
                status = %s,
                error_message = %s,
                result_id = COALESCE(%s, result_id),
                stage_message = COALESCE(%s, stage_message),
                updated_at = CURRENT_TIMESTAMP
                {completed_clause}
            WHERE job_id = %s
            """,
            (
                status.lower(),
                error_message,
                result_id,
                stage_message,
                job_id,
            ),
        )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def delete_generation_job(job_id: str, user_id: int) -> bool:
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM generation_jobs WHERE job_id = %s AND user_id = %s",
            (job_id, user_id),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def recover_interrupted_jobs() -> int:
    """
    Called upon backend startup: detects any job left in 'running' or 'pending'
    and marks it 'interrupted' so the user can cleanly resume from checkpoints.
    """
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE generation_jobs
            SET
                status = 'interrupted',
                control_request = NULL,
                stage_message = 'Interrupted by server restart. Ready to resume.',
                updated_at = CURRENT_TIMESTAMP
            WHERE LOWER(status) IN ('running', 'pending')
            """
        )
        count = cur.rowcount
        conn.commit()
        if count > 0:
            logger.info("Recovered %d interrupted generation job(s) on startup", count)
        return count
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.exception("Failed to recover interrupted jobs: %s", exc)
        return 0
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



# ---------------------------------------------------------------------------
# Cross-process job control (pause / cancel) and atomic state transitions.
#
# Control requests live in the database instead of a Python dict so they work
# when the generation runs in a Celery worker (a different process than the API).
# ---------------------------------------------------------------------------

_CLAIMABLE_FOR_RESUME = ("paused", "interrupted", "failed")
_ACTIVE_STATES = ("pending", "running")


def set_job_control_request(
    job_id: str,
    request: str,
    user_id: Optional[int] = None,
) -> bool:
    """Record a 'pause' or 'cancel' request for a pending/running job.

    Returns True when a row was updated (the job is active), False otherwise.
    """
    if request not in ("pause", "cancel"):
        raise ValueError(f"Unsupported control request: {request}")
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        sql = (
            "UPDATE generation_jobs SET control_request = %s, updated_at = CURRENT_TIMESTAMP "
            "WHERE job_id = %s AND LOWER(status) IN ('pending', 'running')"
        )
        params: list[Any] = [request, job_id]
        if user_id is not None:
            sql += " AND user_id = %s"
            params.append(user_id)
        cur.execute(sql, tuple(params))
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_job_control_request(job_id: str) -> Optional[str]:
    """Return 'pause' / 'cancel' / None.

    A job whose row no longer exists (discarded by the user) is treated as
    'cancel' so a still-running worker stops instead of generating for nobody.
    """
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT control_request FROM generation_jobs WHERE job_id = %s",
            (job_id,),
        )
        row = cur.fetchone()
        if row is None:
            return "cancel"
        return row[0]
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def clear_job_control_request(job_id: str) -> None:
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE generation_jobs SET control_request = NULL WHERE job_id = %s",
            (job_id,),
        )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def claim_job_for_resume(job_id: str, user_id: int) -> bool:
    """Atomically move a paused/interrupted/failed job to 'running'.

    Only ONE concurrent caller can win; everyone else gets False. This is what
    prevents a double-click on Resume from starting two workers on one job.
    """
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE generation_jobs
            SET status = 'running',
                control_request = NULL,
                error_message = NULL,
                stage_message = 'Resuming generation job...',
                last_heartbeat_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = %s
              AND user_id = %s
              AND LOWER(status) IN %s
            RETURNING job_id
            """,
            (job_id, user_id, _CLAIMABLE_FOR_RESUME),
        )
        won = cur.fetchone() is not None
        conn.commit()
        return won
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def claim_job_for_restart(job_id: str, user_id: int) -> bool:
    """Atomically reset a non-active job to row 0 and mark it 'running'."""
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE generation_jobs
            SET status = 'running',
                control_request = NULL,
                error_message = NULL,
                generated_rows = 0,
                current_batch = 0,
                progress_percent = 0,
                checkpoint_path = NULL,
                last_checkpoint_at = NULL,
                completed_at = NULL,
                stage_message = 'Restarting generation from beginning...',
                last_heartbeat_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = %s
              AND user_id = %s
              AND LOWER(status) NOT IN %s
            RETURNING job_id
            """,
            (job_id, user_id, _ACTIVE_STATES),
        )
        won = cur.fetchone() is not None
        conn.commit()
        return won
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Presence ("heartbeat"): is a signed-in browser still watching this job?
#
# Every authenticated status/list request from the app refreshes
# last_heartbeat_at for the user's active jobs. If it goes stale the worker
# pauses itself (see generation_checkpoint_service.check_job_control), so a
# closed tab / expired token / sign-out never leaves a run going unattended
# or loses its progress.
# ---------------------------------------------------------------------------

def touch_job_heartbeat(job_id: str, user_id: Optional[int] = None) -> None:
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        sql = (
            "UPDATE generation_jobs SET last_heartbeat_at = CURRENT_TIMESTAMP "
            "WHERE job_id = %s AND LOWER(status) IN ('pending', 'running')"
        )
        params: list[Any] = [job_id]
        if user_id is not None:
            sql += " AND user_id = %s"
            params.append(user_id)
        cur.execute(sql, tuple(params))
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def touch_user_active_jobs(user_id: int) -> None:
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE generation_jobs SET last_heartbeat_at = CURRENT_TIMESTAMP "
            "WHERE user_id = %s AND LOWER(status) IN ('pending', 'running')",
            (user_id,),
        )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def clear_job_heartbeat(job_id: str) -> None:
    """Opt a job out of the idle check (synchronous runs nobody polls)."""
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE generation_jobs SET last_heartbeat_at = NULL WHERE job_id = %s",
            (job_id,),
        )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def is_job_presence_stale(job_id: str, max_age_seconds: float) -> bool:
    """True when the job has a heartbeat and it is older than max_age_seconds."""
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT last_heartbeat_at IS NOT NULL
                   AND last_heartbeat_at < (CURRENT_TIMESTAMP - make_interval(secs => %s))
            FROM generation_jobs
            WHERE job_id = %s
            """,
            (float(max_age_seconds), job_id),
        )
        row = cur.fetchone()
        return bool(row and row[0])
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def pause_active_jobs_for_user(user_id: int) -> list[str]:
    """Ask every pending/running job of this user to pause. Returns their ids."""
    ensure_generation_jobs_table()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE generation_jobs
            SET control_request = 'pause', updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND LOWER(status) IN ('pending', 'running')
            RETURNING job_id
            """,
            (user_id,),
        )
        ids = [r[0] for r in cur.fetchall()]
        conn.commit()
        return ids
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
