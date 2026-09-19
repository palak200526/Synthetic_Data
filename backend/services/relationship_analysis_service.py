import pandas as pd
from pathlib import Path

from backend.repositories.dataset_repository import (
    get_dataset_filename,
)

from backend.services.dataset_loader import load_dataset

from backend.repositories.relationship_repository import (
    save_relationship_analysis,
    get_relationship_analysis,
    save_dataset_relationship,
)

UPLOAD_DIRECTORY = Path("data/uploads")


def analyze_relationships(dataframe: pd.DataFrame):
    if dataframe.empty:
        raise ValueError("Dataset cannot be empty.")

    numerical_dataframe = dataframe.select_dtypes(
        include="number"
    )

    if numerical_dataframe.empty:
        raise ValueError(
            "Dataset does not contain numerical columns."
        )

    correlation_matrix = numerical_dataframe.corr()
    covariance_matrix = numerical_dataframe.cov()

    return {
        "numerical_columns": numerical_dataframe.columns.tolist(),
        "correlation_matrix": correlation_matrix,
        "covariance_matrix": covariance_matrix,
    }

def create_dataset_relationship(request):

    # 1. Validate parent and child datasets are different
    if request.parent_dataset_id == request.child_dataset_id:
        raise ValueError(
            "Parent and child dataset must be different."
        )

    # 2. Get parent dataset filename
    parent_filename = get_dataset_filename(
        request.parent_dataset_id
    )

    # 3. Get child dataset filename
    child_filename = get_dataset_filename(
        request.child_dataset_id
    )

    # 4. Load parent dataset
    parent_dataframe = load_dataset(
        str(UPLOAD_DIRECTORY / parent_filename)
    )

    # 5. Load child dataset
    child_dataframe = load_dataset(
        str(UPLOAD_DIRECTORY / child_filename)
    )

    # 6. Validate parent column
    if request.parent_column not in parent_dataframe.columns:
        raise ValueError(
            f"Parent column '{request.parent_column}' "
            f"does not exist in dataset "
            f"{request.parent_dataset_id}."
        )

    # 7. Validate child column
    if request.child_column not in child_dataframe.columns:
        raise ValueError(
            f"Child column '{request.child_column}' "
            f"does not exist in dataset "
            f"{request.child_dataset_id}."
        )

    # 8. Save relationship
    result = save_dataset_relationship(
        group_id=request.group_id,
        parent_dataset_id=request.parent_dataset_id,
        parent_column=request.parent_column,
        child_dataset_id=request.child_dataset_id,
        child_column=request.child_column,
        relationship_type=request.relationship_type,
    )

    return {
        "status": "success",
        "message": "Dataset relationship created successfully.",
        "data": {
            "relationship_id": result["relationship_id"],
            "group_id": request.group_id,
            "parent_dataset_id": request.parent_dataset_id,
            "parent_column": request.parent_column,
            "child_dataset_id": request.child_dataset_id,
            "child_column": request.child_column,
            "relationship_type": request.relationship_type,
            "created_at": result["created_at"],
        },
    }