from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from backend.schemas.api_schema import EvaluationRequest
from backend.services.evaluation_service import (
    evaluate_generation,
)
from backend.utils.auth_dependency import get_current_user


router = APIRouter(
    prefix="",
    tags=["Evaluation"],
)


@router.post(
    "/evaluation",
    summary="Evaluate generated synthetic data",
    description=(
        "Evaluates generated synthetic data against the source dataset "
        "using statistical similarity metrics."
    ),
)
def evaluate_generated_data(
    request: EvaluationRequest,
    user_id: int = Depends(get_current_user),
):
    try:

        result = evaluate_generation(
            result_id=request.result_id,
            user_id=user_id,
        )

        return {
            "status": "success",
            "message": (
                "Statistical evaluation completed successfully."
            ),
            "data": result,
        }

    except PermissionError as e:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    except FileNotFoundError as e:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except ValueError as e:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )