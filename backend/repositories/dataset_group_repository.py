from backend.config.database import get_db_connection


def create_dataset_group(
    group_name: str,
    domain_type: str | None = None,
    user_id: int | None = None,
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
            ),
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


def get_user_dataset_groups(user_id: int | None = None):
    """
    Retrieve all dataset groups for a user, or all groups if user_id is not specified.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        if user_id:
            cursor.execute(
                """
                SELECT group_id, group_name, domain_type, user_id, created_at
                FROM dataset_groups
                WHERE user_id = %s OR user_id IS NULL
                ORDER BY group_id DESC
                """,
                (user_id,),
            )
        else:
            cursor.execute(
                """
                SELECT group_id, group_name, domain_type, user_id, created_at
                FROM dataset_groups
                ORDER BY group_id DESC
                """
            )

        rows = cursor.fetchall()

        return [
            {
                "group_id": row[0],
                "group_name": row[1],
                "domain_type": row[2],
                "user_id": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def get_dataset_group_by_id(group_id: int):
    """
    Retrieve single dataset group by group_id.
    """
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT group_id, group_name, domain_type, user_id, created_at
            FROM dataset_groups
            WHERE group_id = %s
            """,
            (group_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "group_id": row[0],
            "group_name": row[1],
            "domain_type": row[2],
            "user_id": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
        }

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()