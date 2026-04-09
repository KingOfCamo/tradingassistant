"""Job scheduler: all scan and monitoring jobs.

Uses APScheduler AsyncIOScheduler driven by the FastAPI lifespan in app.py.
Every job function is wrapped in try/except so a single failure never
crashes the scheduler. Every scan starts with a market_hours guard so we
don't waste API credits on weekends or holidays.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from functools import wraps

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.scheduler import market_hours

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def _safe_job(fn):
    """Decorator — never let a job crash the scheduler."""
    @wraps(fn)
    async def wrapped(*args, **kwargs):
        name = fn.__name__
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            logger.error(
                "Scheduler job %s failed: %s\n%s",
                name, e, traceback.format_exc(),
            )
    return wrapped


def _market_gate(market: str):
    """Decorator — skip execution if the market is closed."""
    def deco(fn):
        @wraps(fn)
        async def wrapped(*args, **kwargs):
            if not market_hours.should_scan_now(market):
                logger.debug("%s skipped — %s closed", fn.__name__, market)
                return
            return await fn(*args, **kwargs)
        return wrapped
    return deco


# ─── Job implementations ──────────────────────────────────────────────────


@_safe_job
async def fred_refresh_job():
    """Daily FRED macro refresh. Runs regardless of market status."""
    logger.info("[job] FRED macro refresh starting")
    from backend.data.feeds.data_router import get_data_router
    router = get_data_router()
    if router.fred:
        snapshot = await router.fred.refresh_all()
        logger.info("[job] FRED macro refresh complete: %s", snapshot)
    else:
        logger.warning("[job] FRED feed unavailable")


@_safe_job
async def regime_update_job():
    """Re-evaluate regime for both markets. Runs every 30 min."""
    logger.info("[job] Regime update (ASX + US)")
    from backend.strategies.regime.detector import detect_regime
    try:
        asx_regime = await detect_regime("ASX")
        logger.info("[job] ASX regime: %s", asx_regime.regime.value)
    except Exception as e:
        logger.warning("[job] ASX regime update failed: %s", e)
    try:
        us_regime = await detect_regime("NYSE")
        logger.info("[job] US regime: %s", us_regime.regime.value)
    except Exception as e:
        logger.warning("[job] US regime update failed: %s", e)


@_safe_job
@_market_gate("ASX")
async def asx_morning_brief_job():
    logger.info("[job] ASX morning brief")
    # Minimal version — full brief requires DB position query.
    # Placeholder logs so we know the job fired.


@_safe_job
@_market_gate("ASX")
async def asx_idea_lifecycle_job():
    logger.info("[job] ASX idea lifecycle evaluation")
    from backend.risk.idea_lifecycle import reevaluate_active_ideas
    try:
        count = await reevaluate_active_ideas("ASX")
        logger.info("[job] ASX re-evaluated %s ideas", count)
    except Exception as e:
        logger.debug("[job] idea lifecycle not yet wired: %s", e)


@_safe_job
@_market_gate("ASX")
async def asx_momentum_scan_job():
    logger.info("[job] ASX momentum scan starting")
    from backend.strategies.registry import StrategyRegistry
    from backend.data.universe.asx200 import get_asx200
    universe = await get_asx200()
    registry = StrategyRegistry()
    ideas = await registry.run_all(universe, "ASX")
    logger.info("[job] ASX momentum scan produced %d ideas", len(ideas))
    await _persist_scan_snapshot("ASX", ideas)


@_safe_job
@_market_gate("ASX")
async def asx_breakout_scan_job():
    logger.info("[job] ASX breakout scan (15-min interval)")
    from backend.strategies.momentum.breakout import Breakout
    from backend.data.universe.asx200 import get_asx200
    universe = await get_asx200()
    try:
        strategy = Breakout()
        ideas = await strategy.generate_signals(universe, "ASX")
        logger.info("[job] ASX breakout scan produced %d ideas", len(ideas))
    except Exception as e:
        logger.error("[job] ASX breakout scan failed: %s", e)


@_safe_job
async def asx_eod_scan_job():
    """End-of-day scan — runs regardless of "should_scan_now" because it's at close."""
    logger.info("[job] ASX EOD scan")
    from backend.strategies.registry import StrategyRegistry
    from backend.data.universe.asx200 import get_asx200
    universe = await get_asx200()
    ideas = await StrategyRegistry().run_all(universe, "ASX")
    logger.info("[job] ASX EOD scan produced %d ideas", len(ideas))
    await _persist_scan_snapshot("ASX_EOD", ideas)


