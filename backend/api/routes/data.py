"""Data layer health endpoint.

Shows feed status, credit usage, scheduler status. Protected by JWT.
First thing to check when debugging.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from backend.api.auth.dependencies import get_current_user
from backend.data.feeds.data_router import get_data_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])


def _iso(dt) -> str | None:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


@router.get("/health")
async def data_health(user=Depends(get_current_user)) -> dict[str, Any]:
    dr = get_data_router()

    # Twelve Data status
    td_block: dict[str, Any] = {"status": "disabled"}
    if dr.twelve is not None:
        try:
            credits = await dr.credit_tracker.get_status()
            td_block = {
                "status": "ok",
                "plan_tier": dr.twelve_plan_tier,
                "asx_enabled": dr.twelve_asx_enabled,
                "covers_markets": ["US"] + (["ASX"] if dr.twelve_asx_enabled else []),
                "credits_used_today": credits["used"],
                "credits_remaining": credits["remaining"],
                "credits_limit": credits["limit"],
                "pct_used": credits["pct_used"],
                "last_successful_call": _iso(dr.twelve.last_successful_call),
            }
            if not dr.twelve_asx_enabled:
                td_block["upgrade_hint"] = (
                    "ASX symbols require a paid Twelve Data plan. "
                    "Set TWELVE_DATA_PLAN_TIER=pro after upgrading."
                )
            if credits["pct_used"] >= 95:
                td_block["status"] = "degraded"
        except Exception as e:
            td_block = {"status": "error", "error": str(e)}

    # Finnhub status
    fh_block: dict[str, Any] = {"status": "disabled"}
    if dr.finnhub is not None and dr.finnhub.enabled:
        try:
            vix = None
            try:
                vix = await dr.finnhub.get_vix()
            except Exception:
                pass
            fh_block = {
                "status": "ok" if vix is not None else "degraded",
                "vix_current": vix,
                "last_successful_call": _iso(dr.finnhub.last_successful_call),
            }
        except Exception as e:
            fh_block = {"status": "error", "error": str(e)}

    # FRED status
    fred_block: dict[str, Any] = {"status": "disabled"}
    if dr.fred is not None:
        try:
            yield_spread = await dr.fred.get_yield_spread()
            fed_funds = await dr.fred.get_fed_funds_rate()
            fred_block = {
                "status": "ok",
                "last_successful_call": _iso(dr.fred.last_successful_call),
                "yield_spread": yield_spread,
                "fed_funds": fed_funds,
            }
        except Exception as e:
            fred_block = {"status": "error", "error": str(e)}

    # Scheduler status
    try:
        from backend.scheduler.jobs import get_scheduler_status
        sched = get_scheduler_status()
    except Exception as e:
        sched = {"running": False, "error": str(e)}

    yfinance_status = (
        {
            "status": "active_fallback",
            "role": "ASX primary (Twelve Data free tier excludes ASX)",
        }
        if not dr.twelve_asx_enabled
        else {"status": "standby", "role": "cold-start fallback only"}
    )

    return {
        "asx_primary_source": dr.asx_primary_source,
        "twelve_data": td_block,
        "finnhub": fh_block,
        "fred": fred_block,
        "yfinance": yfinance_status,
        "scheduler": sched,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
