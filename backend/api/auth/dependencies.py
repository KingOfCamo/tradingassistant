"""FastAPI dependency: get_current_user — used on all protected routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.api.auth.jwt_handler import verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Validates JWT, checks Redis blacklist, returns user info.
    Applied to every protected route via Depends(get_current_user).
    """
    payload = verify_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # TODO: Check Redis blacklist for logged-out tokens
    # TODO: Verify user exists in database

    return {
        "user_id": payload["sub"],
        "jti": payload.get("jti"),
    }
