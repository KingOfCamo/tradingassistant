"""AI analysis endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/analysis/{symbol}")
async def get_analysis(symbol: str, user: dict = Depends(get_current_user)):
    """Get or trigger AI analysis for a symbol."""
    return {"analysis": None}


@router.get("/analysis/brief/latest")
async def get_latest_brief(user: dict = Depends(get_current_user)):
    """Latest morning brief."""
    return {"brief": None}


@router.get("/analysis/briefs")
async def get_briefs(user: dict = Depends(get_current_user)):
    """All morning briefs."""
    return {"briefs": []}
