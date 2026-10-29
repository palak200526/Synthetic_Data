from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
import pandas as pd

from backend.utils.auth_dependency import get_current_user
from backend.services.dataset_service import upload_dataset
from backend.services.dataset_loader import load_dataset
from backend.repositories.session_repository import (
    create_processing_session,
)
from backend.repositories.dataset_repository import (
    get_user_datasets,
    get_dataset_file_path,
    get_dataset_by_id,
    rename_dataset,
    get_dataset_filename,
)

router = APIRouter(
    prefix="",
    tags=["Dataset Upload"],
)


@router.post(
    "/upload",
    summary="Upload dataset files",
    description=(
        "Uploads one or more CSV, XLS, or XLSX dataset files. "
        "For each uploaded dataset, the API validates the file, stores it "
        "in the configured upload location, creates dataset metadata and "
        "assigns a unique dataset ID. A processing session is created for "
        "the upload request and can be associated with an optional dataset "
        "group and domain type."
    ),
)
async def upload_dataset_controller(
    files: list[UploadFile] = File(
        ...,
        description="One or more dataset files to upload."
    ),
    group_id: int | None = Form(
        None,
        description="Optional dataset group ID."
    ),
    domain_type: str | None = Form(
        None,
        description="Optional domain type, such as supply_chain."
    ),
    user_id: int = Depends(get_current_user),
):
    if not files:
        return {
            "status": "error",
            "message": "At least one dataset file is required."
        }

    session_id = create_processing_session(user_id)

    results = []

    for file in files:
        result = await upload_dataset(
            file=file,
            group_id=group_id,
            domain_type=domain_type,
            session_id=session_id,
            user_id=user_id,
        )

        results.append(result)

    return {
        "status": "success",
        "message": "Datasets uploaded successfully.",
        "group_id": group_id,
        "domain_type": domain_type,
        "session_id": session_id,
        "datasets": results,
    }


@router.patch("/datasets/{dataset_id}/rename", summary="Rename an uploaded dataset")
def rename_dataset_controller(dataset_id: int, payload: dict, user_id: int = Depends(get_current_user)):
    current = get_dataset_by_id(dataset_id)
    if not current or current.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    new_name = str(payload.get("file_name", payload.get("name", ""))).strip()
    if not new_name or new_name in {".", ".."} or "/" in new_name or "\\" in new_name:
        raise HTTPException(status_code=400, detail="Enter a valid file name.")
    if len(new_name) > 180:
        raise HTTPException(status_code=400, detail="File name must be 180 characters or fewer.")

    original = get_dataset_filename(dataset_id)
    original_ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if "." not in new_name:
        new_name = f"{new_name}.{original_ext}" if original_ext else new_name
    new_ext = new_name.rsplit(".", 1)[-1].lower() if "." in new_name else ""
    if new_ext != original_ext:
        raise HTTPException(status_code=400, detail=f"Keep the original .{original_ext} file extension.")

    updated = rename_dataset(dataset_id, user_id, new_name)
    if not updated:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return {"status": "success", **updated, "file_name": new_name}


@router.get(
    "/datasets",
    summary="List user datasets",
    description="Retrieves datasets owned by the current user.",
)
def list_datasets_controller(
    user_id: int = Depends(get_current_user),
):
    try:
        datasets = get_user_datasets(user_id=user_id)
        return {
            "status": "success",
            "datasets": datasets,
            "count": len(datasets),
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@router.get(
    "/datasets/{dataset_id}/columns",
    summary="Get dataset columns",
    description="Retrieves the column names, data types, and sample values for a dataset.",
)
def get_dataset_columns_controller(
    dataset_id: int,
    user_id: int = Depends(get_current_user),
):
    try:
        file_path = get_dataset_file_path(dataset_id)
        df = load_dataset(str(file_path))
        columns = [
            {
                "name": str(col),
                "type": str(df[col].dtype),
                "is_numeric": bool(pd.api.types.is_numeric_dtype(df[col])),
                "unique_count": int(df[col].nunique(dropna=True)),
                "sample_values": [str(x) for x in df[col].dropna().head(3).tolist()],
            }
            for col in df.columns
        ]
        return {
            "status": "success",
            "dataset_id": dataset_id,
            "columns": columns,
            "column_names": [str(c) for c in df.columns],
        }
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load columns for dataset {dataset_id}: {error}",
        )