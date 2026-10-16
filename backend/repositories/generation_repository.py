from backend.config.database import get_db_connection
from psycopg2.extras import Json


def create_generation_run(
    dataset_id: int,
    model_name: str,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO generation_runs (
                dataset_id,
                status,
                model_name
            )
            VALUES (%s, %s, %s)
            RETURNING run_id
            """,
            (
                dataset_id,
                "running",
                model_name,
            ),
        )

        run_id = cursor.fetchone()[0]

        connection.commit()

        return run_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def save_model_configuration(
    run_id: int,
    model_name: str,
    parameters: dict,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO model_configurations (
                run_id,
                model_name,
                parameters
            )
            VALUES (%s, %s, %s)
            RETURNING configuration_id
            """,
            (
                run_id,
                model_name,
                Json(parameters),
            ),
        )

        configuration_id = cursor.fetchone()[0]

        connection.commit()

        return configuration_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def save_generated_result(
    run_id: int,
    file_name: str,
    file_path: str,
    row_count: int,
    column_count: int,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO generated_results (
                run_id,
                file_name,
                file_path,
                row_count,
                column_count
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING result_id
            """,
            (
                run_id,
                file_name,
                file_path,
                row_count,
                column_count,
            ),
        )

        result_id = cursor.fetchone()[0]

        connection.commit()

        return result_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def update_generation_run_status(
    run_id: int,
    status: str,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE generation_runs
            SET
                status = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE run_id = %s
            """,
            (
                status,
                run_id,
            ),
        )

        connection.commit()

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def get_generated_result_by_run(run_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT result_id, run_id, file_name, file_path,
                   row_count, column_count
            FROM generated_results
            WHERE run_id = %s
            ORDER BY result_id DESC
            LIMIT 1
        """, (run_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "result_id": row[0], "run_id": row[1],
            "file_name": row[2], "file_path": row[3],
            "row_count": row[4], "column_count": row[5],
        }
    finally:
        cur.close()
        conn.close()

def get_generated_result_by_id(
    result_id: int,
):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                gr.result_id,
                gr.run_id,
                gr.file_name,
                gr.file_path,
                gr.row_count,
                gr.column_count,
                grn.dataset_id,
                grn.model_name
            FROM generated_results gr
            JOIN generation_runs grn
                ON gr.run_id = grn.run_id
            WHERE gr.result_id = %s
            """,
            (result_id,),
        )

        row = cur.fetchone()

        if not row:
            return None

        return {
            "result_id": row[0],
            "run_id": row[1],
            "file_name": row[2],
            "file_path": row[3],
            "row_count": row[4],
            "column_count": row[5],
            "dataset_id": row[6],
            "model_name": row[7],
        }

    finally:
        cur.close()
        conn.close()


def get_latest_generated_result_by_dataset_id(dataset_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                gr.result_id,
                gr.run_id,
                gr.file_name,
                gr.file_path,
                gr.row_count,
                gr.column_count,
                grn.dataset_id
            FROM generated_results gr
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            WHERE grn.dataset_id = %s
            ORDER BY gr.result_id DESC
            LIMIT 1
            """,
            (dataset_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "result_id": row[0],
            "run_id": row[1],
            "file_name": row[2],
            "file_path": row[3],
            "row_count": row[4],
            "column_count": row[5],
            "dataset_id": row[6],
        }
    finally:
        cur.close()
        conn.close()


def get_group_peer_generated_result(
    dataset_id: int,
    model_name: str,
    reference_run_id: int,
    reference_result_id: int,
):
    """
    Multi-table generation creates one run per table, all with the same
    model_name ("<algo>_group_<id>") and finished within moments of each
    other. Return the generated result of `dataset_id` that belongs to the
    SAME generation batch as the reference run (closest completion time,
    then closest result_id), or None if that table has no result.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                gr.result_id,
                gr.run_id,
                gr.file_name,
                gr.file_path,
                gr.row_count,
                gr.column_count,
                grn.dataset_id
            FROM generated_results gr
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            WHERE grn.dataset_id = %s
              AND grn.model_name = %s
            ORDER BY
                ABS(EXTRACT(EPOCH FROM (
                    grn.completed_at -
                    (SELECT completed_at FROM generation_runs WHERE run_id = %s)
                ))) ASC NULLS LAST,
                ABS(gr.result_id - %s) ASC,
                gr.result_id DESC
            LIMIT 1
            """,
            (dataset_id, model_name, reference_run_id, reference_result_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "result_id": row[0],
            "run_id": row[1],
            "file_name": row[2],
            "file_path": row[3],
            "row_count": row[4],
            "column_count": row[5],
            "dataset_id": row[6],
        }
    finally:
        cur.close()
        conn.close()


def get_latest_generated_result_for_user(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                gr.result_id,
                gr.run_id,
                gr.file_name,
                gr.file_path,
                gr.row_count,
                gr.column_count,
                grn.dataset_id
            FROM generated_results gr
            JOIN generation_runs grn ON gr.run_id = grn.run_id
            JOIN datasets d ON grn.dataset_id = d.dataset_id
            WHERE d.user_id = %s
            ORDER BY gr.result_id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "result_id": row[0],
            "run_id": row[1],
            "file_name": row[2],
            "file_path": row[3],
            "row_count": row[4],
            "column_count": row[5],
            "dataset_id": row[6],
        }
    finally:
        cur.close()
        conn.close()


def get_algorithm_timing_stats(user_id: int) -> dict:
    """
    Measured generation speed per model from this user's past runs:
    {model_name: {"seconds": total_seconds, "rows": total_rows, "runs": n}}.
    Multi-table runs (model_name like 'ctgan_group_3') are excluded.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                grn.model_name,
                SUM(EXTRACT(EPOCH FROM (grn.completed_at - grn.started_at))) AS secs,
                SUM(gr.row_count) AS total_rows,
                COUNT(*) AS runs
            FROM generation_runs grn
            JOIN generated_results gr ON gr.run_id = grn.run_id
            JOIN datasets d ON d.dataset_id = grn.dataset_id
            WHERE d.user_id = %s
              AND grn.completed_at IS NOT NULL
              AND grn.started_at IS NOT NULL
              AND gr.row_count > 0
              AND grn.model_name NOT LIKE %s
            GROUP BY grn.model_name
            """,
            (user_id, "%\\_group\\_%"),
        )
        return {
            r[0]: {
                "seconds": float(r[1] or 0),
                "rows": int(r[2] or 0),
                "runs": int(r[3] or 0),
            }
            for r in cursor.fetchall()
        }
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()