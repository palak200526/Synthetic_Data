from fastapi import APIRouter, Depends

from backend.utils.auth_dependency import get_current_user

from backend.schemas.configuration_schema import (
    ColumnConfigurationRequest,
)

from backend.services.configuration_service import (
    save_column_configurations,
    review_column_configurations,
)

router = APIRouter(
    prefix="",
    tags=["Column Configuration"],
)


@router.post(
    "/column-configurations",
    summary="Save column configurations",
    description=(
        "Stores the user's configuration for dataset columns, including "
        "column treatment, suggested data type, sensitivity, identifier "
        "status, and generation-related actions."
    ),
)
def save_column_configurations_controller(
    request: ColumnConfigurationRequest,
    user_id: int = Depends(get_current_user),
):
    return save_column_configurations(
        request,
        user_id
    )


@router.get(
    "/column-configurations/{dataset_id}",
    summary="Get column configurations",
    description=(
        "Retrieves the saved column configurations for the specified dataset. "
        "Only the dataset owner can access these configurations."
    ),
)
def review_column_configurations_controller(
    dataset_id: int,
    user_id: int = Depends(get_current_user),
):
    return review_column_configurations(
        dataset_id,
        user_id
    )