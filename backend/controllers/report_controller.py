from fastapi import APIRouter, Depends

from backend.schemas.api_schema import ReportResponse

from backend.utils.auth_dependency import get_current_user

router = APIRouter(
    prefix="",
    tags=["Reports"],
)


@router.get(
    "/report",
    summary="Generate evaluation report",
    description=(
        "Retrieves the report data generated from synthetic data evaluation, "
        "including generation details, evaluation metrics, privacy results, "
        "and other relevant assessment information."
    ),
    response_model=ReportResponse
)
def get_report(
    current_user=Depends(get_current_user),
):
    return {
        "status": "success",
        "message": "Report endpoint is ready."
    }