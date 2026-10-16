from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.utils.security import (
    create_access_token,
    decode_access_token,
    token_needs_refresh,
)


security = HTTPBearer()


def get_current_user(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    try:
        payload = decode_access_token(token)

        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        # Sliding session: hand the browser a fresh token once the current one
        # is past half of its life. Best effort - never fails the request.
        try:
            if token_needs_refresh(payload):
                response.headers["X-New-Token"] = create_access_token(int(user_id))
        except Exception:
            pass

        return int(user_id)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )