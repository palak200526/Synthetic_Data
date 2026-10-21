from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from backend.repositories.dataset_repository import get_dataset_user_id
from backend.repositories.generation_repository import (
    get_generated_result_by_id,
    get_generated_results_for_group_id,
    get_generated_result_by_run,
    get_latest_generated_result_by_dataset_id,
    get_latest_generated_result_for_user,
)
from backend.services.report_service import REPORTS_DIR, ensure_pdf_report, generate_report
from backend.utils.auth_dependency import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Downloads"])


def _candidate_file_paths(raw_path: str | None):
    """Resolve stored paths against common app roots without assuming cwd."""
    if not raw_path:
        return []
    stored = Path(str(raw_path)).expanduser()
    if stored.is_absolute():
        return [stored]
    here = Path(__file__).resolve()
    roots = [
        Path.cwd(),
        here.parents[2],  # repository root: <repo>/backend/controllers/file.py
        here.parents[1],  # backend root
        Path.cwd() / "backend",
    ]
    candidates = []
    seen = set()
    for root in roots:
        candidate = (root / stored).resolve()
        if str(candidate) not in seen:
            seen.add(str(candidate))
            candidates.append(candidate)
    return candidates


def _generated_roots():
    here = Path(__file__).resolve()
    roots = [
        Path.cwd() / "data" / "generated",
        Path.cwd() / "backend" / "data" / "generated",
        here.parents[2] / "data" / "generated",
        here.parents[1] / "data" / "generated",
    ]
    unique = []
    seen = set()
    for root in roots:
        root = root.resolve()
        if str(root) not in seen:
            seen.add(str(root))
            unique.append(root)
    return unique


@router.get(
    "/download/multi-table",
    summary="Download all generated tables from a multi-table group",
    description="Packages the generated CSV for every table in this group into one ZIP archive.",
)
def download_multi_table_group(
    result_id: int = Query(..., description="Any generated result ID from the multi-table group"),
    user_id: int = Depends(get_current_user),
):
    reference = get_generated_result_by_id(result_id)
    if not reference:
        raise HTTPException(status_code=404, detail=f"Generated result {result_id} not found.")

    model_name = str(reference.get("model_name") or "")
    match = re.search(r"(?:^|_)group_(\d+)$", model_name, flags=re.IGNORECASE)
    if not match:
        raise HTTPException(status_code=400, detail="This result is not associated with a multi-table generation group.")
    group_id = int(match.group(1))

    if get_dataset_user_id(int(reference["dataset_id"])) != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Use actual generated results, not every dataset currently assigned to the
    # group: groups can contain source tables that weren't part of this run.
    result_rows = get_generated_results_for_group_id(group_id)
    if not result_rows:
        raise HTTPException(status_code=404, detail=f"No generated results are registered for group {group_id}.")

    archive = io.BytesIO()
    included_ids = set()
    missing = []
    used_names = set()

    # First try registered paths, resolving them against likely app roots.
    resolved_by_dataset = {}
    for row in result_rows:
        dataset_id = int(row["dataset_id"])
        if get_dataset_user_id(dataset_id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied for one or more generated tables.")
        found = None
        for candidate_path in _candidate_file_paths(row.get("file_path")):
            if candidate_path.is_file():
                found = candidate_path
                break
        if found:
            resolved_by_dataset[dataset_id] = (row, found)

    # Recover CSVs saved successfully even if their result-row insert failed.
    # Search all known generated roots and use the newest matching file per table.
    group_pattern = re.compile(rf"^synthetic_dataset_(\d+)_.*_group_{group_id}\.csv$", re.IGNORECASE)
    filesystem_candidates = {}
    for root in _generated_roots():
        if not root.is_dir():
            continue
        for file_path in root.rglob("*.csv"):
            match_file = group_pattern.match(file_path.name)
            if not match_file or not file_path.is_file():
                continue
            dataset_id = int(match_file.group(1))
            if dataset_id in resolved_by_dataset:
                continue
            current = filesystem_candidates.get(dataset_id)
            if current is None or file_path.stat().st_mtime > current.stat().st_mtime:
                filesystem_candidates[dataset_id] = file_path

    # Package every known generated result, plus any recovered on-disk table.
    files_to_package = list(resolved_by_dataset.items())
    for dataset_id, path in filesystem_candidates.items():
        if get_dataset_user_id(dataset_id) != user_id:
            continue
        files_to_package.append((dataset_id, ({"file_name": path.name}, path)))

    if not files_to_package:
        raise HTTPException(
            status_code=404,
            detail=(f"No generated CSV files were found for group {group_id}. "
                    "Check that the generation output files still exist under data/generated."),
        )

    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for dataset_id, item in files_to_package:
                row, path = item
                name = Path(str(row.get("file_name") or path.name)).name
                if not name.lower().endswith(".csv"):
                    name += ".csv"
                if name in used_names:
                    name = f"dataset_{dataset_id}_{name}"
                used_names.add(name)
                bundle.write(path, arcname=name)
                included_ids.add(dataset_id)

            # A missing registered path is not fatal when other generated files
            # are available; report only if a result row cannot be recovered.
            for row in result_rows:
                dataset_id = int(row["dataset_id"])
                if dataset_id not in included_ids:
                    missing.append(str(row.get("file_name") or f"dataset_{dataset_id}"))
            if missing:
                raise HTTPException(
                    status_code=409,
                    detail=("Some generated tables have no accessible CSV file: " + ", ".join(missing)
                            + ". The download searched stored paths and data/generated folders."),
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to package multi-table download for result %s", result_id)
        raise HTTPException(status_code=500, detail="Failed to package multi-table dataset download.") from exc

    archive.seek(0)
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="datrixa_multitable_group_{group_id}.zip"'},
    )


@router.get(
    "/download",
    summary="Download generated dataset or report",
    description="Streams the requested artifact (dataset CSV, evaluation report PDF/HTML/JSON/CSV) as a downloadable file.",
)
def download_artifact(
    dataset_id: Optional[int] = Query(None, description="Source dataset ID"),
    run_id: Optional[int] = Query(None, description="Generation run ID"),
    result_id: Optional[int] = Query(None, description="Generated result ID"),
    type: str = Query("dataset", description="Artifact type: dataset | report | evaluation"),
    format: str = Query("json", description="Report format: pdf | json | html | csv"),
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

        # PDF report (built on demand from the report data)
        if fmt == "pdf":
            try:
                pdf_path = ensure_pdf_report(result_id=res_id, user_id=user_id)
            except Exception as exc:
                logger.exception("Failed to build PDF report: %s", exc)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to build PDF report: {str(exc)}",
                )
            return FileResponse(
                path=pdf_path,
                media_type="application/pdf",
                filename=pdf_path.name,
            )

        # Filename mappings
        file_map = {
            "json": (f"report_dataset_{dataset_id}_result_{res_id}.json", "application/json"),
            "html": (f"report_dataset_{dataset_id}_result_{res_id}.html", "text/html"),
            "csv": (f"report_dataset_{dataset_id}_result_{res_id}_summary.csv", "text/csv"),
        }

        if fmt not in file_map:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{fmt}'. Choose from: pdf, json, html, csv.",
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