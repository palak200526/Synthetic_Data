from backend.config.database import get_db_connection


def create_dataset_group(
    group_name,
    domain_type=None,
    user_id=None
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO dataset_groups (
                group_name,
                domain_type,
                user_id
            )
            VALUES (%s, %s, %s)
            RETURNING group_id
            """,
            (
                group_name,
                domain_type,
                user_id,
            )
        )

        group_id = cursor.fetchone()[0]

        connection.commit()

        return group_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close() 