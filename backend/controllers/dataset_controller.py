from fastapi import APIRouter, File, UploadFile, Form

from backend.services.dataset_service import upload_dataset
from backend.repositories.session_repository import (
    create_processing_session,
)

router = APIRouter()


@router.post("/upload")
async def upload_dataset_controller(
    files: list[UploadFile] = File(...),
    group_id: int | None = Form(None),
    domain_type: str | None = Form(None)
):
    session_id = create_processing_session()

    results = []

    for file in files:
        result = await upload_dataset(
            file,
            group_id,
            domain_type,
            session_id
        )

        results.append(result)

    return {
        "status": "success",
        "message": "Datasets uploaded successfully.",
        "group_id": group_id,
        "domain_type": domain_type,
        "session_id": session_id,
        "datasets": results
    }