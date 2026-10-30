"""Persistence for human feedback on Improve Quality outcomes."""
from __future__ import annotations

import logging
from typing import Any

from psycopg2.extras import Json
from backend.config.database import get_db_connection

logger = logging.getLogger(__name__)


def save_quality_feedback(
    *,
    user_id: int,
    dataset_id: int,
    result_id: int,
    improved_result_id: int | None,
    feedback: str,
    focus_area: str | None,
    comment: str | None,
) -> dict[str, Any]:
    """Create the feedback table if needed and persist one feedback event."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quality_improvement_feedback (
                feedback_id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                dataset_id BIGINT NOT NULL,
                result_id BIGINT NOT NULL,
                improved_result_id BIGINT NULL,
                feedback VARCHAR(32) NOT NULL,
                focus_area VARCHAR(80) NULL,
                comment TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO quality_improvement_feedback
                (user_id, dataset_id, result_id, improved_result_id,
                 feedback, focus_area, comment)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING feedback_id, created_at
            """,
            (
                user_id, dataset_id, result_id, improved_result_id,
                feedback, focus_area, comment,
            ),
        )
        row = cursor.fetchone()
        connection.commit()
        return {
            "feedback_id": row[0],
            "created_at": row[1].isoformat() if row[1] else None,
        }
    except Exception:
        if connection:
            connection.rollback()
        logger.exception("Could not save quality improvement feedback")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



def get_recent_quality_feedback(
    *,
    user_id: int,
    dataset_id: int,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return recent user feedback for this user's dataset, newest first."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT feedback, focus_area, comment, created_at
            FROM quality_improvement_feedback
            WHERE user_id = %s AND dataset_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, dataset_id, max(1, min(int(limit), 20))),
        )
        return [
            {
                "feedback": row[0],
                "focus_area": row[1],
                "comment": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
            }
            for row in cursor.fetchall()
        ]
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
