from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.dataset_group_service import create_group


router = APIRouter()


class DatasetGroupRequest(BaseModel):
    group_name: str
    domain_type: str | None = None
    user_id: int | None = None


@router.post("/groups")
def create_dataset_group_controller(
    request: DatasetGroupRequest
):
    try:
        group_id = create_group(
            group_name=request.group_name,
            domain_type=request.domain_type,
            user_id=request.user_id,
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
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )