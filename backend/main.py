from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException

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

        return {
            "status": "success",
            "message": "Dataset uploaded successfully.",
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

        return {
            "status": "success",
            "message": "Dataset profile generated successfully.",
            "data": profile,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate profile: {error}"
        )

