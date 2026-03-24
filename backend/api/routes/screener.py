"""Stock screener endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/screener")
async def run_screener(user: dict = Depends(get_current_user)):
    """Run custom screener with user-defined filters."""
    return {"results": []}


@router.get("/screener/presets")
async def get_presets(user: dict = Depends(get_current_user)):
    return {"presets": []}
