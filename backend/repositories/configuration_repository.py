from backend.config.database import get_db_connection


def save_configuration(configuration):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO column_configurations (
                dataset_id,
                column_name,
                column_type,
                is_sensitive,
                is_identifier,
                action
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (dataset_id, column_name)
            DO UPDATE SET
                column_type = EXCLUDED.column_type,
                is_sensitive = EXCLUDED.is_sensitive,
                is_identifier = EXCLUDED.is_identifier,
                action = EXCLUDED.action
            RETURNING configuration_id
            """,
            (
                configuration.dataset_id,
                configuration.column_name,
                configuration.column_type,
                configuration.is_sensitive,
                configuration.is_identifier,
                configuration.action,
            ),
        )

        configuration_id = cursor.fetchone()[0]

        connection.commit()

        return {
            "configuration_id": configuration_id,
            "dataset_id": configuration.dataset_id,
            "column_name": configuration.column_name,
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

def get_identifier_configurations(dataset_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                column_name,
                is_sensitive,
                is_identifier,
                action
            FROM column_configurations
            WHERE dataset_id = %s
              AND is_identifier = TRUE
            """,
            (dataset_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "column_name": row[0],
                "is_sensitive": row[1],
                "is_identifier": row[2],
                "action": row[3],
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()  

        if connection:
            connection.close()

def get_configurations(dataset_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                configuration_id,
                dataset_id,
                column_name,
                column_type,
                is_sensitive,
                is_identifier,
                action
            FROM column_configurations
            WHERE dataset_id = %s
            ORDER BY configuration_id
            """,
            (dataset_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "configuration_id": row[0],
                "dataset_id": row[1],
                "column_name": row[2],
                "column_type": row[3],
                "is_sensitive": row[4],
                "is_identifier": row[5],
                "action": row[6],
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()