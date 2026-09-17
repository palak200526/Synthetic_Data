from fastapi import APIRouter

from backend.schemas.api_schema import ReportResponse

router = APIRouter()


@router.get(
    "/report",
    response_model=ReportResponse
)
def get_report():
    return {
        "status": "success",
        "message": "Report endpoint is ready."
    }