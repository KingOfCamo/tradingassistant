"""Alert management endpoints."""

from fastapi import APIRouter, Depends
from backend.api.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/alerts")
async def get_alerts(user: dict = Depends(get_current_user)):
    return {"alerts": []}


@router.post("/alerts")
async def create_alert(user: dict = Depends(get_current_user)):
    return {"status": "created"}


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, user: dict = Depends(get_current_user)):
    return {"status": "deleted"}
