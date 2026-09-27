from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.services.dataset_group_service import create_group
from backend.utils.auth_dependency import get_current_user


router = APIRouter(
    prefix="",
    tags=["Dataset Groups"],
)


class DatasetGroupRequest(BaseModel):
    group_name: str
    domain_type: str | None = None


@router.post(
    "/groups",
    summary="Create dataset group",
    description=(
        "Creates a dataset group for organizing multiple related datasets. "
        "Groups can be used to associate datasets that belong to the same "
        "domain or relational data workflow."
    ),
)
def create_dataset_group_controller(
    request: DatasetGroupRequest,
    current_user=Depends(get_current_user),
):
    try:
        group_id = create_group(
            group_name=request.group_name,
            domain_type=request.domain_type,
            user_id=current_user,
        )

        return {
            "status": "success",
            "message": "Dataset group created successfully.",
            "group_id": group_id,
            "group_name": request.group_name,
            "domain_type": request.domain_type,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )