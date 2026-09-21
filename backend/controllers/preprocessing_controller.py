from fastapi import APIRouter

from backend.services.dataset_loader import load_dataset
from backend.services.preprocessing_service import preprocess_dataset


router = APIRouter(
    prefix="/preprocess",
    tags=["Preprocessing"],
)


@router.post("/{filename}")
def preprocess(filename: str):

    file_path = f"data/uploads/{filename}"

    dataframe = load_dataset(file_path)

    result = preprocess_dataset(dataframe)

    return {
        "status": "success",
        "message": "Dataset preprocessing completed successfully.",
        "filename": filename,
        "row_count": len(result["dataframe"]),
        "column_count": len(result["dataframe"].columns),
        "numerical_columns": result["numerical_columns"],
        "categorical_columns": result["categorical_columns"],
        "outliers": result["outliers"],
        "validation": result["validation"],
    }