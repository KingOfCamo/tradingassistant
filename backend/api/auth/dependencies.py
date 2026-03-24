"""FastAPI dependency: get_current_user — used on all protected routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.api.auth.jwt_handler import verify_token
from backend.db.redis import get_redis

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

    # Check Redis blacklist for logged-out tokens
    jti = payload.get("jti")
    if jti:
        try:
            redis = await get_redis()
            blacklisted = await redis.get(f"token_blacklist:{jti}")
            if blacklisted:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )
        except (ConnectionError, OSError):
            # If Redis is down, allow the request (fail open for availability)
            pass

    return {
        "user_id": payload["sub"],
        "jti": jti,
    }
