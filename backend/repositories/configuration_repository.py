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