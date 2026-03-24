"""Portfolio and positions endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/portfolio")
async def get_portfolio(user: dict = Depends(get_current_user)):
    """Positions + heat map summary."""
    return {"positions": [], "heatmap": {}}


@router.get("/portfolio/heatmap")
async def get_heatmap(user: dict = Depends(get_current_user)):
    """Full heat map: sectors, beta, correlations."""
    return {"heatmap": {}}


@router.post("/portfolio/positions")
async def create_position(user: dict = Depends(get_current_user)):
    """Log new position."""
    return {"status": "created"}


@router.put("/portfolio/positions/{position_id}")
async def update_position(position_id: str, user: dict = Depends(get_current_user)):
    return {"status": "updated"}


@router.post("/portfolio/positions/{position_id}/close")
async def close_position(position_id: str, user: dict = Depends(get_current_user)):
    return {"status": "closed"}