@_safe_job
@_market_gate("NYSE")
async def us_morning_brief_job():
    logger.info("[job] US morning brief")


@_safe_job
@_market_gate("NYSE")
async def us_momentum_scan_job():
    logger.info("[job] US momentum scan starting")
    from backend.strategies.registry import StrategyRegistry
    from backend.data.universe.sp500 import get_sp500
    universe = await get_sp500()
    ideas = await StrategyRegistry().run_all(universe, "NYSE")
    logger.info("[job] US momentum scan produced %d ideas", len(ideas))
    await _persist_scan_snapshot("NYSE", ideas)


@_safe_job
async def us_eod_scan_job():
    logger.info("[job] US EOD scan")
    from backend.strategies.registry import StrategyRegistry
    from backend.data.universe.sp500 import get_sp500
    universe = await get_sp500()
    ideas = await StrategyRegistry().run_all(universe, "NYSE")
    logger.info("[job] US EOD scan produced %d ideas", len(ideas))
    await _persist_scan_snapshot("NYSE_EOD", ideas)


@_safe_job
async def weekly_fundamental_scan_job():
    logger.info("[job] Weekly fundamental scan (Sun)")
    from backend.strategies.value.fundamental_screen import FundamentalScreen
    from backend.data.universe.asx200 import get_asx200
    try:
        universe = await get_asx200()
        strategy = FundamentalScreen()
        ideas = await strategy.generate_signals(universe, "ASX")
        logger.info("[job] Fundamental scan: %d ideas", len(ideas))
    except Exception as e:
        logger.error("[job] Fundamental scan failed: %s", e)


@_safe_job
async def weekly_sector_rotation_job():
    logger.info("[job] Weekly sector rotation (Sun)")
    from backend.strategies.macro.sector_rotation import SectorRotation
    from backend.data.universe.asx200 import get_asx200
    try:
        universe = await get_asx200()
        strategy = SectorRotation()
        ideas = await strategy.generate_signals(universe, "ASX")
        logger.info("[job] Sector rotation: %d ideas", len(ideas))
    except Exception as e:
        logger.error("[job] Sector rotation failed: %s", e)


@_safe_job
async def weekly_style_report_job():
    logger.info("[job] Weekly style report (Sun)")


# ─── Snapshot persistence ─────────────────────────────────────────────────


async def _persist_scan_snapshot(label: str, ideas: list) -> None:
    """Persist the latest scan result.

    Primary: Postgres trade_ideas table (via trade_ideas_repo). The repo
    archives prior active rows for this market then inserts the fresh batch.

    Secondary: Redis snapshot under scan:latest:{label} for fast reads
    and for backfill if the DB write fails.

    `label` may be a raw market name (e.g. "ASX") or include a suffix
    (e.g. "ASX_EOD"). The market portion is parsed out for the DB write.
    """
    try:
        # Always write the Redis snapshot (cheap, tolerant)
        from backend.data.cache import cache_set
        from dataclasses import asdict, is_dataclass

        payload = []
        for idea in ideas[:20]:
            if is_dataclass(idea):
                d = asdict(idea)
                for k, v in list(d.items()):
                    if isinstance(v, datetime):
                        d[k] = v.isoformat()
                    elif hasattr(v, "value"):  # Enum
                        d[k] = v.value
                payload.append(d)
        await cache_set(f"scan:latest:{label}", payload, 43200)  # 12h
    except Exception as e:
        logger.warning("Failed to write Redis snapshot for %s: %s", label, e)

    # DB write
    try:
        from backend.db.repositories.trade_ideas_repo import save_scan_ideas
        market = label.split("_")[0]  # "ASX_EOD" → "ASX"
        count = await save_scan_ideas(ideas, market)
        logger.info("DB persist %s: %d ideas written", market, count)
    except Exception as e:
        logger.warning("Failed to persist scan to DB for %s: %s", label, e)


# ─── Registration ─────────────────────────────────────────────────────────


