"""Trade ideas endpoints — backed by the trade_ideas_repo (Postgres)."""

import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from backend.api.auth.dependencies import get_current_user
from backend.data.cache import cache_get, cache_set
from backend.db.repositories import trade_ideas_repo as repo

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialise(idea) -> dict:
    if is_dataclass(idea):
        d = asdict(idea)
    elif isinstance(idea, dict):
        d = dict(idea)
    else:
        return {}
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif hasattr(v, "value"):  # Enum
            d[k] = v.value
    return d


@router.get("/ideas")
async def get_ideas(
    user: dict = Depends(get_current_user),
    market: str = Query(default="ALL"),
    limit: int = Query(default=50, le=200),
) -> dict:
    """Return active trade ideas from Postgres."""
    try:
        ideas = await repo.list_active_ideas(market=market, limit=limit)
        return {"ideas": ideas, "total": len(ideas), "source": "postgres"}
    except Exception as e:
        logger.warning("Postgres read failed, falling back to Redis: %s", e)
        # Redis fallback (should be rare)
        ideas = []
        if market in ("ALL", "ASX"):
            ideas.extend(await cache_get("scan:latest:ASX") or [])
        if market in ("ALL", "NYSE", "US"):
            ideas.extend(await cache_get("scan:latest:NYSE") or [])
        return {"ideas": ideas, "total": len(ideas), "source": "redis_fallback"}


@router.get("/ideas/history")
async def get_ideas_history(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=100, le=500),
) -> dict:
    ideas = await repo.list_history(limit=limit)
    return {"ideas": ideas, "total": len(ideas)}


@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: str, user: dict = Depends(get_current_user)) -> dict:
    idea = await repo.get_idea(idea_id)
    return {"idea": idea}


@router.post("/ideas/{idea_id}/action")
async def idea_action(
    idea_id: str,
    user: dict = Depends(get_current_user),
    body: dict = Body(default={}),
) -> dict:
    action = body.get("action", "watching")
    pass_reason = body.get("pass_reason")
    notes = body.get("notes")
    ok = await repo.record_user_action(idea_id, action, pass_reason, notes)
    return {"status": "ok" if ok else "not_found"}


@router.post("/ideas/refresh")
async def refresh_ideas(
    user: dict = Depends(get_current_user),
    market: str = Query(default="ASX"),
    force: bool = Query(default=False),
) -> dict:
    """Trigger a fresh scan synchronously. For debugging and manual refresh."""
    throttle_key = f"ideas:refresh:throttle:{market}"
    if not force:
        throttled = await cache_get(throttle_key)
        if throttled:
            return {"status": "throttled", "message": "Last refresh was less than 1 hour ago."}
    await cache_set(throttle_key, {"ts": datetime.utcnow().isoformat()}, 3600)

    logger.info("Manual /ideas/refresh triggered for %s by user %s", market, user.get("sub"))

    from backend.strategies.registry import StrategyRegistry
    from backend.scheduler.jobs import _persist_scan_snapshot

    if market == "ASX":
        from backend.data.universe.asx200 import get_asx200
        universe = await get_asx200()
    else:
        from backend.data.universe.sp500 import get_sp500
        universe = await get_sp500()

    try:
        ideas = await StrategyRegistry().run_all(universe, market)
    except Exception as e:
        logger.exception("Manual scan failed")
        return {"status": "error", "message": str(e)}

    # Persist to DB + Redis via the same path scheduler uses
    await _persist_scan_snapshot(market, ideas)

    preview = [_serialise(i) for i in ideas[:3]]
    return {
        "status": "ok",
        "market": market,
        "ideas_generated": len(ideas),
        "preview": preview,
    }
