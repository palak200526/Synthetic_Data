from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.config.database import get_db_connection
from backend.repositories.user_repository import (
    get_user_with_password_by_id,
    update_username,
    username_exists,
    update_password_hash,
)
from backend.utils.auth_dependency import get_current_user
from backend.utils.security import hash_password, verify_password

router = APIRouter(prefix="/account", tags=["Account"])


class ProfileUpdateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_. -]+$")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


def _iso(value: Any):
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


@router.patch("/profile", summary="Update the authenticated user's profile")
def update_profile(request: ProfileUpdateRequest, user_id: int = Depends(get_current_user)):
    username = request.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must contain at least 3 characters")
    try:
        if username_exists(username, user_id):
            raise HTTPException(status_code=409, detail="That username is already in use")
        row = update_username(user_id, username)
        return {
            "user_id": row[0],
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "created_at": _iso(row[3]),
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not update profile") from exc


@router.post("/change-password", summary="Change the authenticated user's password")
def change_password(request: PasswordChangeRequest, user_id: int = Depends(get_current_user)):
    try:
        user = get_user_with_password_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Account not found")
        if not verify_password(request.current_password, user[3]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if request.current_password == request.new_password:
            raise HTTPException(status_code=400, detail="New password must be different from the current password")
        updated = update_password_hash(user_id, hash_password(request.new_password))
        if not updated:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"status": "success", "message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not change password") from exc


@router.get("/activity", summary="Get recent activity for the authenticated user")
def recent_activity(limit: int = 12, user_id: int = Depends(get_current_user)):
    limit = max(1, min(limit, 30))
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        activities = []

        # Upload events are strictly scoped to the authenticated user.
        cursor.execute(
            """
            SELECT dataset_id, COALESCE(dataset_name, file_name, 'Dataset') AS title,
                   uploaded_at
            FROM datasets
            WHERE user_id = %s
            ORDER BY uploaded_at DESC NULLS LAST, dataset_id DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        for row in cursor.fetchall():
            activities.append({
                "id": f"dataset-{row[0]}",
                "type": "dataset",
                "title": f"Dataset uploaded: {row[1]}",
                "status": "Uploaded",
                "occurred_at": _iso(row[2]),
                "dataset_id": row[0],
            })

        cursor.execute(
            """
            SELECT job_id, file_name, model_name, status, created_at, updated_at
            FROM generation_jobs
            WHERE user_id = %s
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT %s
            """,
            (user_id, limit),
        )
        for row in cursor.fetchall():
            status_text = str(row[3] or "unknown").replace("_", " ").title()
            activities.append({
                "id": f"job-{row[0]}",
                "type": "generation",
                "title": f"Generation: {row[1] or 'Dataset'} · {row[2] or 'Model'}",
                "status": status_text,
                "occurred_at": _iso(row[5] or row[4]),
                "job_id": str(row[0]),
            })

        activities.sort(key=lambda item: item.get("occurred_at") or "", reverse=True)
        return {"items": activities[:limit]}
    except Exception as exc:
        # A failed activity feed should not expose database details.
        raise HTTPException(status_code=500, detail="Could not load recent activity") from exc
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
