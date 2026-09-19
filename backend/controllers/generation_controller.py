from fastapi import APIRouter

from backend.schemas.api_schema import GenerationRequest
from backend.services.generation_service import (
    generate_synthetic_dataset,
)


router = APIRouter()


@router.post("/generation")
def generate_synthetic_data(
    request: GenerationRequest,
):
    return generate_synthetic_dataset(
        dataset_id=request.dataset_id,
        model_name=request.model_name,
        parameters=request.parameters,
    )