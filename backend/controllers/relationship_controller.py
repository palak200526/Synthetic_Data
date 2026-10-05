from fastapi import APIRouter, Depends, HTTPException
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
    get_dataset_relationships,
    delete_dataset_relationship,
)

from backend.repositories.dataset_repository import (
    get_dataset_file_path,
    get_dataset_by_id,
    assign_dataset_to_group,
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
    "/group/{group_id}",
    summary="Get dataset relationships for a group",
    description="Retrieves all relationships configured for datasets within a group, enriched with table names.",
)
def get_group_relationships_api(
    group_id: int,
    current_user=Depends(get_current_user),
):
    try:
        relationships = get_dataset_relationships(group_id)
        enriched = []
        for r in relationships:
            p_info = get_dataset_by_id(r["parent_dataset_id"])
            c_info = get_dataset_by_id(r["child_dataset_id"])
            p_name = (p_info.get("dataset_name") or p_info.get("file_name")) if p_info else f"Dataset {r['parent_dataset_id']}"
            c_name = (c_info.get("dataset_name") or c_info.get("file_name")) if c_info else f"Dataset {r['child_dataset_id']}"
            enriched.append({
                **r,
                "parent_table_name": p_name,
                "child_table_name": c_name,
            })

        return {
            "status": "success",
            "group_id": group_id,
            "relationships": enriched,
            "count": len(enriched),
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


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
    "",
    summary="Create dataset relationship",
    description="Creates and stores a relationship between datasets for multi-table synthetic data generation.",
)
def create_relationship_direct_api(
    request: DatasetRelationshipRequest,
    current_user=Depends(get_current_user),
):
    try:
        result = create_dataset_relationship(request)
        try:
            assign_dataset_to_group(request.parent_dataset_id, request.group_id)
            assign_dataset_to_group(request.child_dataset_id, request.group_id)
        except Exception:
            pass
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post(
    "/{dataset_id}",
    summary="Create dataset relationship (legacy path)",
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
    try:
        result = create_dataset_relationship(request)
        try:
            assign_dataset_to_group(request.parent_dataset_id, request.group_id)
            assign_dataset_to_group(request.child_dataset_id, request.group_id)
        except Exception:
            pass
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.delete(
    "/{relationship_id}",
    summary="Delete dataset relationship",
    description="Deletes a relationship between datasets by relationship ID.",
)
def delete_dataset_relationship_api(
    relationship_id: int,
    current_user=Depends(get_current_user),
):
    try:
        success = delete_dataset_relationship(relationship_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Relationship {relationship_id} not found.",
            )
        return {
            "status": "success",
            "message": f"Relationship {relationship_id} deleted successfully.",
            "relationship_id": relationship_id,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )