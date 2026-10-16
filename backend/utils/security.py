from passlib.context import CryptContext
from jose import jwt
import time
from datetime import datetime, timedelta

from backend.config.settings import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_SECRET_KEY,
)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES comes from settings (env, default 24 h).


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )


def token_needs_refresh(payload: dict) -> bool:
    """True once less than half of the token's lifetime is left (sliding session)."""
    exp = payload.get("exp")
    if exp is None:
        return False
    remaining = float(exp) - time.time()
    return remaining < (ACCESS_TOKEN_EXPIRE_MINUTES * 60) / 2
