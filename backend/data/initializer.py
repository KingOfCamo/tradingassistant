"""Startup data initialiser — warms the Redis cache on app boot.

Called once from the FastAPI lifespan. Skips anything already cached. Backs
off immediately if Twelve Data credits are scarce.
"""

from __future__ import annotations

import asyncio
import logging

from backend.data.feeds.data_router import DataRouter

logger = logging.getLogger(__name__)


async def initialise_data(router: DataRouter) -> None:
    logger.info("=== DATA INITIALISATION START ===")

    # 1. FRED macro data (fast — ~5 series)
    if router.fred:
        try:
            await router.fred.refresh_all()
        except Exception as e:
            logger.warning("FRED refresh failed during init: %s", e)

    # 2. ASX 200 universe symbols
    try:
        from backend.data.universe.asx200 import get_asx200
        asx_universe = await get_asx200()
        asx_symbols = [s.symbol for s in asx_universe]
        logger.info("ASX universe loaded: %d symbols", len(asx_symbols))
    except Exception as e:
        logger.error("Failed to load ASX universe: %s", e)
        asx_symbols = []

    # 3. Warm ASX quote cache in batches of 50 — check quota before each
    if asx_symbols and router.twelve:
        for i in range(0, len(asx_symbols), 50):
            batch = asx_symbols[i:i + 50]
            remaining = await router.credit_tracker.get_remaining()
            if remaining < 60:
                logger.warning(
                    "Credit limit approaching (%d remaining) — deferring warm-up",
                    remaining,
                )
                break
            try:
                await router.twelve.get_quotes_batch(batch, "ASX")
                await asyncio.sleep(1)  # 1s pause between batches
            except Exception as e:
                logger.warning("ASX warm-up batch failed: %s", e)

    # 4. US universe — quotes only for top 25 most liquid
    try:
        from backend.data.universe.sp500 import get_sp500
        sp500_symbols = [s.symbol for s in (await get_sp500())][:25]
    except Exception as e:
        logger.error("Failed to load S&P 500 universe: %s", e)
        sp500_symbols = []

    if sp500_symbols and router.finnhub and router.finnhub.enabled:
        try:
            await asyncio.gather(
                *[router.finnhub.get_quote_us(s) for s in sp500_symbols],
                return_exceptions=True,
            )
        except Exception as e:
            logger.warning("US warm-up failed: %s", e)

    credit_status = await router.credit_tracker.get_status()
    logger.info("=== DATA INITIALISATION COMPLETE === credits: %s", credit_status)
