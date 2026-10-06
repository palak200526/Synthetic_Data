from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.repositories.generation_repository import (
    get_latest_generated_result_by_dataset_id,
    get_latest_generated_result_for_user,
)
from backend.repositories.report_repository import list_reports_for_user
from backend.schemas.api_schema import ReportGenerateRequest, ReportResponse
from backend.services.report_service import (
    generate_report,
    get_report_for_result,
)
from backend.utils.auth_dependency import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["Reports"],
)


@router.get(
    "/report",
    summary="Get or view evaluation report",
    description="Retrieve report data for a generated dataset result or list available reports.",
    response_model=ReportResponse,
)
def get_report(
    result_id: Optional[int] = Query(None, description="Generated result ID"),
    dataset_id: Optional[int] = Query(None, description="Dataset ID"),
    current_user: int = Depends(get_current_user),
):
    try:
        # Case 1: result_id provided
        if result_id is not None:
            report_data = get_report_for_result(
                result_id=result_id,
                user_id=current_user,
            )
            return {
                "status": "success",
                "message": "Report retrieved successfully.",
                "data": report_data,
            }

        # Case 2: dataset_id provided
        if dataset_id is not None:
            latest_result = get_latest_generated_result_by_dataset_id(dataset_id)
            if not latest_result:
                raise HTTPException(
                    status_code=404,
                    detail=f"No generated results found for dataset {dataset_id}.",
                )
            report_data = get_report_for_result(
                result_id=latest_result["result_id"],
                user_id=current_user,
            )
            return {
                "status": "success",
                "message": "Report retrieved successfully.",
                "data": report_data,
            }

        # Case 3: neither provided -> list reports for current user and auto-load latest
        user_reports = list_reports_for_user(current_user)
        latest_report_data = None
        if user_reports:
            try:
                latest_report_data = get_report_for_result(
                    result_id=user_reports[0]["result_id"],
                    user_id=current_user,
                )
            except Exception as exc:
                logger.warning("Could not fetch latest report: %s", exc)
        else:
            latest_gen = get_latest_generated_result_for_user(current_user)
            if latest_gen:
                try:
                    latest_report_data = generate_report(
                        result_id=latest_gen["result_id"],
                        user_id=current_user,
                    )
                    user_reports = list_reports_for_user(current_user)
                except Exception as exc:
                    logger.warning("Could not auto-generate report: %s", exc)

        return {
            "status": "success",
            "message": "User reports list retrieved.",
            "data": {
                "reports": user_reports,
                "latest_report": latest_report_data,
            },
        }

    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Error processing get_report: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve report: {str(exc)}",
        )


@router.post(
    "/report",
    summary="Generate evaluation report",
    description="Generates and persists full evaluation report across statistical, correlation, ML, privacy, and text dimensions.",
    response_model=ReportResponse,
)
def create_report(
    payload: ReportGenerateRequest,
    current_user: int = Depends(get_current_user),
):
    try:
        report_data = generate_report(
            result_id=payload.result_id,
            user_id=current_user,
            format=payload.format or "json",
        )
        return {
            "status": "success",
            "message": "Report generated successfully.",
            "data": report_data,
        }
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Error generating report: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(exc)}",
        )