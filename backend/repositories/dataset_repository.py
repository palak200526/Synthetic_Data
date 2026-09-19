from backend.config.database import get_db_connection
import json


def create_dataset(
    filename,
    row_count,
    column_count,
    session_id,
    group_id=None,
    domain_type=None
):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO datasets (
                dataset_name,
                file_name,
                file_type,
                row_count,
                column_count,
                session_id,
                group_id,
                domain_type
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING dataset_id
            """,
            (
                filename,
                filename,
                filename.split(".")[-1].lower(),
                row_count,
                column_count,
                session_id,
                group_id,
                domain_type,
            )
        )

        dataset_id = cursor.fetchone()[0]

        connection.commit()

        return dataset_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

def get_dataset_filename(dataset_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT file_name
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,),
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Dataset with ID {dataset_id} does not exist."
            )

        return result[0]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

def save_dataset_profile(dataset_id: int, profile_data: dict):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO dataset_profiles (
                dataset_id,
                profile_data
            )
            VALUES (%s, %s)
            RETURNING profile_id
            """,
            (
                dataset_id,
                json.dumps(profile_data),
            ),
        )

        profile_id = cursor.fetchone()[0]

        connection.commit()

        return {
            "profile_id": profile_id,
            "dataset_id": dataset_id,
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

def get_dataset_id_by_filename(filename: str):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT dataset_id
            FROM datasets
            WHERE file_name = %s
            ORDER BY dataset_id DESC
            LIMIT 1
            """,
            (filename,),
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Dataset with filename '{filename}' does not exist."
            )

        return result[0]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

def get_dataset_profile(dataset_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT profile_id, dataset_id, profile_data, created_at
            FROM dataset_profiles
            WHERE dataset_id = %s
            ORDER BY profile_id DESC
            LIMIT 1
            """,
            (dataset_id,),
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Profile for dataset ID {dataset_id} does not exist."
            )

        return {
            "profile_id": result[0],
            "dataset_id": result[1],
            "profile_data": result[2],
            "created_at": result[3],
        }

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()