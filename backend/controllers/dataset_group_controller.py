from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.services.dataset_group_service import create_group
from backend.repositories.dataset_group_repository import (
    get_user_dataset_groups,
    get_dataset_group_by_id,
)
from backend.repositories.dataset_repository import (
    get_datasets_by_group,
    assign_dataset_to_group,
    get_dataset_by_id,
)
from backend.repositories.relationship_repository import (
    get_dataset_relationships,
)
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


@router.get(
    "/groups",
    summary="List dataset groups",
    description="Retrieves all dataset groups belonging to the user or system.",
)
def list_dataset_groups_controller(
    current_user=Depends(get_current_user),
):
    try:
        groups = get_user_dataset_groups(user_id=current_user)
        return {
            "status": "success",
            "groups": groups,
            "count": len(groups),
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@router.get(
    "/groups/{group_id}",
    summary="Get dataset group details",
    description="Retrieves metadata for a specific dataset group.",
)
def get_dataset_group_controller(
    group_id: int,
    current_user=Depends(get_current_user),
):
    group = get_dataset_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found.")

    return {
        "status": "success",
        "group": group,
    }


@router.get(
    "/groups/{group_id}/datasets",
    summary="List datasets in a group",
    description="Retrieves all datasets associated with a dataset group, including relationship tables.",
)
def get_group_datasets_controller(
    group_id: int,
    current_user=Depends(get_current_user),
):
    try:
        datasets = get_datasets_by_group(group_id)

        # Also find any datasets referenced in relationships for this group
        relationships = get_dataset_relationships(group_id)
        existing_ids = {d["dataset_id"] for d in datasets}

        rel_dataset_ids = set()
        for r in relationships:
            rel_dataset_ids.add(r["parent_dataset_id"])
            rel_dataset_ids.add(r["child_dataset_id"])

        for did in sorted(rel_dataset_ids):
            if did not in existing_ids:
                d_info = get_dataset_by_id(did)
                if d_info:
                    datasets.append(d_info)
                    existing_ids.add(did)

        return {
            "status": "success",
            "group_id": group_id,
            "datasets": datasets,
            "count": len(datasets),
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@router.post(
    "/groups/{group_id}/datasets/{dataset_id}",
    summary="Assign dataset to group",
    description="Associates a dataset with a dataset group.",
)
def assign_dataset_to_group_controller(
    group_id: int,
    dataset_id: int,
    current_user=Depends(get_current_user),
):
    try:
        assign_dataset_to_group(dataset_id=dataset_id, group_id=group_id)
        return {
            "status": "success",
            "message": f"Dataset {dataset_id} assigned to group {group_id} successfully.",
            "group_id": group_id,
            "dataset_id": dataset_id,
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )