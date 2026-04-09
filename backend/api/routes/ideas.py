"""Trade ideas endpoints."""

import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from backend.api.auth.dependencies import get_current_user
from backend.data.cache import cache_get, cache_set

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
    return d


async def _load_latest_scan(label: str) -> list[dict]:
    data = await cache_get(f"scan:latest:{label}")
    return data or []


@router.get("/ideas")
async def get_ideas(
    user: dict = Depends(get_current_user),
    market: str = Query(default="ALL"),
) -> dict:
    """Return active ideas from the latest scan snapshots."""
    ideas: list[dict] = []
    if market in ("ALL", "ASX"):
        ideas.extend(await _load_latest_scan("ASX"))
    if market in ("ALL", "NYSE", "US"):
        ideas.extend(await _load_latest_scan("NYSE"))
    return {"ideas": ideas, "total": len(ideas)}


@router.get("/ideas/history")
async def get_ideas_history(user: dict = Depends(get_current_user)) -> dict:
    return {"ideas": [], "total": 0}


@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: str, user: dict = Depends(get_current_user)) -> dict:
    return {"idea": None}


@router.post("/ideas/{idea_id}/action")
async def idea_action(idea_id: str, user: dict = Depends(get_current_user)) -> dict:
    return {"status": "ok"}


@router.post("/ideas/refresh")
async def refresh_ideas(
    user: dict = Depends(get_current_user),
    market: str = Query(default="ASX"),
) -> dict:
    """Trigger a fresh scan synchronously. For debugging and manual refresh."""
    # 1-per-hour throttle
    throttle_key = f"ideas:refresh:throttle:{market}"
    throttled = await cache_get(throttle_key)
    if throttled:
        return {"status": "throttled", "message": "Last refresh was less than 1 hour ago."}
    await cache_set(throttle_key, {"ts": datetime.utcnow().isoformat()}, 3600)

    logger.info("Manual /ideas/refresh triggered for %s by user %s", market, user.get("sub"))

    from backend.strategies.registry import StrategyRegistry

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

    # Persist snapshot to the same Redis key the scheduler uses
    payload = [_serialise(i) for i in ideas[:20]]
    await cache_set(f"scan:latest:{market}", payload, 43200)

    return {
        "status": "ok",
        "market": market,
        "ideas_generated": len(ideas),
        "preview": payload[:3],
    }
