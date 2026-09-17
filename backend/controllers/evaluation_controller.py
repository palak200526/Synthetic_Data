from fastapi import APIRouter

from backend.schemas.api_schema import EvaluationRequest

router = APIRouter()


@router.post("/evaluation")
def evaluate_generated_data(
    request: EvaluationRequest
):
    return {
        "status": "success",
        "message": "Evaluation endpoint is ready.",
        "data": {
            "result_id": request.result_id
        }
    }