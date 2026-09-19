from backend.config.database import get_db_connection
import json


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
            (dataset_id,)
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
            "created_at": result[3].isoformat()
        }

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()