from fastapi import APIRouter

from backend.schemas.api_schema import GenerationRequest

router = APIRouter()


@router.post("/generation")
def generate_synthetic_data(
    request: GenerationRequest
):
    return {
        "status": "success",
        "message": "Synthetic data generation endpoint is ready.",
        "data": {
            "dataset_id": request.dataset_id,
            "model_name": request.model_name,
            "parameters": request.parameters
        }
    }