"""User style profile endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/style/profile")
async def get_style_profile(user: dict = Depends(get_current_user)):
    """Current user style profile."""
    return {"profile": {}}


@router.get("/style/reports")
async def get_style_reports(user: dict = Depends(get_current_user)):
    """All weekly style reports."""
    return {"reports": []}


@router.get("/style/prompt")
async def get_current_prompt(user: dict = Depends(get_current_user)):
    """Current personalised AI prompt (transparency)."""
    return {"prompt": ""}
