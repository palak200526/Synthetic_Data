from fastapi import APIRouter, Depends

from backend.repositories.evaluation_repository import (
    get_dashboard_summary,
    get_evaluation_by_result_id,
)
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
    response_model=DashboardResponse,
)
def get_dashboard(
    current_user=Depends(get_current_user),
):
    user_id = current_user if isinstance(current_user, int) else getattr(current_user, "user_id", current_user)
    summary = get_dashboard_summary(user_id)

    latest_metrics = {}
    if summary.get("recent_evaluations"):
        latest_res_id = summary["recent_evaluations"][0]["result_id"]
        latest_eval = get_evaluation_by_result_id(latest_res_id)
        if latest_eval and latest_eval.get("utility_metrics"):
            latest_metrics = latest_eval["utility_metrics"]

    payload = {
        "status": "success",
        "message": "Dashboard data retrieved successfully.",
        **summary,
        **latest_metrics,
        "data": {
            **summary,
            **latest_metrics,
        },
    }

    return payload