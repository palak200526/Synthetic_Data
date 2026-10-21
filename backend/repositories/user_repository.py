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

def update_username(user_id: int, username: str):
    """Update a user's username after the service has validated uniqueness."""
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET username = %s WHERE user_id = %s RETURNING user_id, username, email, created_at",
            (username, user_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Account not found")
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conn.close()


def username_exists(username: str, exclude_user_id: int) -> bool:
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM users WHERE LOWER(username) = LOWER(%s) AND user_id <> %s LIMIT 1",
            (username, exclude_user_id),
        )
        return cursor.fetchone() is not None
    finally:
        if cursor:
            cursor.close()
        conn.close()


def get_user_with_password_by_id(user_id: int):
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, email, password_hash, created_at FROM users WHERE user_id = %s",
            (user_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        conn.close()


def update_password_hash(user_id: int, password_hash: str) -> bool:
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (password_hash, user_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conn.close()
