"""Confluence alerts endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/confluence")
async def get_confluence_alerts(user: dict = Depends(get_current_user)):
    """Active confluence alerts ranked by score."""
    return {"alerts": [], "total": 0}


@router.get("/confluence/{alert_id}")
async def get_confluence_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """Full confluence alert with contributing ideas."""
    return {"alert": None}


@router.post("/confluence/{alert_id}/action")
async def confluence_action(alert_id: str, user: dict = Depends(get_current_user)):
    """Record user action on confluence alert."""
    return {"status": "ok"}