def register_all_jobs() -> int:
    """Attach every job to the scheduler. Times are UTC."""
    # Clear any prior registrations (matters on app reload)
    scheduler.remove_all_jobs()

    # FRED daily refresh — 20:00 UTC daily (before ASX open)
    scheduler.add_job(
        fred_refresh_job,
        CronTrigger(hour=20, minute=0),
        id="fred_daily_refresh",
        name="FRED Daily Refresh",
        replace_existing=True,
    )

    # Regime — every 30 minutes
    scheduler.add_job(
        regime_update_job,
        IntervalTrigger(minutes=30),
        id="regime_update",
        name="Regime Update (ASX+US)",
        replace_existing=True,
    )

    # ASX — times are in Australia/Sydney
    scheduler.add_job(
        asx_morning_brief_job,
        CronTrigger(hour=9, minute=30, day_of_week="mon-fri", timezone="Australia/Sydney"),
        id="asx_morning_brief",
        name="ASX Morning Brief",
        replace_existing=True,
    )
    scheduler.add_job(
        asx_idea_lifecycle_job,
        CronTrigger(hour=9, minute=25, day_of_week="mon-fri", timezone="Australia/Sydney"),
        id="asx_idea_lifecycle",
        name="ASX Idea Lifecycle",
        replace_existing=True,
    )
    scheduler.add_job(
        asx_momentum_scan_job,
        CronTrigger(hour=10, minute=30, day_of_week="mon-fri", timezone="Australia/Sydney"),
        id="asx_momentum_scan",
        name="ASX Momentum Scan",
        replace_existing=True,
    )
    scheduler.add_job(
        asx_breakout_scan_job,
        IntervalTrigger(minutes=15),
        id="asx_breakout_scan",
        name="ASX Breakout Scan (15m)",
        replace_existing=True,
    )
    scheduler.add_job(
        asx_eod_scan_job,
        CronTrigger(hour=16, minute=15, day_of_week="mon-fri", timezone="Australia/Sydney"),
        id="asx_eod_scan",
        name="ASX End-of-Day Scan",
        replace_existing=True,
    )

    # US — times are in America/New_York
    scheduler.add_job(
        us_morning_brief_job,
        CronTrigger(hour=9, minute=0, day_of_week="mon-fri", timezone="America/New_York"),
        id="us_morning_brief",
        name="US Morning Brief",
        replace_existing=True,
    )
    scheduler.add_job(
        us_momentum_scan_job,
        CronTrigger(hour=10, minute=0, day_of_week="mon-fri", timezone="America/New_York"),
        id="us_momentum_scan",
        name="US Momentum Scan",
        replace_existing=True,
    )
    scheduler.add_job(
        us_eod_scan_job,
        CronTrigger(hour=16, minute=5, day_of_week="mon-fri", timezone="America/New_York"),
        id="us_eod_scan",
        name="US End-of-Day Scan",
        replace_existing=True,
    )

    # Weekly — Sunday 18:00 Australia/Sydney
    scheduler.add_job(
        weekly_fundamental_scan_job,
        CronTrigger(day_of_week="sun", hour=18, minute=0, timezone="Australia/Sydney"),
        id="weekly_fundamental",
        name="Weekly Fundamental Screen",
        replace_existing=True,
    )
    scheduler.add_job(
        weekly_sector_rotation_job,
        CronTrigger(day_of_week="sun", hour=18, minute=15, timezone="Australia/Sydney"),
        id="weekly_sector_rotation",
        name="Weekly Sector Rotation",
        replace_existing=True,
    )
    scheduler.add_job(
        weekly_style_report_job,
        CronTrigger(day_of_week="sun", hour=17, minute=0, timezone="Australia/Sydney"),
        id="weekly_style_report",
        name="Weekly Style Report",
        replace_existing=True,
    )

    count = len(scheduler.get_jobs())
    logger.info("Scheduler registered %d jobs", count)
    return count


def start_scheduler() -> int:
    """Start the scheduler. Call from app lifespan after the event loop is running."""
    n = register_all_jobs()
    if not scheduler.running:
        scheduler.start()
    logger.info("Scheduler started — %d jobs active", n)
    return n


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """For the /api/data/health endpoint."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": jobs,
    }
