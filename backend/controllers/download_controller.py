from fastapi import APIRouter, Depends

from backend.schemas.api_schema import DownloadResponse

from backend.utils.auth_dependency import get_current_user

router = APIRouter(
    prefix="",
    tags=["Downloads"],
)


@router.get(
    "/download",
    summary="Download generated dataset",
    description=(
        "Downloads the generated synthetic dataset produced by the platform. "
        "The endpoint returns the generated output file for further use."
    ),
    response_model=DownloadResponse
)
def download_result(
    current_user=Depends(get_current_user),
):
    return {
        "status": "success",
        "message": "Download endpoint is ready."
    }