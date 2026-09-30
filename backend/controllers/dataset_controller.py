from fastapi import APIRouter, File, UploadFile, Form, Depends

from backend.utils.auth_dependency import get_current_user
from backend.services.dataset_service import upload_dataset
from backend.repositories.session_repository import (
    create_processing_session,
)

router = APIRouter(
    prefix="",
    tags=["Dataset Upload"],
)



@router.post(
    "/upload",
    summary="Upload dataset files",
    description=(
        "Uploads one or more CSV, XLS, or XLSX dataset files. "
        "For each uploaded dataset, the API validates the file, stores it "
        "in the configured upload location, creates dataset metadata and "
        "assigns a unique dataset ID. A processing session is created for "
        "the upload request and can be associated with an optional dataset "
        "group and domain type."
    ),
)

async def upload_dataset_controller(
    files: list[UploadFile] = File(
        ...,
        description="One or more dataset files to upload."
    ),
    group_id: int | None = Form(
        None,
        description="Optional dataset group ID."
    ),
    domain_type: str | None = Form(
        None,
        description="Optional domain type, such as supply_chain."
    ),
    user_id: int = Depends(get_current_user),
):
    if not files:
        return {
            "status": "error",
            "message": "At least one dataset file is required."
        }

    session_id = create_processing_session()

    results = []

    for file in files:
        result = await upload_dataset(
            file=file,
            group_id=group_id,
            domain_type=domain_type,
            session_id=session_id,
            user_id=user_id,
        )

        results.append(result)

    return {
        "status": "success",
        "message": "Datasets uploaded successfully.",
        "group_id": group_id,
        "domain_type": domain_type,
        "session_id": session_id,
        "datasets": results,
    }