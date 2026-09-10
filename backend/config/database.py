import psycopg2

from backend.config.settings import DATABASE_URL


def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.Error as error:
        raise RuntimeError(
            f"Unable to connect to PostgreSQL: {error}"
        ) from error