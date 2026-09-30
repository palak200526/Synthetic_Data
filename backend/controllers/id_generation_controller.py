from fastapi import APIRouter, Depends

from backend.services.id_configuration_service import (
    generate_ids_for_dataset,
)

from backend.utils.auth_dependency import get_current_user

router = APIRouter(
    prefix="",
    tags=["ID Generation"],
)


@router.post(
    "/generation/ids/{dataset_id}",
    summary="Generate synthetic identifiers",
    description=(
        "Generates new unique identifier values for the specified dataset. "
        "The generated identifiers are designed to replace or protect original "
        "identifier values while maintaining uniqueness in the synthetic data."
    ),
)
def generate_ids(
    dataset_id: int,
    current_user=Depends(get_current_user),
):
    result = generate_ids_for_dataset(dataset_id)

    return {
        "status": "success",
        "message": "New identifiers generated successfully.",
        "data": {
            "dataset_id": dataset_id,
            "output": result["output"],
        },
    }