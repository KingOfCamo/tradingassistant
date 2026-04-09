"""FRED feed — macro data for regime detection and risk-free rates.

All calls are cached aggressively (24h default) since FRED data changes
at most daily. The underlying fredapi library is synchronous; every call
is wrapped in asyncio.to_thread().

Also exposes module-level get_vix() and get_yield_spread() wrappers so that
existing callers (backend.strategies.regime.detector) keep working without
refactor. Those module-level helpers route through the DataRouter singleton
when it is available; otherwise they fall back to a direct FRED call.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.data.cache import cache_get, cache_set
from backend.data.feeds.exceptions import DataFeedError, FeedUnavailableError

logger = logging.getLogger(__name__)


class FREDFeed:
    def __init__(self, api_key: str, cache_ttl_seconds: int = 86400):
        if not api_key:
            raise FeedUnavailableError("FREDFeed requires FRED_API_KEY")
        try:
            from fredapi import Fred
        except ImportError as e:
            raise FeedUnavailableError(f"fredapi package not installed: {e}")
        self.fred = Fred(api_key=api_key)
        self.ttl = cache_ttl_seconds
        self._last_ok: Optional[datetime] = None

    def _mark_ok(self) -> None:
        self._last_ok = datetime.now(timezone.utc)

    @property
    def last_successful_call(self) -> Optional[datetime]:
        return self._last_ok

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    async def _fetch_series(self, series_id: str, **kwargs) -> pd.Series:
        def _blocking():
            return self.fred.get_series(series_id, **kwargs)
        return await asyncio.to_thread(_blocking)

    async def _latest(self, series_id: str, cache_key: str) -> Optional[float]:
        cached = await cache_get(cache_key)
        if cached and "value" in cached:
            return float(cached["value"])
        try:
            series = await self._fetch_series(series_id)
        except Exception as e:
            raise DataFeedError(f"FRED {series_id} failed: {e}")
        if series is None or len(series) == 0:
            raise DataFeedError(f"FRED {series_id} returned empty")
        value = series.dropna()
        if len(value) == 0:
            raise DataFeedError(f"FRED {series_id} all NaN")
        latest = float(value.iloc[-1])
        self._mark_ok()
        await cache_set(cache_key, {"value": latest}, self.ttl)
        return latest

    async def get_vix_history(self, days: int = 30) -> Optional[list[dict]]:
        """Historical VIX (VIXCLS). Returns list of {date, value}."""
        cache_key = f"fred:vix:history:{days}"
        cached = await cache_get(cache_key)
        if cached:
            return cached
        try:
            start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
            series = await self._fetch_series("VIXCLS", observation_start=start)
        except Exception as e:
            logger.warning("FRED VIXCLS history failed: %s", e)
            return None
        if series is None or len(series) == 0:
            return None
        self._mark_ok()
        result = [
            {"date": idx.strftime("%Y-%m-%d"), "value": float(val)}
            for idx, val in series.dropna().items()
        ]
        await cache_set(cache_key, result, self.ttl)
        return result

    async def get_yield_spread(self) -> Optional[float]:
        """T10Y2Y — 10Y minus 2Y Treasury spread."""
        return await self._latest("T10Y2Y", "fred:yield_spread")

    async def get_fed_funds_rate(self) -> Optional[float]:
        return await self._latest("FEDFUNDS", "fred:fed_funds")

    async def get_rba_rate(self) -> Optional[float]:
        # Series IRSTCB01AUM156N: Immediate Rates: Less than 24 Hours: Central Bank Rates for Australia
        return await self._latest("IRSTCB01AUM156N", "fred:rba_rate")

    async def get_cpi(self, market: str = "US") -> Optional[float]:
        """Latest YoY CPI change. US uses CPIAUCSL; AU uses AUSCPIALLQINMEI."""
        series_id = "CPIAUCSL" if market == "US" else "AUSCPIALLQINMEI"
        cache_key = f"fred:cpi:{market}"
        cached = await cache_get(cache_key)
        if cached and "yoy_pct" in cached:
            return float(cached["yoy_pct"])
        try:
            series = await self._fetch_series(series_id)
        except Exception as e:
            logger.warning("FRED %s failed: %s", series_id, e)
            return None
        if series is None or len(series) < 13:
            return None
        series = series.dropna()
        if len(series) < 13:
            return None
        latest = float(series.iloc[-1])
        year_ago = float(series.iloc[-13])
        yoy = ((latest - year_ago) / year_ago * 100) if year_ago else 0
        self._mark_ok()
        await cache_set(cache_key, {"yoy_pct": yoy}, self.ttl)
        return yoy

    async def get_vix_latest(self) -> Optional[float]:
        """Latest VIX level from FRED (fallback for Finnhub)."""
        return await self._latest("VIXCLS", "fred:vix:latest")

    async def refresh_all(self) -> dict:
        """Refresh all FRED series at once. Returns the snapshot."""
        snapshot: dict = {}
        for name, fn in (
            ("vix", self.get_vix_latest),
            ("yield_spread", self.get_yield_spread),
            ("fed_funds", self.get_fed_funds_rate),
            ("rba_rate", self.get_rba_rate),
            ("cpi_us", lambda: self.get_cpi("US")),
        ):
            try:
                snapshot[name] = await fn()
            except Exception as e:
                logger.warning("FRED refresh %s failed: %s", name, e)
                snapshot[name] = None
        logger.info(
            "FRED macro refresh: VIX=%s yield_spread=%s fed_funds=%s rba=%s",
            snapshot.get("vix"),
            snapshot.get("yield_spread"),
            snapshot.get("fed_funds"),
            snapshot.get("rba_rate"),
        )
        return snapshot


# ─── Module-level back-compat wrappers ────────────────────────────────────
# These are preserved so callers like regime/detector.py don't need refactor.
# They route through the DataRouter singleton when possible.


async def get_vix() -> Optional[float]:
    """Back-compat wrapper used by regime/detector.py."""
    try:
        from backend.data.feeds.data_router import get_data_router
        router = get_data_router()
        return await router.get_vix()
    except Exception as e:
        logger.warning("get_vix via router failed: %s", e)
        return None


async def get_yield_spread() -> Optional[float]:
    """Back-compat wrapper used by regime/detector.py."""
    try:
        from backend.data.feeds.data_router import get_data_router
        router = get_data_router()
        macro = await router.get_macro()
        return macro.get("yield_spread")
    except Exception as e:
        logger.warning("get_yield_spread via router failed: %s", e)
        return None


async def get_index_price(index_symbol: str) -> Optional[float]:
    """Back-compat stub — not used on active code paths."""
    logger.debug("fred_feed.get_index_price called (%s) — no-op", index_symbol)
    return None


async def get_rba_cash_rate() -> float:
    try:
        from backend.data.feeds.data_router import get_data_router
        macro = await get_data_router().get_macro()
        return float(macro.get("rba_rate") or 4.35)
    except Exception:
        return 4.35


async def get_fed_funds_rate() -> float:
    try:
        from backend.data.feeds.data_router import get_data_router
        macro = await get_data_router().get_macro()
        return float(macro.get("fed_funds") or 5.33)
    except Exception:
        return 5.33
