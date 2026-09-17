from fastapi import APIRouter, File, UploadFile

from backend.services.dataset_service import upload_dataset

router = APIRouter()


@router.post("/upload")
async def upload_dataset_controller(
    file: UploadFile = File(...)
):
    return await upload_dataset(file)