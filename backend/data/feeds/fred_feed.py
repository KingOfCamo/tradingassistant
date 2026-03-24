"""Economic data feed from FRED via pandas-datareader / yfinance."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import yfinance as yf

from backend.data.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

# FRED series we track (fetched via yfinance proxies where possible)
SERIES = {
    "vix": "^VIX",
    "us_10y": "^TNX",        # 10-year treasury yield
    "us_2y": "^IRX",         # Proxy — 13-week T-bill
    "sp500": "^GSPC",
    "asx200": "^AXJO",
}

ECONOMIC_CACHE_TTL = 1800  # 30 minutes


async def get_vix() -> Optional[float]:
    """Get current VIX level."""
    cache_key = "fred:vix"
    cached = await cache_get(cache_key)
    if cached:
        return cached.get("value")

    try:
        ticker = yf.Ticker("^VIX")
        info = ticker.info
        value = float(info.get("regularMarketPrice", 0))
        await cache_set(cache_key, {"value": value}, ECONOMIC_CACHE_TTL)
        return value
    except Exception as e:
        logger.error("Failed to get VIX: %s", e)
        return None


async def get_yield_spread() -> Optional[float]:
    """Get 10Y-2Y yield spread (approximate via available yfinance data)."""
    cache_key = "fred:yield_spread"
    cached = await cache_get(cache_key)
    if cached:
        return cached.get("value")

    try:
        tnx = yf.Ticker("^TNX")
        ten_year = float(tnx.info.get("regularMarketPrice", 0))

        irx = yf.Ticker("^IRX")
        short_rate = float(irx.info.get("regularMarketPrice", 0))

        spread = ten_year - short_rate
        await cache_set(cache_key, {"value": spread}, ECONOMIC_CACHE_TTL)
        return spread
    except Exception as e:
        logger.error("Failed to get yield spread: %s", e)
        return None


async def get_index_price(index_symbol: str) -> Optional[float]:
    """Get current price for an index."""
    cache_key = f"fred:index:{index_symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached.get("value")

    try:
        ticker = yf.Ticker(index_symbol)
        info = ticker.info
        value = float(info.get("regularMarketPrice", 0))
        await cache_set(cache_key, {"value": value}, ECONOMIC_CACHE_TTL)
        return value
    except Exception as e:
        logger.error("Failed to get index %s: %s", index_symbol, e)
        return None


async def get_rba_cash_rate() -> float:
    """RBA cash rate — hardcoded fallback since yfinance doesn't have it directly."""
    # In production, scrape from RBA website or use a data service
    # For now, return a reasonable estimate
    cache_key = "fred:rba_cash_rate"
    cached = await cache_get(cache_key)
    if cached:
        return cached.get("value", 4.35)
    return 4.35  # Current as of 2024


async def get_fed_funds_rate() -> float:
    """Fed funds effective rate."""
    cache_key = "fred:fed_funds"
    cached = await cache_get(cache_key)
    if cached:
        return cached.get("value", 5.33)
    return 5.33  # Fallback
