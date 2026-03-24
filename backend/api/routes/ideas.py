"""Trade ideas endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/ideas")
async def get_ideas(user: dict = Depends(get_current_user)):
    """Paginated, filterable — only ACTIVE/WATCHING ideas."""
    return {"ideas": [], "total": 0}


@router.get("/ideas/history")
async def get_ideas_history(user: dict = Depends(get_current_user)):
    """Archived ideas with audit trail."""
    return {"ideas": [], "total": 0}


@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: str, user: dict = Depends(get_current_user)):
    """Full idea with portfolio impact preview."""
    return {"idea": None}


@router.post("/ideas/{idea_id}/action")
async def idea_action(idea_id: str, user: dict = Depends(get_current_user)):
    """Record user action on idea (act, pass, watch)."""
    return {"status": "ok"}


@router.post("/ideas/refresh")
async def refresh_ideas(user: dict = Depends(get_current_user)):
    """Trigger fresh scan (1/hour throttle)."""
    return {"status": "scanning"}
