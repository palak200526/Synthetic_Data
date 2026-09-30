import json

from backend.config.database import get_db_connection


# ============================================================
# Relationship Analysis
# ============================================================

def save_relationship_analysis(
    dataset_id: int,
    correlation_matrix: dict,
    covariance_matrix: dict,
    test_size: float,
    random_state: int,
):
    connection = get_db_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO relationship_analysis (
                dataset_id,
                correlation_matrix,
                covariance_matrix,
                test_size,
                random_state
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING analysis_id, created_at;
        """

        cursor.execute(
            query,
            (
                dataset_id,
                json.dumps(correlation_matrix),
                json.dumps(covariance_matrix),
                test_size,
                random_state,
            ),
        )

        result = cursor.fetchone()
        connection.commit()

        return {
            "analysis_id": result[0],
            "created_at": result[1],
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def get_relationship_analysis(dataset_id: int):
    connection = get_db_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                analysis_id,
                dataset_id,
                correlation_matrix,
                covariance_matrix,
                test_size,
                random_state,
                created_at
            FROM relationship_analysis
            WHERE dataset_id = %s
            ORDER BY created_at DESC
            LIMIT 1;
        """

        cursor.execute(query, (dataset_id,))
        result = cursor.fetchone()

        if not result:
            return None

        correlation_matrix = result[2]
        covariance_matrix = result[3]

        # Handle JSON stored as string or returned as dictionary
        if isinstance(correlation_matrix, str):
            correlation_matrix = json.loads(correlation_matrix)

        if isinstance(covariance_matrix, str):
            covariance_matrix = json.loads(covariance_matrix)

        return {
            "analysis_id": result[0],
            "dataset_id": result[1],
            "correlation_matrix": correlation_matrix,
            "covariance_matrix": covariance_matrix,
            "test_size": result[4],
            "random_state": result[5],
            "created_at": result[6],
        }

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# Dataset Relationships
# ============================================================

def save_dataset_relationship(
    group_id: int,
    parent_dataset_id: int,
    parent_column: str,
    child_dataset_id: int,
    child_column: str,
    relationship_type: str = "one-to-many",
):
    connection = get_db_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO dataset_relationships (
                group_id,
                parent_dataset_id,
                parent_column,
                child_dataset_id,
                child_column,
                relationship_type
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING relationship_id, created_at;
        """

        cursor.execute(
            query,
            (
                group_id,
                parent_dataset_id,
                parent_column,
                child_dataset_id,
                child_column,
                relationship_type,
            ),
        )

        result = cursor.fetchone()
        connection.commit()

        return {
            "relationship_id": result[0],
            "created_at": result[1],
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def get_dataset_relationships(group_id: int):
    connection = get_db_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                relationship_id,
                group_id,
                parent_dataset_id,
                parent_column,
                child_dataset_id,
                child_column,
                relationship_type,
                created_at
            FROM dataset_relationships
            WHERE group_id = %s
            ORDER BY relationship_id;
        """

        cursor.execute(query, (group_id,))
        rows = cursor.fetchall()

        return [
            {
                "relationship_id": row[0],
                "group_id": row[1],
                "parent_dataset_id": row[2],
                "parent_column": row[3],
                "child_dataset_id": row[4],
                "child_column": row[5],
                "relationship_type": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()