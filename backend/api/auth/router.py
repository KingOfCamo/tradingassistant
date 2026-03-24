"""Auth endpoints: login, refresh, logout."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.api.auth.dependencies import get_current_user
from backend.api.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
)
from backend.api.auth.rate_limiter import limiter
from backend.api.auth.audit import log_auth_event

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(credentials: LoginRequest, request: Request):
    """Rate limited: 5 attempts per IP per 15 minutes."""
    # TODO: Validate against database user
    # For now, stub — will be fully implemented in Prompt B
    await log_auth_event(
        "login_attempt",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Auth not yet configured — run create_user.py first",
    )


@router.post("/refresh")
async def refresh(request: Request):
    """Validates refresh token, rotates to new token pair."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Blacklists current token in Redis."""
    return {"message": "Logged out"}
