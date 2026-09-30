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