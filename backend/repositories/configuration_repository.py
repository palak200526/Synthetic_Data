from backend.config.database import get_db_connection
from psycopg2.extras import Json

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
                is_identifier,
                action
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (dataset_id, column_name)
            DO UPDATE SET
                column_type = EXCLUDED.column_type,
                is_identifier = EXCLUDED.is_identifier,
                action = EXCLUDED.action
            RETURNING configuration_id
            """,
            (
                configuration.dataset_id,
                configuration.column_name,
                configuration.column_type,
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
                is_identifier,
                action
            FROM column_configurations
            WHERE dataset_id = %s
              AND is_identifier = TRUE
            ORDER BY configuration_id
            """,
            (dataset_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "column_name": row[0],
                "is_identifier": row[1],
                "action": row[2],
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
                is_identifier,
                action,
                rule
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
                "is_identifier": row[4],
                "action": row[5],
                "rule": row[6],
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def get_generation_configurations(dataset_id: int):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                column_name,
                column_type,
                is_identifier,
                action,
                rule
            FROM column_configurations
            WHERE dataset_id = %s
            ORDER BY configuration_id
            """,
            (dataset_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "column_name": row[0],
                "column_type": row[1],
                "is_identifier": row[2],
                "action": row[3],
                "rule": row[4],
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

def _rule_to_json(rule):
    if rule is None:
        return None
    if hasattr(rule, "model_dump"):
        return rule.model_dump()
    if isinstance(rule, dict):
        return rule
    if hasattr(rule, "operation"):
        return {
            "operation": rule.operation,
            "operands": list(getattr(rule, "operands", [])),
        }
    return None


def save_configurations_bulk(dataset_id: int, configurations: list) -> list:
    """
    Save multiple column configurations in one transaction.

    Uses a single DB connection and runs all inserts/updates
    back-to-back, then a single commit.
    """
    from backend.config.database import get_db_connection

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        saved = []

        for config in configurations:

            rule_payload = _rule_to_json(config.rule)

            cursor.execute(
                """
                INSERT INTO column_configurations (
                    dataset_id,
                    column_name,
                    column_type,
                    is_identifier,
                    action,
                    rule
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_id, column_name)
                DO UPDATE SET
                    column_type   = EXCLUDED.column_type,
                    is_identifier = EXCLUDED.is_identifier,
                    action        = EXCLUDED.action,
                    rule          = EXCLUDED.rule
                RETURNING
                    configuration_id,
                    dataset_id,
                    column_name,
                    column_type,
                    is_identifier,
                    action,
                    rule
                """,
                (
                    config.dataset_id,
                    config.column_name,
                    config.column_type,
                    config.is_identifier,
                    config.action,
                    Json(rule_payload) if rule_payload else None,
                ),
            )

            row = cursor.fetchone()

            saved.append({
                "configuration_id": row[0],
                "dataset_id": row[1],
                "column_name": row[2],
                "column_type": row[3],
                "is_identifier": row[4],
                "action": row[5],
                "rule": row[6],
            })

        connection.commit()
        return saved

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()