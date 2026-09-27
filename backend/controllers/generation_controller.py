from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from backend.schemas.api_schema import GenerationRequest

from backend.services.generation_service import (
    generate_synthetic_dataset,
)

from backend.utils.auth_dependency import get_current_user


router = APIRouter(
    prefix="",
    tags=["Generation"],
)


@router.post(
    "/generation",
    summary="Generate synthetic data",
    description=(
        "Generates synthetic data for a dataset using the selected "
        "generation model and configured parameters. The generation "
        "process uses the prepared dataset and column configurations "
        "and returns information about the generated synthetic dataset."
    ),
)
def generate_synthetic_data(
    request: GenerationRequest,
    user_id: int = Depends(get_current_user),
):

    try:

        return generate_synthetic_dataset(
            dataset_id=request.dataset_id,
            model_name=request.model_name,
            parameters=request.parameters,
            user_id=user_id,
        )

    except PermissionError as e:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    except ValueError as e:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )