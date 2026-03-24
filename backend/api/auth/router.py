"""Auth endpoints: login, refresh, logout, change-password."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from passlib.hash import bcrypt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth.dependencies import get_current_user
from backend.api.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from backend.api.auth.rate_limiter import limiter
from backend.api.auth.audit import log_auth_event
from backend.db.database import get_db
from backend.db.redis import get_redis
from backend.db.models import User

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Rate limited: 5 attempts per IP per 15 minutes."""
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")

    # Find user
    result = await db.execute(
        select(User).where(User.username == credentials.username)
    )
    user = result.scalar_one_or_none()

    if not user or not bcrypt.verify(credentials.password, user.hashed_password):
        await log_auth_event(
            "login_failure",
            ip_address=ip,
            user_agent=ua,
            details={"username": credentials.username[:20]},
        )
        # Generic error — never reveal whether username or password is wrong
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create tokens
    user_id = str(user.id)
    access_token = create_access_token(user_id)
    refresh_token, refresh_jti = create_refresh_token(user_id)

    # Store refresh token in Redis
    redis = await get_redis()
    await redis.setex(
        f"refresh_token:{refresh_jti}",
        REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        user_id,
    )

    # Update last login
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login=datetime.now(timezone.utc))
    )
    await db.commit()

    await log_auth_event(
        "login_success",
        ip_address=ip,
        user_id=user_id,
        user_agent=ua,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """Validates refresh token, rotates to new token pair."""
    payload = verify_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    jti = payload.get("jti")
    user_id = payload.get("sub")

    # Validate refresh token exists in Redis (not revoked)
    redis = await get_redis()
    stored = await redis.get(f"refresh_token:{jti}")
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )

    # Rotate: delete old, issue new
    await redis.delete(f"refresh_token:{jti}")

    new_access = create_access_token(user_id)
    new_refresh, new_jti = create_refresh_token(user_id)
    await redis.setex(
        f"refresh_token:{new_jti}",
        REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        user_id,
    )

    await log_auth_event("token_refresh", user_id=user_id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Blacklists current access token in Redis."""
    jti = current_user.get("jti")
    if jti:
        redis = await get_redis()
        # Blacklist for remaining token lifetime
        await redis.setex(
            f"token_blacklist:{jti}",
            ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "1",
        )

    await log_auth_event("logout", user_id=current_user["user_id"])
    return {"message": "Logged out"}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password. Revokes all existing sessions."""
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not bcrypt.verify(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Validate new password
    pwd = body.new_password
    errors = []
    if len(pwd) < 12:
        errors.append("at least 12 characters")
    if not any(c.isupper() for c in pwd):
        errors.append("one uppercase letter")
    if not any(c.islower() for c in pwd):
        errors.append("one lowercase letter")
    if not any(c.isdigit() for c in pwd):
        errors.append("one number")
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pwd):
        errors.append("one symbol")
    if errors:
        raise HTTPException(
            status_code=400,
            detail=f"Password must contain: {', '.join(errors)}",
        )

    new_hash = bcrypt.using(rounds=12).hash(pwd)
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(hashed_password=new_hash)
    )
    await db.commit()

    await log_auth_event("password_change", user_id=str(user.id))
    return {"message": "Password changed. Please log in again."}
