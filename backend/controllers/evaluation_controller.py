from fastapi import APIRouter, Depends

from backend.utils.auth_dependency import get_current_user

from backend.schemas.api_schema import EvaluationRequest

router = APIRouter(
    prefix="",
    tags=["Evaluation"],
)

@router.post(
    "/evaluation",
    summary="Evaluate generated synthetic data",
    description=(
        "Evaluates the quality of generated synthetic data against the source "
        "dataset using statistical, distributional, utility, and privacy-related "
        "metrics."
    ),
)
def evaluate_generated_data(
    request: EvaluationRequest,
    current_user=Depends(get_current_user),
):
    return {
        "status": "success",
        "message": "Evaluation endpoint is ready.",
        "data": {
            "result_id": request.result_id
        }
    }