"""Watchlist endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/watchlist")
async def get_watchlist(user: dict = Depends(get_current_user)):
    return {"symbols": []}


@router.post("/watchlist")
async def add_to_watchlist(user: dict = Depends(get_current_user)):
    return {"status": "added"}


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str, user: dict = Depends(get_current_user)):
    return {"status": "removed"}
