from fastapi import APIRouter

from backend.schemas.api_schema import DashboardResponse

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardResponse
)
def get_dashboard():
    return {
        "status": "success",
        "message": "Dashboard endpoint is ready."
    }