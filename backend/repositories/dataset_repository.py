from backend.config.database import get_db_connection


def create_dataset(
    filename,
    row_count,
    column_count
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
                column_count
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING dataset_id
            """,
            (
                filename,
                filename,
                filename.split(".")[-1].lower(),
                row_count,
                column_count,
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