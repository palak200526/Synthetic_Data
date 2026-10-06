from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.repositories.dataset_repository import (
    get_dataset_user_id,
)
from backend.repositories.generation_repository import (
    get_generated_result_by_id,
    get_generated_result_by_run,
    get_latest_generated_result_by_dataset_id,
    get_latest_generated_result_for_user,
)
from backend.services.report_service import (
    REPORTS_DIR,
    generate_report,
)
from backend.utils.auth_dependency import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["Downloads"],
)


@router.get(
    "/download",
    summary="Download generated dataset or report",
    description="Streams the requested artifact (dataset CSV, evaluation report HTML/JSON/CSV) as a downloadable file.",
)
def download_artifact(
    dataset_id: Optional[int] = Query(None, description="Source dataset ID"),
    run_id: Optional[int] = Query(None, description="Generation run ID"),
    result_id: Optional[int] = Query(None, description="Generated result ID"),
    type: str = Query("dataset", description="Artifact type: dataset | report | evaluation"),
    format: str = Query("json", description="Report format: json | html | csv"),
    user_id: int = Depends(get_current_user),
):
    # ------------------------------------------------------------------
    # 1. Resolve dataset_id and generated_result
    # ------------------------------------------------------------------
    target_result = None

    if result_id is not None:
        target_result = get_generated_result_by_id(result_id)
        if not target_result:
            raise HTTPException(status_code=404, detail=f"Generated result {result_id} not found.")
        dataset_id = target_result["dataset_id"]

    elif run_id is not None:
        target_result = get_generated_result_by_run(run_id)
        if not target_result:
            raise HTTPException(status_code=404, detail=f"No generated result for run {run_id}.")
        dataset_id = target_result.get("dataset_id")
        if dataset_id is None and target_result.get("result_id"):
            res_full = get_generated_result_by_id(target_result["result_id"])
            if res_full:
                dataset_id = res_full["dataset_id"]

    elif dataset_id is not None:
        # Check if the dataset_id is actually a result_id!
        res_by_id = get_generated_result_by_id(dataset_id)
        if res_by_id:
            target_result = res_by_id
            dataset_id = res_by_id["dataset_id"]
        else:
            target_result = get_latest_generated_result_by_dataset_id(dataset_id)

    if target_result is None:
        target_result = get_latest_generated_result_for_user(user_id)
        if target_result:
            dataset_id = target_result["dataset_id"]

    if target_result is None or dataset_id is None:
        raise HTTPException(
            status_code=400,
            detail="No generated dataset or report available for download.",
        )

    # ------------------------------------------------------------------
    # 2. Ownership verification
    # ------------------------------------------------------------------
    owner_id = get_dataset_user_id(dataset_id)
    if owner_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # ------------------------------------------------------------------
    # 3. Handle dataset download
    # ------------------------------------------------------------------
    if type == "dataset":
        if not target_result:
            raise HTTPException(
                status_code=404,
                detail=f"No generated dataset found for dataset {dataset_id}.",
            )

        file_path_str = target_result.get("file_path")
        if not file_path_str:
            raise HTTPException(status_code=404, detail="File path not recorded.")

        file_path = Path(file_path_str)
        if not file_path.is_absolute():
            file_path = Path.cwd() / file_path

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File missing on server.")

        return FileResponse(
            path=file_path,
            media_type="text/csv",
            filename=target_result.get("file_name", file_path.name),
        )

    # ------------------------------------------------------------------
    # 4. Handle report download (HTML, JSON, CSV)
    # ------------------------------------------------------------------
    if type == "report":
        if not target_result:
            raise HTTPException(
                status_code=404,
                detail=f"Cannot generate report: no generated results for dataset {dataset_id}.",
            )

        res_id = target_result["result_id"]
        fmt = (format or "json").lower().strip()

        # Filename mappings
        file_map = {
            "json": (f"report_dataset_{dataset_id}_result_{res_id}.json", "application/json"),
            "html": (f"report_dataset_{dataset_id}_result_{res_id}.html", "text/html"),
            "csv": (f"report_dataset_{dataset_id}_result_{res_id}_summary.csv", "text/csv"),
        }

        if fmt not in file_map:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{fmt}'. Choose from: json, html, csv.",
            )

        filename, media_type = file_map[fmt]
        file_path = REPORTS_DIR / filename

        # If file does not exist yet, generate it on demand
        if not file_path.exists():
            try:
                generate_report(result_id=res_id, user_id=user_id, format=fmt)
            except Exception as exc:
                logger.exception("Failed to generate report for download: %s", exc)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate report: {str(exc)}",
                )

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Report artifact could not be found.")

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
        )

    # ------------------------------------------------------------------
    # 5. Unsupported type
    # ------------------------------------------------------------------
    raise HTTPException(
        status_code=400,
        detail=f"Download type '{type}' is not supported. Use 'dataset' or 'report'.",
    )