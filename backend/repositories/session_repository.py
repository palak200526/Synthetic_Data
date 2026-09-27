from backend.config.database import get_db_connection


def create_processing_session(user_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO sessions (
                user_id,
                created_at,
                expires_at
            )
            VALUES (
                %s,
                NOW(),
                NOW() + INTERVAL '30 minutes'
            )
            RETURNING session_id, user_id, created_at, expires_at
            """,
            (user_id,)
        )

        session = cursor.fetchone()

        connection.commit()

        return session

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()