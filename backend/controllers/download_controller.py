from fastapi import APIRouter, Depends

from backend.schemas.api_schema import DownloadResponse

from backend.utils.auth_dependency import get_current_user

router = APIRouter(
    prefix="",
    tags=["Downloads"],
)


@router.get(
    "/download",
    summary="Download generated dataset",
    description=(
        "Downloads the generated synthetic dataset produced by the platform. "
        "The endpoint returns the generated output file for further use."
    ),
    response_model=DownloadResponse
)
def download_result(
    current_user=Depends(get_current_user),
):
    return {
        "status": "success",
        "message": "Download endpoint is ready."
    }


from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.utils.auth_dependency import get_current_user
from backend.repositories.dataset_repository import (
    get_dataset_filename, get_dataset_user_id, get_dataset_file_path,
)
from backend.repositories.generation_repository import (
    # you'll need a helper to fetch generated_results by run_id
    # see below
    get_generated_result_by_run,
)


router = APIRouter(prefix="", tags=["Downloads"])


@router.get(
    "/download",
    summary="Download generated dataset / report",
    description="Streams the requested artifact as a file.",
)
def download_result(
    dataset_id: int = Query(..., description="Source dataset ID"),
    run_id: int | None = Query(None, description="Generation run ID"),
    type: str = Query("dataset", description="dataset | report | evaluation"),
    user_id: int = Depends(get_current_user),
):
    # --- ownership check ---
    if get_dataset_user_id(dataset_id) != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    if type == "dataset":
        if run_id is None:
            raise HTTPException(status_code=400, detail="run_id is required.")

        result = get_generated_result_by_run(run_id)
        if not result:
            raise HTTPException(status_code=404, detail="Generated dataset not found.")

        file_path = Path(result["file_path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File missing on server.")

        return FileResponse(
            path=file_path,
            media_type="text/csv",
            filename=result["file_name"],
        )

    raise HTTPException(
        status_code=501,
        detail=f"Download type '{type}' is not implemented yet.",
    )