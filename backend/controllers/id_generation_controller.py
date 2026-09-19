from fastapi import APIRouter

from backend.services.id_configuration_service import (
    generate_ids_for_dataset,
)

router = APIRouter()


@router.post("/generation/ids/{dataset_id}")
def generate_ids(dataset_id: int):
    result = generate_ids_for_dataset(dataset_id)

    dataframe = result["dataframe"]
    output = result["output"]

    return {
        "status": "success",
        "message": "New identifiers generated successfully.",
        "data": {
            "dataset_id": dataset_id,
            "row_count": len(dataframe),
            "columns": list(dataframe.columns),
            "output": output,
            "preview": dataframe.head(5).to_dict(
                orient="records"
            ),
        },
    }