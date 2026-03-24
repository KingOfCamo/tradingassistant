"""Trade journal endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/journal")
async def get_journal(user: dict = Depends(get_current_user)):
    return {"trades": [], "total": 0}


@router.get("/journal/stats")
async def get_journal_stats(user: dict = Depends(get_current_user)):
    return {"stats": {}}


@router.get("/journal/tax")
async def get_tax_report(user: dict = Depends(get_current_user)):
    """CGT tax report for AU financial year."""
    return {"report": {}}
