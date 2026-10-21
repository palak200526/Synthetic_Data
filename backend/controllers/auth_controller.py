from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr

from backend.utils.auth_dependency import get_current_user
from backend.repositories.user_repository import get_user_by_id
from backend.schemas.auth_schema import SignupRequest, LoginRequest, UserResponse
from backend.services.auth_service import signup_user, login_user, verify_login_otp

router = APIRouter(prefix="/auth", tags=["Authentication"])


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class LoginOTPResponse(BaseModel):
    status: str
    message: str
    email: EmailStr


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates a new user account using username, email, and password. "
        "The password is securely hashed before being stored."
    ),
)
def signup(request: SignupRequest):
    try:
        user = signup_user(
            username=request.username,
            email=request.email,
            password=request.password,
        )
        return UserResponse(
            user_id=user[0],
            username=user[1],
            email=user[2],
            created_at=str(user[3]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/login",
    response_model=LoginOTPResponse,
    summary="Login with password",
    description=(
        "Verifies the user's email and password. If the credentials are valid, "
        "a one-time password is sent to the registered email. The JWT token is "
        "issued only after successful OTP verification."
    ),
)
def login(request: LoginRequest):
    try:
        return login_user(email=request.email, password=request.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except Exception as exc:
        import traceback
        print("LOGIN ERROR:", exc)
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed.",
        )


@router.post("/login/verify-otp", summary="Verify login OTP")
def verify_login_otp_api(request: VerifyOTPRequest):
    try:
        result = verify_login_otp(email=request.email, otp=request.otp)
        return {"status": "success", "message": "Login successful.", **result}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except Exception as exc:
        print("OTP VERIFICATION ERROR:", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify OTP.",
        )


@router.get(
    "/me",
    summary="Get current authenticated user",
    description="Returns the profile for the authenticated user identified by the JWT.",
)
def get_me(user_id: int = Depends(get_current_user)):
    """Return actual profile fields; AuthContext stores this response as `user`."""
    try:
        user = get_user_by_id(user_id)
    except Exception as exc:
        print("AUTH ME PROFILE ERROR:", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the current user profile.",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # get_user_by_id returns: user_id, username, email, created_at.
    return {
        "message": "Authentication successful",
        "user_id": user[0],
        "id": user[0],
        "username": user[1],
        "name": user[1],
        "email": user[2],
        "created_at": user[3].isoformat() if hasattr(user[3], "isoformat") else user[3],
    }
