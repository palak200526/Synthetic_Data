from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from backend.utils.auth_dependency import get_current_user
from backend.services.profiling_service import get_profile


router = APIRouter(
    prefix="",
    tags=["Dataset Profiling"],
)


@router.get(
    "/profile/{dataset_id}",
    summary="Get dataset profile",
    description=(
        "Retrieves the profiling information for a dataset using its dataset ID. "
        "If a profile already exists, the saved profile is returned. "
        "Otherwise, the dataset is loaded, profiled, and the generated "
        "profile is stored for future retrieval."
    ),
)
def get_profile_controller(
    dataset_id: int,
    user_id: int = Depends(get_current_user),
):
    try:

        return get_profile(
            dataset_id,
            user_id,
        )

    except PermissionError as e:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )