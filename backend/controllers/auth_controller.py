from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr

from backend.utils.auth_dependency import get_current_user

from backend.schemas.auth_schema import (
    SignupRequest,
    LoginRequest,
    UserResponse,
)

from backend.services.auth_service import (
    signup_user,
    login_user,
    verify_login_otp,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# =========================
# OTP Request Schema
# =========================

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


# =========================
# Login OTP Response Schema
# =========================

class LoginOTPResponse(BaseModel):
    status: str
    message: str
    email: EmailStr


# =========================
# Signup
# =========================

@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates a new user account using username, email, and password. "
        "The password is securely hashed before being stored."
    )
)
def signup(request: SignupRequest):

    try:
        user = signup_user(
            username=request.username,
            email=request.email,
            password=request.password
        )

        return UserResponse(
            user_id=user[0],
            username=user[1],
            email=user[2],
            created_at=str(user[3])
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =========================
# Login - Password Verification
# =========================

@router.post(
    "/login",
    response_model=LoginOTPResponse,
    summary="Login with password",
    description=(
        "Verifies the user's email and password. If the credentials "
        "are valid, a one-time password is generated and sent to the "
        "user's registered email. The JWT access token is issued only "
        "after successful OTP verification."
    )
)
def login(request: LoginRequest):

    try:
        return login_user(
            email=request.email,
            password=request.password
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    except Exception as e:
        import traceback
        print("LOGIN ERROR:", e)
        traceback.print_exc()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# =========================
# Verify Login OTP
# =========================

@router.post(
    "/login/verify-otp",
    summary="Verify login OTP",
    description=(
        "Verifies the OTP sent to the user's registered email after "
        "successful password verification. A JWT access token is "
        "generated only when the OTP is valid and has not expired."
    )
)
def verify_login_otp_api(
    request: VerifyOTPRequest,
):

    try:
        result = verify_login_otp(
            email=request.email,
            otp=request.otp
        )

        return {
            "status": "success",
            "message": "Login successful.",
            **result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    except Exception as e:
        print("OTP VERIFICATION ERROR:", e)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify OTP."
        )


# =========================
# Current User
# =========================

@router.get(
    "/me",
    summary="Get current authenticated user",
    description=(
        "Returns the user ID of the currently authenticated user. "
        "Requires a valid JWT access token."
    )
)
def get_me(
    user_id: int = Depends(get_current_user)
):
    return {
        "message": "Authentication successful",
        "user_id": user_id
    }