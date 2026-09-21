from fastapi import APIRouter

from backend.services.profiling_service import get_profile


router = APIRouter()


@router.get("/profile/{filename}")
def get_profile_controller(filename: str):
    return get_profile(filename)