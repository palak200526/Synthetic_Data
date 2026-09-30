from fastapi import APIRouter, Depends
from backend.utils.auth_dependency import get_current_user

from backend.services.dataset_loader import load_dataset

from backend.services.relationship_analysis_service import (
    analyze_relationships,
    create_dataset_relationship,
)

from backend.services.train_test_split_service import (
    create_train_test_split,
)

from backend.schemas.relationship_schema import (
    RelationshipAnalysisRequest,
    DatasetRelationshipRequest,
)

from backend.repositories.relationship_repository import (
    save_relationship_analysis,
    get_relationship_analysis,
)

# Add your dataset repository function
from backend.repositories.dataset_repository import (
    get_dataset_file_path,
)


router = APIRouter(
    prefix="/relationships",
    tags=["Relationship Analysis"],
)


@router.post(
    "/dataset",
    summary="Analyze dataset relationships",
    description=(
        "Analyzes relationships within the specified dataset and prepares "
        "relationship information required for synthetic data generation. "
        "The dataset is identified using dataset_id. "
        "The stored file path is retrieved internally."
    ),
)
def analyze_relationships_api(
    dataset_id: int,
    request: RelationshipAnalysisRequest,
    current_user=Depends(get_current_user),
):
    # Get stored file path using dataset_id
    file_path = get_dataset_file_path(dataset_id)

    # Load dataset
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


@router.get(
    "/{dataset_id}",
    summary="Get relationship analysis",
    description=(
        "Retrieves the previously stored relationship analysis for a "
        "dataset using its dataset ID."
    ),
)
def get_relationship_analysis_api(
    dataset_id: int,
    current_user=Depends(get_current_user),
):
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


@router.post(
    "/{dataset_id}",
    summary="Create dataset relationship",
    description=(
        "Creates and stores relationships between datasets or tables "
        "by defining relational information required for multi-table "
        "synthetic data generation."
    ),
)
def create_dataset_relationship_api(
    request: DatasetRelationshipRequest,
    current_user=Depends(get_current_user),
):
    return create_dataset_relationship(request)