from fastapi import APIRouter

from backend.schemas.api_schema import DownloadResponse

router = APIRouter()


@router.get(
    "/download",
    response_model=DownloadResponse
)
def download_result():
    return {
        "status": "success",
        "message": "Download endpoint is ready."
    }