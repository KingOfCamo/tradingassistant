"""Risk management endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/risk/regime")
async def get_regime(user: dict = Depends(get_current_user)):
    """Current market regime for AU and US."""
    return {"au": None, "us": None}


@router.get("/risk/regime/history")
async def get_regime_history(user: dict = Depends(get_current_user)):
    """Regime change log."""
    return {"history": []}


@router.get("/risk/heatmap")
async def get_risk_heatmap(user: dict = Depends(get_current_user)):
    """Portfolio heat map data."""
    return {"heatmap": {}}


@router.get("/risk/impact/{symbol}")
async def get_impact(symbol: str, user: dict = Depends(get_current_user)):
    """Simulate adding a symbol — portfolio impact."""
    return {"impact": {}}
