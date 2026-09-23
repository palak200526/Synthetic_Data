from fastapi import APIRouter

from backend.schemas.api_schema import MultiTableGenerationRequest
from backend.services.multi_table_generation_service import (
    generate_linked_tables,
)
from backend.services.referential_integrity_service import (
    validate_referential_integrity,
)

router = APIRouter()


@router.post("/generation/multi-table")
def generate_multi_table_data(
    request: MultiTableGenerationRequest,
):
    result = generate_linked_tables(
        group_id=request.group_id,
        model_name=request.model_name,
        parameters=request.parameters,
    )

    validation = validate_referential_integrity(
        result["tables"],
        result["relationships"],
    )

    return {
        "status": "success",
        "message": "Multi-table synthetic data generated successfully.",
        "group_id": result["group_id"],
        "model_name": result["model_name"],
        "tables": {
            dataset_id: {
                "dataset_id": table["dataset_id"],
                "source_filename": table["source_filename"],
                "file_name": table["file_name"],
                "file_path": table["file_path"],
                "row_count": table["row_count"],
                "column_count": table["column_count"],
            }
            for dataset_id, table in result["tables"].items()
        },
        "relationships": validation["relationships"],
        "referential_integrity": validation["valid"],
    }