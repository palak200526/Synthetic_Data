from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException

from backend.config.database import get_db_connection

from backend.services.sensitive_detector import (
    detect_sensitive_and_identifier_columns,
)

from pydantic import BaseModel
from typing import List

from backend.services.dataset_loader import (
    load_dataset,
    get_dataset_metadata,
)


from backend.services.dataset_profiler import (
    generate_profile,
)

from backend.utils.validators import (
    validate_file_extension,
    validate_file_size,
    validate_filename,
)


app = FastAPI(
    title="Synthetic Data Platform API",
    description="Backend API for the Synthetic Data Platform",
    version="1.0.0",
)


class ColumnConfiguration(BaseModel):
    dataset_id: int
    column_name: str
    column_type: str
    is_sensitive: bool
    is_identifier: bool
    action: str


class ColumnConfigurationRequest(BaseModel):
    configurations: List[ColumnConfiguration]

UPLOAD_DIRECTORY = Path("data/uploads")

UPLOAD_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True
)


@app.get("/")
def root():
    return {
        "message": "Synthetic Data Platform API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...)
):

    try:

        # 1. Validate filename

        validate_filename(file.filename)

        # 2. Validate extension

        validate_file_extension(file.filename)

        # 3. Read file

        file_content = await file.read()

        # 4. Validate file size

        validate_file_size(len(file_content))

        # 5. Save uploaded file

        file_path = UPLOAD_DIRECTORY / file.filename

        with open(file_path, "wb") as output_file:
            output_file.write(file_content)

        # 6. Load dataset

        dataframe = load_dataset(str(file_path))

        # 7. Generate metadata

        metadata = get_dataset_metadata(
            dataframe,
            file.filename
        )

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO datasets (
                dataset_name,
                file_name,
                file_type,
                row_count,
                column_count
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING dataset_id
            """,
            (
                file.filename,
                file.filename,
                file.filename.split(".")[-1].lower(),
                len(dataframe),
                len(dataframe.columns),
            )
        )

        dataset_id = cursor.fetchone()[0]

        connection.commit()

        cursor.close()
        connection.close()

        return {
            "status": "success",
            "message": "Dataset uploaded successfully.",
            "dataset_id": dataset_id,
            "data": metadata
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {error}"
        )


@app.get("/profile/{filename}")
def get_dataset_profile(filename: str):

    try:

        file_path = UPLOAD_DIRECTORY / filename

        if not file_path.exists():

            raise HTTPException(
                status_code=404,
                detail="Dataset not found."
            )

        dataframe = load_dataset(
            str(file_path)
        )

        profile = generate_profile(
            dataframe
        )
        detections = detect_sensitive_and_identifier_columns(
            dataframe
        )

        return {
            "status": "success",
            "message": "Dataset profile generated successfully.",
            "data": profile,
            "sensitive_identifier_detection": detections,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate profile: {error}"
        )


@app.post("/column-configurations")
def save_column_configurations(
    request: ColumnConfigurationRequest
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        for configuration in request.configurations:
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
                """,
                (
                    configuration.dataset_id,
                    configuration.column_name,
                    configuration.column_type,
                    configuration.is_sensitive,
                    configuration.is_identifier,
                    configuration.action,
                )
            )

        connection.commit()

        return {
            "status": "success",
            "message": "Column configurations saved successfully."
        }

    except Exception as error:

        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Unable to save column configurations: {error}"
        )

    finally:

        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()


@app.get("/health/database")
def database_health_check():
    connection = None

    try:
        connection = get_db_connection()

        return {
            "status": "healthy",
            "database": "PostgreSQL",
            "connection": "successful"
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    finally:
        if connection is not None:
            connection.close()