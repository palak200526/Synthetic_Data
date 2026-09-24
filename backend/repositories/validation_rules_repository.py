from backend.config.database import get_db_connection
from psycopg2.extras import Json


def create_validation_rule(
    dataset_id: int,
    rule_name: str,
    rule_type: str,
    rule_definition: dict,
    description: str | None = None,
    is_active: bool = True,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO validation_rules (
                dataset_id,
                rule_name,
                rule_type,
                rule_definition,
                description,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING rule_id
            """,
            (
                dataset_id,
                rule_name,
                rule_type,
                Json(rule_definition),
                description,
                is_active,
            ),
        )

        rule_id = cursor.fetchone()[0]

        connection.commit()

        return {
            "rule_id": rule_id,
            "dataset_id": dataset_id,
            "rule_name": rule_name,
            "rule_type": rule_type,
            "rule_definition": rule_definition,
            "description": description,
            "is_active": is_active,
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


def get_validation_rules(dataset_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                rule_id,
                dataset_id,
                rule_name,
                rule_type,
                rule_definition,
                description,
                is_active,
                created_at
            FROM validation_rules
            WHERE dataset_id = %s
            ORDER BY rule_id
            """,
            (dataset_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "rule_id": row[0],
                "dataset_id": row[1],
                "rule_name": row[2],
                "rule_type": row[3],
                "rule_definition": row[4],
                "description": row[5],
                "is_active": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def get_validation_rule(rule_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                rule_id,
                dataset_id,
                rule_name,
                rule_type,
                rule_definition,
                description,
                is_active,
                created_at
            FROM validation_rules
            WHERE rule_id = %s
            """,
            (rule_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "rule_id": row[0],
            "dataset_id": row[1],
            "rule_name": row[2],
            "rule_type": row[3],
            "rule_definition": row[4],
            "description": row[5],
            "is_active": row[6],
            "created_at": row[7],
        }

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def delete_validation_rule(rule_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM validation_rules
            WHERE rule_id = %s
            RETURNING rule_id
            """,
            (rule_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        connection.commit()

        return {
            "rule_id": row[0],
            "deleted": True,
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