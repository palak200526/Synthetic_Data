from pathlib import Path
from backend.config.database import get_db_connection
import json


# --------------------------------------------------
# Create Dataset
# --------------------------------------------------

def create_dataset(
    filename,
    row_count,
    column_count,
    session_id,
    group_id=None,
    domain_type=None,
    user_id=None
):  

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO datasets (
                dataset_name,
                file_name,
                file_type,
                row_count,
                column_count,
                session_id,
                group_id,
                domain_type,
                user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING dataset_id
            """,
            (
                filename,
                filename,
                filename.split(".")[-1].lower(),
                row_count,
                column_count,
                session_id,
                group_id,
                domain_type,
                user_id,
            )
        )

        dataset_id = cursor.fetchone()[0]

        connection.commit()

        return dataset_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# --------------------------------------------------
# Get Dataset Filename
# --------------------------------------------------

def get_dataset_filename(dataset_id: int):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT file_name
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,),
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Dataset with ID {dataset_id} does not exist."
            )

        return result[0]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# --------------------------------------------------
# Get Dataset Domain Type
# --------------------------------------------------

def get_dataset_domain_type(dataset_id: int):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT domain_type
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,),
        )

        result = cursor.fetchone()

        if not result:
            raise ValueError(
                f"Dataset {dataset_id} not found."
            )

        return result[0]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# --------------------------------------------------
# Save Dataset Profile
# --------------------------------------------------

def save_dataset_profile(
    dataset_id: int,
    profile_data: dict
):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO dataset_profiles (
                dataset_id,
                profile_data
            )
            VALUES (%s, %s)
            RETURNING profile_id
            """,
            (
                dataset_id,
                json.dumps(profile_data),
            ),
        )

        profile_id = cursor.fetchone()[0]

        connection.commit()

        return {
            "profile_id": profile_id,
            "dataset_id": dataset_id,
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


# --------------------------------------------------
# Get Dataset ID By Filename
# --------------------------------------------------

def get_dataset_id_by_filename(filename: str):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT dataset_id
            FROM datasets
            WHERE file_name = %s
            ORDER BY dataset_id DESC
            LIMIT 1
            """,
            (filename,),
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Dataset with filename '{filename}' does not exist."
            )

        return result[0]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# --------------------------------------------------
# Get Dataset Profile
# --------------------------------------------------

def get_dataset_profile(dataset_id: int):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                profile_id,
                dataset_id,
                profile_data,
                created_at
            FROM dataset_profiles
            WHERE dataset_id = %s
            ORDER BY profile_id DESC
            LIMIT 1
            """,
            (dataset_id,),
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Profile for dataset ID {dataset_id} does not exist."
            )

        return {
            "profile_id": result[0],
            "dataset_id": result[1],
            "profile_data": result[2],
            "created_at": result[3],
        }

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# --------------------------------------------------
# Get Actual Uploaded Dataset File Path
# --------------------------------------------------

def get_dataset_file_path(dataset_id: int):

    upload_directory = Path("data/uploads")

    # Make sure upload directory exists
    if not upload_directory.exists():
        raise FileNotFoundError(
            "Dataset upload directory does not exist: "
            f"{upload_directory.resolve()}"
        )

    # --------------------------------------------------
    # 1. First try the dataset-specific upload format
    #    Example:
    #    dataset_263_netflix_titles.csv
    # --------------------------------------------------

    dataset_pattern = f"dataset_{dataset_id}_*"

    matching_files = [
        file
        for file in upload_directory.rglob(dataset_pattern)
        if file.is_file()
    ]

    if matching_files:
        return matching_files[0]


    # --------------------------------------------------
    # 2. If not found, get original filename from DB
    # --------------------------------------------------

    filename = get_dataset_filename(dataset_id)

    if filename:

        # --------------------------------------------------
        # 3. Try exact filename
        #    Example:
        #    data/uploads/netflix_titles.csv
        # --------------------------------------------------

        exact_file = upload_directory / filename

        if exact_file.exists() and exact_file.is_file():
            return exact_file


        # --------------------------------------------------
        # 4. Try filename anywhere inside uploads
        # --------------------------------------------------

        matching_original_files = [
            file
            for file in upload_directory.rglob(filename)
            if file.is_file()
        ]

        if matching_original_files:
            return matching_original_files[0]


        # --------------------------------------------------
        # 5. Try dataset_<id>_<filename>
        # --------------------------------------------------

        dataset_filename = (
            upload_directory /
            f"dataset_{dataset_id}_{filename}"
        )

        if (
            dataset_filename.exists()
            and dataset_filename.is_file()
        ):
            return dataset_filename


    # --------------------------------------------------
    # 6. Nothing found
    # --------------------------------------------------

    raise FileNotFoundError(
        f"Uploaded file for dataset ID {dataset_id} "
        f"could not be found in "
        f"{upload_directory.resolve()}. "
        f"Expected filename: {filename}"
    )


