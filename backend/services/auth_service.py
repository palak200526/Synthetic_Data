from backend.repositories.user_repository import (
    create_user,
    get_user_by_email
)

from backend.utils.security import (
    hash_password,
    verify_password,
    create_access_token
)

from backend.services.otp_service import (
    create_otp,
    verify_otp
)

from backend.services.email_service import (
    send_otp_email
)

from backend.repositories.session_repository import (
    create_processing_session
)

from backend.config.database import get_db_connection

# =========================================================
# SIGNUP
# =========================================================

def signup_user(
    username: str,
    email: str,
    password: str
):
    existing_user = get_user_by_email(email)

    if existing_user:
        raise ValueError("Email already registered")

    password_hash = hash_password(password)

    user = create_user(
        username=username,
        email=email,
        password_hash=password_hash
    )

    return user


# =========================================================
# LOGIN - PASSWORD VERIFICATION + SEND OTP
# =========================================================

def login_user(
    email: str,
    password: str
):
    # Find user
    user = get_user_by_email(email)

    if not user:
        raise ValueError("Invalid email or password")

    # user:
    # user_id, username, email, password_hash, created_at

    password_hash = user[3]

    # Verify password
    if not verify_password(password, password_hash):
        raise ValueError("Invalid email or password")

    # Generate OTP
    otp = create_otp(email)

    # Send OTP to registered email
    send_otp_email(
        recipient_email=email,
        otp=otp
    )

    # IMPORTANT:
    # Do NOT generate JWT here.
    # JWT will be generated only after OTP verification.

    return {
        "status": "success",
        "message": "Password verified. OTP sent to your email.",
        "email": email
    }


# =========================================================
# VERIFY OTP - FINAL LOGIN
# =========================================================

def verify_login_otp(
    email: str,
    otp: str
):
    # Find user
    user = get_user_by_email(email)

    if not user:
        raise ValueError("Email is not registered")

    # Verify OTP
    if not verify_otp(email, otp):
        raise ValueError("Invalid or expired OTP")

    # OTP verified → NOW create JWT
    access_token = create_access_token(user[0])

    session = create_auth_session(user[0])

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "session": {
            "session_id": session[0],
            "user_id": session[1],
            "created_at": str(session[2]),
            "expires_at": str(session[3])
        },
        "user": {
            "user_id": user[0],
            "username": user[1],
            "email": user[2],
            "created_at": str(user[4])
        }
    }


def create_auth_session(user_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO sessions (
                user_id,
                created_at,
                expires_at
            )
            VALUES (
                %s,
                NOW(),
                NOW() + INTERVAL '30 minutes'
            )
            RETURNING session_id, user_id, created_at, expires_at
            """,
            (user_id,)
        )

        session = cursor.fetchone()

        connection.commit()

        return session

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()