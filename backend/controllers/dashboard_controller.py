from fastapi import APIRouter, Depends

from backend.schemas.api_schema import DashboardResponse

from backend.utils.auth_dependency import get_current_user

router = APIRouter(
    prefix="",
    tags=["Dashboard"],
)


@router.get(
    "/dashboard",
    summary="Get evaluation dashboard",
    description=(
        "Retrieves aggregated evaluation results required to display the "
        "synthetic data quality, utility, privacy, and model comparison "
        "information on the dashboard."
    ),
    response_model=DashboardResponse
)
def get_dashboard(
    current_user=Depends(get_current_user),
):
    return {
        "status": "success",
        "message": "Dashboard endpoint is ready."
    }