from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from backend.utils.auth_dependency import get_current_user

from backend.services.llm_column_configuration_service import (
    analyze_dataset_columns,
)


router = APIRouter(
    prefix="",
    tags=["LLM Column Analysis"],
)


@router.post(
    "/column-analysis/{dataset_id}",
    summary="Analyze dataset columns using LLM",
    description=(
        "Analyzes every column of the specified dataset using the "
        "LLM. The LLM determines identifier status, recommended "
        "generation action, and the reason for the recommendation. "
        "The result is returned for user review and is not saved "
        "as the final column configuration."
    ),
)
def analyze_dataset_columns_controller(
    dataset_id: int,
    user_id: int = Depends(get_current_user),
):
    try:

        return analyze_dataset_columns(
            dataset_id,
            user_id,
        )

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