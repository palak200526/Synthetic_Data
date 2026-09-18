from fastapi import APIRouter

from backend.services.dataset_loader import load_dataset
from backend.services.relationship_analysis_service import (
    analyze_relationships,
)
from backend.services.train_test_split_service import (
    create_train_test_split,
)
from backend.schemas.relationship_schema import (
    RelationshipAnalysisRequest,
)
from backend.repositories.relationship_repository import (
    save_relationship_analysis,
    get_relationship_analysis,
)


router = APIRouter(
    prefix="/relationships",
    tags=["Relationship Analysis"],
)


@router.post("/{dataset_id}/{filename}")
def analyze_relationships_api(
    dataset_id: int,
    filename: str,
    request: RelationshipAnalysisRequest,
):
    file_path = f"data/uploads/{filename}"

    dataframe = load_dataset(file_path)

    relationship_result = analyze_relationships(dataframe)

    split_result = create_train_test_split(
        dataframe,
        test_size=request.test_size,
        random_state=request.random_state,
    )

    # Save relationship analysis in PostgreSQL
    saved_analysis = save_relationship_analysis(
        dataset_id=dataset_id,
        correlation_matrix=(
            relationship_result["correlation_matrix"].to_dict()
        ),
        covariance_matrix=(
            relationship_result["covariance_matrix"].to_dict()
        ),
        test_size=split_result["test_size"],
        random_state=split_result["random_state"],
    )

    return {
        "status": "success",
        "message": (
            "Relationship analysis and train/test split "
            "completed successfully."
        ),
        "analysis_id": saved_analysis["analysis_id"],
        "dataset_id": dataset_id,
        "filename": filename,
        "numerical_columns": relationship_result[
            "numerical_columns"
        ],
        "correlation_matrix": (
            relationship_result["correlation_matrix"].to_dict()
        ),
        "covariance_matrix": (
            relationship_result["covariance_matrix"].to_dict()
        ),
        "train_rows": len(
            split_result["train_dataframe"]
        ),
        "test_rows": len(
            split_result["test_dataframe"]
        ),
        "test_size": split_result["test_size"],
        "random_state": split_result["random_state"],
    }

@router.get("/{dataset_id}")
def get_relationship_analysis_api(dataset_id: int):
    analysis = get_relationship_analysis(dataset_id)

    if not analysis:
        return {
            "status": "error",
            "message": "No relationship analysis found for this dataset.",
            "dataset_id": dataset_id,
        }

    return {
        "status": "success",
        "dataset_id": analysis["dataset_id"],
        "analysis_id": analysis["analysis_id"],
        "correlation_matrix": analysis["correlation_matrix"],
        "covariance_matrix": analysis["covariance_matrix"],
        "test_size": analysis["test_size"],
        "random_state": analysis["random_state"],
        "created_at": analysis["created_at"],
    }