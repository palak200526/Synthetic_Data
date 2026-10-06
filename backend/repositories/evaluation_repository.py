from __future__ import annotations

import json
import logging
from typing import Any

from psycopg2.extras import Json

from backend.config.database import get_db_connection

logger = logging.getLogger(__name__)


def save_evaluation_result(
    result_id: int,
    utility_metrics: dict,
    privacy_metrics: dict | None = None,
    overall_score: float | None = None,
) -> dict[str, Any]:
    """
    US-026: Persist evaluation results into evaluation_results table.
    Associates the evaluation with result_id, and indirectly with
    generation_run, model, and dataset.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if record already exists for result_id
        cursor.execute(
            """
            SELECT evaluation_id
            FROM evaluation_results
            WHERE result_id = %s
            ORDER BY evaluation_id DESC
            LIMIT 1
            """,
            (result_id,),
        )
        existing = cursor.fetchone()

        if existing:
            eval_id = existing[0]
            cursor.execute(
                """
                UPDATE evaluation_results
                SET
                    utility_metrics = %s,
                    privacy_metrics = %s,
                    overall_score = %s,
                    evaluated_at = CURRENT_TIMESTAMP
                WHERE evaluation_id = %s
                RETURNING evaluation_id, evaluated_at
                """,
                (
                    Json(utility_metrics),
                    Json(privacy_metrics) if privacy_metrics is not None else None,
                    overall_score,
                    eval_id,
                ),
            )
            row = cursor.fetchone()
        else:
            cursor.execute(
                """
                INSERT INTO evaluation_results (
                    result_id,
                    utility_metrics,
                    privacy_metrics,
                    overall_score,
                    evaluated_at
                )
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING evaluation_id, evaluated_at
                """,
                (
                    result_id,
                    Json(utility_metrics),
                    Json(privacy_metrics) if privacy_metrics is not None else None,
                    overall_score,
                ),
            )
            row = cursor.fetchone()

        connection.commit()

        return {
            "evaluation_id": row[0],
            "result_id": result_id,
            "overall_score": float(overall_score) if overall_score is not None else None,
            "evaluated_at": row[1].isoformat() if row and row[1] else None,
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


def get_evaluation_by_result_id(result_id: int) -> dict[str, Any] | None:
    """
    Retrieve evaluation results by result_id with associated
    generation run, model, and dataset details.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                er.evaluation_id,
                er.result_id,
                gr.run_id,
                grn.dataset_id,
                d.dataset_name,
                grn.model_name,
                gr.file_name,
                gr.file_path,
                er.utility_metrics,
                er.privacy_metrics,
                er.overall_score,
                er.evaluated_at
            FROM evaluation_results er
            JOIN generated_results gr ON er.result_id = gr.result_id
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            WHERE er.result_id = %s
            ORDER BY er.evaluation_id DESC
            LIMIT 1
            """,
            (result_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "evaluation_id": row[0],
            "result_id": row[1],
            "run_id": row[2],
            "dataset_id": row[3],
            "dataset_name": row[4],
            "model_name": row[5],
            "file_name": row[6],
            "file_path": row[7],
            "utility_metrics": row[8],
            "privacy_metrics": row[9],
            "overall_score": float(row[10]) if row[10] is not None else None,
            "evaluated_at": row[11].isoformat() if row[11] else None,
        }

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_evaluation_by_run_id(run_id: int) -> dict[str, Any] | None:
    """Retrieve evaluation by generation run_id."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                er.evaluation_id,
                er.result_id,
                gr.run_id,
                grn.dataset_id,
                d.dataset_name,
                grn.model_name,
                gr.file_name,
                gr.file_path,
                er.utility_metrics,
                er.privacy_metrics,
                er.overall_score,
                er.evaluated_at
            FROM evaluation_results er
            JOIN generated_results gr ON er.result_id = gr.result_id
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            WHERE grn.run_id = %s
            ORDER BY er.evaluation_id DESC
            LIMIT 1
            """,
            (run_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "evaluation_id": row[0],
            "result_id": row[1],
            "run_id": row[2],
            "dataset_id": row[3],
            "dataset_name": row[4],
            "model_name": row[5],
            "file_name": row[6],
            "file_path": row[7],
            "utility_metrics": row[8],
            "privacy_metrics": row[9],
            "overall_score": float(row[10]) if row[10] is not None else None,
            "evaluated_at": row[11].isoformat() if row[11] else None,
        }

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_evaluations_by_dataset_id(dataset_id: int) -> list[dict[str, Any]]:
    """Retrieve all evaluation records for a dataset."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                er.evaluation_id,
                er.result_id,
                gr.run_id,
                grn.dataset_id,
                d.dataset_name,
                grn.model_name,
                gr.file_name,
                gr.file_path,
                er.utility_metrics,
                er.privacy_metrics,
                er.overall_score,
                er.evaluated_at
            FROM evaluation_results er
            JOIN generated_results gr ON er.result_id = gr.result_id
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            WHERE grn.dataset_id = %s
            ORDER BY er.evaluated_at DESC
            """,
            (dataset_id,),
        )
        rows = cursor.fetchall()

        return [
            {
                "evaluation_id": row[0],
                "result_id": row[1],
                "run_id": row[2],
                "dataset_id": row[3],
                "dataset_name": row[4],
                "model_name": row[5],
                "file_name": row[6],
                "file_path": row[7],
                "utility_metrics": row[8],
                "privacy_metrics": row[9],
                "overall_score": float(row[10]) if row[10] is not None else None,
                "evaluated_at": row[11].isoformat() if row[11] else None,
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_dashboard_summary(user_id: int) -> dict[str, Any]:
    """Retrieve aggregated dashboard stats and recent entities for a user."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Total datasets count
        cursor.execute(
            "SELECT COUNT(*) FROM datasets WHERE user_id = %s",
            (user_id,),
        )
        total_datasets = cursor.fetchone()[0]

        # Total generations count
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM generation_runs grn
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            WHERE d.user_id = %s
            """,
            (user_id,),
        )
        total_generations = cursor.fetchone()[0]

        # Total evaluations count and average score
        cursor.execute(
            """
            SELECT COUNT(*), AVG(er.overall_score)
            FROM evaluation_results er
            JOIN generated_results gr ON er.result_id = gr.result_id
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            WHERE d.user_id = %s AND er.overall_score IS NOT NULL
            """,
            (user_id,),
        )
        eval_row = cursor.fetchone()
        total_evaluations = eval_row[0] if eval_row else 0
        avg_score = round(float(eval_row[1]), 2) if eval_row and eval_row[1] is not None else None

        # Recent datasets
        cursor.execute(
            """
            SELECT dataset_id, dataset_name, row_count, column_count, uploaded_at
            FROM datasets
            WHERE user_id = %s
            ORDER BY uploaded_at DESC
            LIMIT 5
            """,
            (user_id,),
        )
        recent_datasets = [
            {
                "dataset_id": r[0],
                "name": r[1],
                "rows": r[2],
                "columns": r[3],
                "uploaded_at": r[4].isoformat() if r[4] else None,
            }
            for r in cursor.fetchall()
        ]

        # Recent generations
        cursor.execute(
            """
            SELECT grn.run_id, grn.dataset_id, grn.model_name, grn.status, grn.started_at, gr.result_id
            FROM generation_runs grn
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            LEFT JOIN generated_results gr ON grn.run_id = gr.run_id
            WHERE d.user_id = %s
            ORDER BY grn.started_at DESC
            LIMIT 5
            """,
            (user_id,),
        )
        recent_generations = [
            {
                "run_id": r[0],
                "dataset_id": r[1],
                "model_name": r[2],
                "status": r[3],
                "started_at": r[4].isoformat() if r[4] else None,
                "result_id": r[5],
            }
            for r in cursor.fetchall()
        ]

        # Recent evaluations
        cursor.execute(
            """
            SELECT er.evaluation_id, er.result_id, grn.dataset_id, grn.model_name, er.overall_score, er.evaluated_at
            FROM evaluation_results er
            JOIN generated_results gr ON er.result_id = gr.result_id
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            WHERE d.user_id = %s
            ORDER BY er.evaluated_at DESC
            LIMIT 5
            """,
            (user_id,),
        )
        recent_evaluations = [
            {
                "evaluation_id": r[0],
                "result_id": r[1],
                "dataset_id": r[2],
                "model_name": r[3],
                "overall_score": float(r[4]) if r[4] is not None else None,
                "evaluated_at": r[5].isoformat() if r[5] else None,
            }
            for r in cursor.fetchall()
        ]

        return {
            "total_datasets": total_datasets,
            "total_generations": total_generations,
            "total_evaluations": total_evaluations,
            "average_score": avg_score,
            "recent_datasets": recent_datasets,
            "recent_generations": recent_generations,
            "recent_evaluations": recent_evaluations,
        }

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
