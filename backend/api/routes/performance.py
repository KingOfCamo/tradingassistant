"""Performance analytics endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/performance")
async def get_performance(user: dict = Depends(get_current_user)):
    """Overall performance metrics."""
    return {"performance": {}}


@router.get("/performance/by-strategy")
async def get_performance_by_strategy(user: dict = Depends(get_current_user)):
    return {"strategies": {}}


@router.get("/performance/by-sector")
async def get_performance_by_sector(user: dict = Depends(get_current_user)):
    return {"sectors": {}}
