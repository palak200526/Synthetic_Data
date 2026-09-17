from backend.config.database import get_db_connection


def create_processing_session():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO processing_sessions
            DEFAULT VALUES
            RETURNING session_id
            """
        )

        session_id = cursor.fetchone()[0]

        connection.commit()

        return session_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()