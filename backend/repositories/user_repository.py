from backend.config.database import get_db_connection


def create_user(username: str, email: str, password_hash: str):
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        query = """
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING user_id, username, email, created_at;
        """

        cursor.execute(query, (username, email, password_hash))

        user = cursor.fetchone()
        conn.commit()

        return user

    finally:
        cursor.close()
        conn.close()


def get_user_by_email(email: str):
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        query = """
            SELECT user_id, username, email, password_hash, created_at
            FROM users
            WHERE email = %s;
        """

        cursor.execute(query, (email,))

        return cursor.fetchone()

    finally:
        cursor.close()
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        query = """
            SELECT user_id, username, email, created_at
            FROM users
            WHERE user_id = %s;
        """

        cursor.execute(query, (user_id,))

        return cursor.fetchone()

    finally:
        cursor.close()
        conn.close()