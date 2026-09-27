from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from backend.utils.auth_dependency import get_current_user

from backend.services.dataset_loader import load_dataset
from backend.services.preprocessing_service import preprocess_dataset

from backend.repositories.dataset_repository import (
    get_dataset_file_path,
)


router = APIRouter(
    prefix="/preprocess",
    tags=["Preprocessing"],
)


@router.post(
    "/{dataset_id}",
    summary="Preprocess dataset",
    description=(
        "Preprocesses the specified dataset using the saved column "
        "configurations and prepares it for synthetic data generation."
    ),
)
async def preprocess(
    dataset_id: int,
    user_id: int = Depends(get_current_user),
):

    try:

        # --------------------------------------------------
        # 1. Get actual uploaded file path using dataset ID
        # --------------------------------------------------

        file_path = get_dataset_file_path(
            dataset_id
        )

        # --------------------------------------------------
        # 2. Load dataset
        # --------------------------------------------------

        dataframe = load_dataset(
            file_path
        )

        # --------------------------------------------------
        # 3. Preprocess dataset
        # --------------------------------------------------

        result = preprocess_dataset(
            dataframe,
            dataset_id
        )

        # --------------------------------------------------
        # 4. Return preprocessing result
        # --------------------------------------------------

        return {
            "status": "success",
            "message": (
                "Dataset preprocessing completed successfully."
            ),
            "dataset_id": dataset_id,
            "row_count": len(
                result["dataframe"]
            ),
            "column_count": len(
                result["dataframe"].columns
            ),
            "numerical_columns": (
                result["numerical_columns"]
            ),
            "categorical_columns": (
                result["categorical_columns"]
            ),
            "outliers": result["outliers"],
            "validation": result["validation"],
        }

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

    except FileNotFoundError as e:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except Exception as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )