from __future__ import annotations

import logging
from typing import Any

from backend.config.database import get_db_connection

logger = logging.getLogger(__name__)


def save_report(
    result_id: int,
    report_name: str,
    report_path: str,
) -> dict[str, Any]:
    """
    Save or update a generated report in the reports table.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if report already exists for this result_id
        cursor.execute(
            """
            SELECT report_id
            FROM reports
            WHERE result_id = %s
            ORDER BY report_id DESC
            LIMIT 1
            """,
            (result_id,),
        )
        existing = cursor.fetchone()

        if existing:
            report_id = existing[0]
            cursor.execute(
                """
                UPDATE reports
                SET
                    report_name = %s,
                    report_path = %s,
                    generated_at = CURRENT_TIMESTAMP
                WHERE report_id = %s
                RETURNING report_id, result_id, report_name, report_path, generated_at
                """,
                (report_name, report_path, report_id),
            )
            row = cursor.fetchone()
        else:
            cursor.execute(
                """
                INSERT INTO reports (
                    result_id,
                    report_name,
                    report_path
                )
                VALUES (%s, %s, %s)
                RETURNING report_id, result_id, report_name, report_path, generated_at
                """,
                (result_id, report_name, report_path),
            )
            row = cursor.fetchone()

        connection.commit()

        return {
            "report_id": row[0],
            "result_id": row[1],
            "report_name": row[2],
            "report_path": row[3],
            "generated_at": row[4].isoformat() if row[4] else None,
        }

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_report_by_result_id(result_id: int) -> dict[str, Any] | None:
    """
    Get the most recent report record for a generated result.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                r.report_id,
                r.result_id,
                r.report_name,
                r.report_path,
                r.generated_at,
                gr.run_id,
                gr.file_name,
                run.dataset_id,
                d.dataset_name
            FROM reports r
            JOIN generated_results gr ON r.result_id = gr.result_id
            JOIN generation_runs run ON gr.run_id = run.run_id
            JOIN datasets d ON run.dataset_id = d.dataset_id
            WHERE r.result_id = %s
            ORDER BY r.report_id DESC
            LIMIT 1
            """,
            (result_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "report_id": row[0],
            "result_id": row[1],
            "report_name": row[2],
            "report_path": row[3],
            "generated_at": row[4].isoformat() if row[4] else None,
            "run_id": row[5],
            "file_name": row[6],
            "dataset_id": row[7],
            "dataset_name": row[8],
        }

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_report_by_id(report_id: int) -> dict[str, Any] | None:
    """
    Get a report record by report_id.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                r.report_id,
                r.result_id,
                r.report_name,
                r.report_path,
                r.generated_at,
                gr.run_id,
                gr.file_name,
                run.dataset_id,
                d.dataset_name,
                d.user_id
            FROM reports r
            JOIN generated_results gr ON r.result_id = gr.result_id
            JOIN generation_runs run ON gr.run_id = run.run_id
            JOIN datasets d ON run.dataset_id = d.dataset_id
            WHERE r.report_id = %s
            """,
            (report_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "report_id": row[0],
            "result_id": row[1],
            "report_name": row[2],
            "report_path": row[3],
            "generated_at": row[4].isoformat() if row[4] else None,
            "run_id": row[5],
            "file_name": row[6],
            "dataset_id": row[7],
            "dataset_name": row[8],
            "user_id": row[9],
        }

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def list_reports_for_user(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """
    List reports accessible to a specific user.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                r.report_id,
                r.result_id,
                r.report_name,
                r.report_path,
                r.generated_at,
                gr.run_id,
                gr.file_name,
                run.dataset_id,
                d.dataset_name,
                ev.overall_score
            FROM reports r
            JOIN generated_results gr ON r.result_id = gr.result_id
            JOIN generation_runs run ON gr.run_id = run.run_id
            JOIN datasets d ON run.dataset_id = d.dataset_id
            LEFT JOIN evaluation_results ev ON r.result_id = ev.result_id
            WHERE d.user_id = %s
            ORDER BY r.generated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall()
        reports = []
        for row in rows:
            reports.append(
                {
                    "report_id": row[0],
                    "result_id": row[1],
                    "report_name": row[2],
                    "report_path": row[3],
                    "generated_at": row[4].isoformat() if row[4] else None,
                    "run_id": row[5],
                    "file_name": row[6],
                    "dataset_id": row[7],
                    "dataset_name": row[8],
                    "overall_score": float(row[9]) if row[9] is not None else None,
                }
            )
        return reports

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
