from backend.config.database import get_db_connection


def get_domain_preset(
    column_name: str,
    domain_type: str,
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                preset_id,
                column_pattern,
                suggested_type,
                is_sensitive,
                is_identifier
            FROM domain_column_presets
            WHERE domain_type = %s
            AND LOWER(column_pattern) = LOWER(%s)
            LIMIT 1
        """

        cursor.execute(
            query,
            (
                domain_type,
                column_name,
            ),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "preset_id": row[0],
            "column_pattern": row[1],
            "suggested_type": row[2],
            "is_sensitive": row[3],
            "is_identifier": row[4],
        }

    finally:
        cursor.close()
        connection.close()