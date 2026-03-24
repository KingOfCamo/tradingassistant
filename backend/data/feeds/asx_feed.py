"""ASX-specific data feed for announcements and corporate actions."""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from backend.data.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

ASX_ANNOUNCEMENT_TTL = 7200  # 2 hours

# Sentiment keywords
POSITIVE_KEYWORDS = [
    "record", "beat", "upgrade", "above guidance", "strong", "exceed",
    "buyback", "dividend increase", "profit growth", "outperform",
]
NEGATIVE_KEYWORDS = [
    "shortfall", "downgrade", "below", "challenging", "impairment",
    "suspended dividend", "loss", "decline", "writedown", "recall",
]


def score_sentiment(text: str) -> float:
    """Score announcement sentiment from -1.0 to +1.0."""
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 2)


async def get_asx_announcements(symbol: str) -> list[dict]:
    """
    Fetch recent ASX announcements for a symbol.
    Note: In production, this would scrape asx.com.au or use an API.
    """
    cache_key = f"asx_announcements:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Placeholder — real implementation would scrape ASX
    logger.info("ASX announcement fetch for %s (placeholder)", symbol)
    return []


async def get_asx_dividend_calendar(symbol: str) -> Optional[dict]:
    """Get upcoming dividend information for an ASX stock."""
    cache_key = f"asx_dividend:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Would fetch from ASX or financial data provider
    return None


# GICS Sector to ASX Sector ETF mapping
SECTOR_ETF_MAP = {
    "Materials": "XMJ.AX",
    "Financials": "XFJ.AX",
    "Energy": "XEJ.AX",
    "Health Care": "XHJ.AX",
    "Industrials": "XIJ.AX",
    "Consumer Discretionary": "XDJ.AX",
    "Consumer Staples": "XSJ.AX",
    "Real Estate": "XPJ.AX",
    "Utilities": "XUJ.AX",
    "Information Technology": "XTJ.AX" if False else None,  # No dedicated IT ETF
    "Communication Services": None,
}


def get_sector_etf(sector: str) -> Optional[str]:
    """Get the ASX sector ETF for a given GICS sector."""
    return SECTOR_ETF_MAP.get(sector)