# --------------------------------------------------
# Get Dataset User ID
# --------------------------------------------------

def get_dataset_user_id(dataset_id: int):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT user_id
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,),
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Dataset with ID {dataset_id} does not exist."
            )

        return result[0]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# --------------------------------------------------
# Get Dataset By ID
# --------------------------------------------------

def get_dataset_by_id(dataset_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                dataset_id,
                dataset_name,
                file_name,
                file_type,
                row_count,
                column_count,
                session_id,
                group_id,
                domain_type,
                user_id
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        return {
            "dataset_id": row[0],
            "dataset_name": row[1],
            "name": row[1] or row[2],
            "file_name": row[2],
            "file_type": row[3],
            "row_count": row[4],
            "column_count": row[5],
            "session_id": row[6],
            "group_id": row[7],
            "domain_type": row[8],
            "user_id": row[9],
        }

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --------------------------------------------------
# Get Datasets By Group
# --------------------------------------------------

def get_datasets_by_group(group_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                dataset_id,
                dataset_name,
                file_name,
                file_type,
                row_count,
                column_count,
                group_id,
                domain_type,
                user_id,
                uploaded_at
            FROM datasets
            WHERE group_id = %s
            ORDER BY dataset_id ASC
            """,
            (group_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "dataset_id": row[0],
                "dataset_name": row[1],
                "name": row[1] or row[2],
                "file_name": row[2],
                "file_type": row[3],
                "row_count": row[4],
                "column_count": row[5],
                "group_id": row[6],
                "domain_type": row[7],
                "user_id": row[8],
                "uploaded_at": row[9].isoformat() if row[9] else None,
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --------------------------------------------------
# Get User Datasets
# --------------------------------------------------

def get_user_datasets(user_id: int | None = None):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        if user_id:
            cursor.execute(
                """
                SELECT
                    dataset_id,
                    dataset_name,
                    file_name,
                    file_type,
                    row_count,
                    column_count,
                    group_id,
                    domain_type,
                    user_id,
                    uploaded_at
                FROM datasets
                WHERE user_id = %s OR user_id IS NULL
                ORDER BY dataset_id DESC
                """,
                (user_id,),
            )
        else:
            cursor.execute(
                """
                SELECT
                    dataset_id,
                    dataset_name,
                    file_name,
                    file_type,
                    row_count,
                    column_count,
                    group_id,
                    domain_type,
                    user_id,
                    uploaded_at
                FROM datasets
                ORDER BY dataset_id DESC
                """
            )

        rows = cursor.fetchall()

        return [
            {
                "dataset_id": row[0],
                "dataset_name": row[1],
                "name": row[1] or row[2],
                "file_name": row[2],
                "file_type": row[3],
                "row_count": row[4],
                "column_count": row[5],
                "group_id": row[6],
                "domain_type": row[7],
                "user_id": row[8],
                "uploaded_at": row[9].isoformat() if row[9] else None,
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --------------------------------------------------
# Assign Dataset to Group
# --------------------------------------------------

def assign_dataset_to_group(dataset_id: int, group_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE datasets
            SET group_id = %s
            WHERE dataset_id = %s
            """,
            (group_id, dataset_id),
        )

        connection.commit()
        return True

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
