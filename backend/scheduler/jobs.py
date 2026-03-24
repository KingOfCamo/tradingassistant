"""Job scheduler: all scan and monitoring jobs from Phase 14."""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ─── Job Functions ───────────────────────────────────────────────────────────

async def asx_morning_brief():
    """Daily 9:30 AM AEDT."""
    logger.info("Running ASX morning brief...")
    from backend.ai.market_brief import generate_morning_brief
    # Would fetch positions, market data, ideas, regime and generate brief
    # Placeholder — full implementation requires DB queries


async def asx_regime_update():
    """Every 30 min."""
    logger.info("Running ASX regime update...")
    from backend.strategies.regime.detector import detect_regime
    await detect_regime("ASX")


async def asx_momentum_scan():
    """Daily 10:30 AM AEDT."""
    logger.info("Running ASX momentum scan...")
    from backend.strategies.registry import StrategyRegistry
    from backend.data.universe.asx200 import get_asx200
    universe = await get_asx200()
    registry = StrategyRegistry()
    ideas = await registry.run_all(universe, "ASX")
    logger.info("ASX scan produced %d ideas", len(ideas))


async def asx_idea_lifecycle():
    """Daily 9:30 AM AEDT."""
    logger.info("Running ASX idea lifecycle evaluation...")
    # Would query all active ideas from DB and re-evaluate


async def us_regime_update():
    """Every 30 min."""
    logger.info("Running US regime update...")
    from backend.strategies.regime.detector import detect_regime
    await detect_regime("US")


async def us_momentum_scan():
    """Daily 10:00 AM ET."""
    logger.info("Running US momentum scan...")
    from backend.strategies.registry import StrategyRegistry
    from backend.data.universe.sp500 import get_sp500
    universe = await get_sp500()
    registry = StrategyRegistry()
    ideas = await registry.run_all(universe, "NYSE")
    logger.info("US scan produced %d ideas", len(ideas))


async def weekly_fundamental_scan():
    """Sunday 6:00 PM AEDT."""
    logger.info("Running weekly fundamental + sector rotation scan...")


async def weekly_style_report():
    """Sunday 5:00 PM AEDT."""
    logger.info("Running weekly style report...")


# ─── Schedule Setup ──────────────────────────────────────────────────────────

def setup_scheduler():
    """Configure all scheduled jobs."""

    # ASX Jobs (times in Australia/Sydney)
    scheduler.add_job(
        asx_morning_brief, CronTrigger(hour=9, minute=30, timezone="Australia/Sydney"),
        id="asx_morning_brief", name="ASX Morning Brief",
    )
    scheduler.add_job(
        asx_regime_update, CronTrigger(minute="*/30", timezone="Australia/Sydney"),
        id="asx_regime_update", name="ASX Regime Update",
    )
    scheduler.add_job(
        asx_momentum_scan, CronTrigger(hour=10, minute=30, timezone="Australia/Sydney"),
        id="asx_momentum_scan", name="ASX Momentum Scan",
    )
    scheduler.add_job(
        asx_idea_lifecycle, CronTrigger(hour=9, minute=30, timezone="Australia/Sydney"),
        id="asx_idea_lifecycle", name="ASX Idea Lifecycle",
    )

    # US Jobs (times in America/New_York)
    scheduler.add_job(
        us_regime_update, CronTrigger(minute="*/30", timezone="America/New_York"),
        id="us_regime_update", name="US Regime Update",
    )
    scheduler.add_job(
        us_momentum_scan, CronTrigger(hour=10, minute=0, timezone="America/New_York"),
        id="us_momentum_scan", name="US Momentum Scan",
    )

    # Weekly Jobs
    scheduler.add_job(
        weekly_fundamental_scan,
        CronTrigger(day_of_week="sun", hour=18, minute=0, timezone="Australia/Sydney"),
        id="weekly_fundamental", name="Weekly Fundamental Scan",
    )
    scheduler.add_job(
        weekly_style_report,
        CronTrigger(day_of_week="sun", hour=17, minute=0, timezone="Australia/Sydney"),
        id="weekly_style_report", name="Weekly Style Report",
    )

    logger.info("Scheduler configured with %d jobs", len(scheduler.get_jobs()))


def start_scheduler():
    """Start the scheduler."""
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    scheduler.shutdown()
    logger.info("Scheduler stopped")
