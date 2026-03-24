"""JWT token creation, validation, and refresh rotation."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from fastapi import HTTPException, status

from backend.config import settings

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours — matches Cloudflare session
REFRESH_TOKEN_EXPIRE_DAYS = 30


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "jti": str(uuid4()),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (encoded_token, jti) so jti can be stored in Redis."""
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    payload = {
        "sub": user_id,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)
    return token, jti


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
        if payload.get("sub") is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token",
        )
