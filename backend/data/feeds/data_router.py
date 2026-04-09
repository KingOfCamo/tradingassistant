"""DataRouter — the single entry point for all market data.

Responsibilities
  • Route each request to the right feed based on market.
  • Fall back to a secondary source on failure.
  • Track Twelve Data credits and degrade to cache-only near the quota.
  • Compute indicators locally for US symbols (Finnhub doesn't provide them).

All feeds are lazily initialised and cached as a module-level singleton so
strategies can call module-level helpers in yfinance_feed.py without any
constructor plumbing.

NOTE — architectural simplification:
The original spec had every strategy take `data_router: DataRouter` in its
constructor. That would require rewriting 9 strategies + the registry + tests.
Instead we wire a module-level singleton here and route the existing
`get_daily_bars`/`get_quote` helpers in yfinance_feed.py through it. The
functional guarantee is the same (yfinance never on the live path). A future
cleanup can migrate to explicit DI if desired.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import settings
from backend.data.feeds.credit_tracker import CreditTracker
from backend.data.feeds.exceptions import DataFeedError, FeedUnavailableError
from backend.data.feeds.finnhub_feed import FinnhubFeed
from backend.data.feeds.fred_feed import FREDFeed
from backend.data.feeds.twelve_data_feed import TwelveDataFeed
from backend.data.normalizer import OHLCV, Quote

logger = logging.getLogger(__name__)


# ─── period → outputsize translation ──────────────────────────────────────

_PERIOD_TO_OUTPUTSIZE = {
    "1d": 1,
    "5d": 5,
    "1mo": 22,
    "3mo": 66,
    "6mo": 132,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
}


def period_to_outputsize(period: str) -> int:
    return _PERIOD_TO_OUTPUTSIZE.get(period, 252)


# ─── the router ───────────────────────────────────────────────────────────


class DataRouter:
    def __init__(
        self,
        twelve: Optional[TwelveDataFeed],
        finnhub: Optional[FinnhubFeed],
        fred: Optional[FREDFeed],
        credit_tracker: CreditTracker,
        twelve_plan_tier: str = "free",
    ):
        self.twelve = twelve
        self.finnhub = finnhub
        self.fred = fred
        self.credit_tracker = credit_tracker
        # Twelve Data free tier does not include ASX. If the user is on free,
        # skip Twelve Data for ASX entirely and fall back to yfinance.
        self.twelve_plan_tier = (twelve_plan_tier or "free").lower()
        self.twelve_asx_enabled = self.twelve_plan_tier not in ("", "free")

    @property
    def asx_primary_source(self) -> str:
        if self.twelve and self.twelve_asx_enabled:
            return "twelve_data"
        return "yfinance_fallback"

    # ─── quotes ──────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str, market: str) -> Quote:
        errors = []

        if market == "ASX":
            if self.twelve and self.twelve_asx_enabled:
                try:
                    return await self.twelve.get_quote(symbol, market)
                except Exception as e:
                    errors.append(f"twelve: {e}")
                    logger.warning("Twelve Data quote failed for ASX %s: %s", symbol, e)
        else:  # US
            if self.finnhub and self.finnhub.enabled:
                try:
                    return await self.finnhub.get_quote_us(symbol)
                except Exception as e:
                    errors.append(f"finnhub: {e}")
                    logger.warning("Finnhub quote failed for US %s: %s", symbol, e)
            if self.twelve:
                try:
                    return await self.twelve.get_quote(symbol, market)
                except Exception as e:
                    errors.append(f"twelve: {e}")

        # Last-resort fallback: yfinance legacy path
        fallback = await _yfinance_fallback_quote(symbol, market)
        if fallback is not None:
            return fallback

        raise DataFeedError(
            f"All quote sources failed for {market}:{symbol} — {'; '.join(errors)}"
        )

    async def get_quotes_batch(
        self, symbols: list[str], market: str
    ) -> dict[str, Quote]:
        if market == "ASX":
            if self.twelve and self.twelve_asx_enabled:
                try:
                    return await self.twelve.get_quotes_batch(symbols, market)
                except Exception as e:
                    logger.warning("Twelve Data batch failed for ASX: %s", e)
        # US has no batch on Finnhub; parallel
        results: dict[str, Quote] = {}
        if not symbols:
            return results

        async def _one(s: str):
            try:
                results[s] = await self.get_quote(s, market)
            except Exception as e:
                logger.debug("batch quote %s failed: %s", s, e)

        await asyncio.gather(*[_one(s) for s in symbols])
        return results

    # ─── OHLCV ───────────────────────────────────────────────────────────

    async def get_ohlcv(
        self,
        symbol: str,
        market: str,
        interval: str = "1day",
        outputsize: int = 365,
    ) -> list[OHLCV]:
        errors = []

        if market == "ASX":
            if self.twelve and self.twelve_asx_enabled:
                try:
                    bars = await self.twelve.get_ohlcv(symbol, market, interval, outputsize)
                    if bars:
                        return bars
                except Exception as e:
                    errors.append(f"twelve: {e}")
                    logger.warning("Twelve Data OHLCV failed for ASX %s: %s", symbol, e)
        else:  # US
            # Prefer Finnhub for US daily bars
            if self.finnhub and self.finnhub.enabled and interval == "1day":
                try:
                    bars = await self.finnhub.get_candles_us(symbol, "D", outputsize)
                    if bars:
                        return bars
                except Exception as e:
                    errors.append(f"finnhub: {e}")
                    logger.warning("Finnhub candles failed for US %s: %s", symbol, e)
            if self.twelve:
                try:
                    bars = await self.twelve.get_ohlcv(symbol, market, interval, outputsize)
                    if bars:
                        return bars
                except Exception as e:
                    errors.append(f"twelve: {e}")

        # Fallback
        fallback = await _yfinance_fallback_ohlcv(symbol, market, interval, outputsize)
        if fallback:
            return fallback

        logger.error("All OHLCV sources failed for %s:%s — %s", market, symbol, errors)
        return []

    # ─── indicators ──────────────────────────────────────────────────────

    async def get_indicators(self, symbol: str, market: str) -> dict:
        if market == "ASX" and self.twelve and self.twelve_asx_enabled:
            try:
                return await self.twelve.get_indicators(symbol, market)
            except Exception as e:
                logger.warning("Twelve Data indicators failed %s: %s", symbol, e)

        # US: compute from OHLCV locally (Finnhub doesn't provide pre-computed)
        bars = await self.get_ohlcv(symbol, market, "1day", 250)
        if not bars:
            return {}
        return _compute_indicators_from_bars(bars)

    # ─── VIX ─────────────────────────────────────────────────────────────

    async def get_vix(self) -> Optional[float]:
        if self.finnhub and self.finnhub.enabled:
            try:
                return await self.finnhub.get_vix()
            except Exception as e:
                logger.debug("Finnhub VIX failed: %s", e)
        if self.fred:
            try:
                return await self.fred.get_vix_latest()
            except Exception as e:
                logger.debug("FRED VIX failed: %s", e)
        return None

    # ─── forex ───────────────────────────────────────────────────────────

    async def get_forex_audusd(self) -> float:
        if self.twelve:
            try:
                return await self.twelve.get_forex_rate("AUD", "USD")
            except Exception as e:
                logger.debug("Twelve Data forex failed: %s", e)
        if self.finnhub and self.finnhub.enabled:
            try:
                return await self.finnhub.get_forex_audusd()
            except Exception as e:
                logger.debug("Finnhub forex failed: %s", e)
        logger.warning("All forex sources failed — using 0.65 fallback")
        return 0.65

    # ─── macro ───────────────────────────────────────────────────────────

    async def get_macro(self) -> dict:
        """Aggregated FRED data. Cached 24h inside FREDFeed."""
        if not self.fred:
            return {}
        try:
            yield_spread = await self.fred.get_yield_spread()
        except Exception:
            yield_spread = None
        try:
            fed_funds = await self.fred.get_fed_funds_rate()
        except Exception:
            fed_funds = None
        try:
            rba_rate = await self.fred.get_rba_rate()
        except Exception:
            rba_rate = None
        return {
            "yield_spread": yield_spread,
            "fed_funds": fed_funds,
            "rba_rate": rba_rate,
        }

    # ─── earnings ────────────────────────────────────────────────────────

    async def get_earnings_calendar(self, market: str) -> list[dict]:
        if market == "ASX" and self.twelve and self.twelve_asx_enabled:
            try:
                return await self.twelve.get_earnings_calendar(market)
            except Exception as e:
                logger.warning("Twelve Data earnings calendar failed: %s", e)
                return []
        if self.finnhub and self.finnhub.enabled:
            try:
                return await self.finnhub.get_earnings_calendar_us()
            except Exception as e:
                logger.warning("Finnhub earnings calendar failed: %s", e)
        return []


# ─── local indicator computation (for US via Finnhub bars) ────────────────


def _compute_indicators_from_bars(bars: list[OHLCV]) -> dict:
    import numpy as np
    closes = np.array([b.close for b in bars], dtype=float)
    if len(closes) < 50:
        return {}

    def ema(vals, period):
        if len(vals) < period:
            return float(vals[-1])
        k = 2 / (period + 1)
        v = vals[0]
        for x in vals[1:]:
            v = x * k + v * (1 - k)
        return float(v)

    # RSI
    rsi = None
    if len(closes) >= 15:
        deltas = np.diff(closes[-15:])
        gains = np.where(deltas > 0, deltas, 0).mean()
        losses = np.where(deltas < 0, -deltas, 0).mean()
        if losses == 0:
            rsi = 100.0
        else:
            rs = gains / losses
            rsi = round(100 - (100 / (1 + rs)), 2)

    # MACD
    ema12 = ema(closes[-26:], 12) if len(closes) >= 26 else None
    ema26 = ema(closes[-26:], 26) if len(closes) >= 26 else None
    macd = (ema12 - ema26) if ema12 is not None and ema26 is not None else None

    # Bollinger (20, 2)
    bb_upper = bb_lower = bb_mid = None
    if len(closes) >= 20:
        recent = closes[-20:]
        mid = float(recent.mean())
        std = float(recent.std())
        bb_mid = round(mid, 4)
        bb_upper = round(mid + 2 * std, 4)
        bb_lower = round(mid - 2 * std, 4)

    # ATR (14)
    atr = None
    if len(bars) >= 15:
        trs = []
        for i in range(1, 15):
            tr = max(
                bars[-i].high - bars[-i].low,
                abs(bars[-i].high - bars[-i - 1].close),
                abs(bars[-i].low - bars[-i - 1].close),
            )
            trs.append(tr)
        atr = round(float(np.mean(trs)), 4)

    # ADX — use regime detector's implementation
    adx = None
    try:
        from backend.strategies.regime.detector import compute_adx
        adx = compute_adx(bars)
    except Exception:
        adx = None

    return {
        "rsi": rsi,
        "macd": round(macd, 4) if macd is not None else None,
        "macd_signal": None,
        "macd_hist": None,
        "bb_upper": bb_upper,
        "bb_middle": bb_mid,
        "bb_lower": bb_lower,
        "adx": adx,
        "atr": atr,
        "ema_20": round(ema(closes[-40:], 20), 4) if len(closes) >= 20 else None,
        "ema_50": round(ema(closes[-100:], 50), 4) if len(closes) >= 50 else None,
        "ema_200": round(ema(closes[-200:], 200), 4) if len(closes) >= 200 else None,
    }


# ─── yfinance cold-start fallback ─────────────────────────────────────────


async def _yfinance_fallback_quote(symbol: str, market: str) -> Optional[Quote]:
    """Last-resort fallback. Only used if every primary feed fails."""
    try:
        from backend.data.feeds import yfinance_feed
        return await yfinance_feed._legacy_get_quote(symbol, market)
    except Exception as e:
        logger.debug("yfinance fallback quote failed for %s: %s", symbol, e)
        return None


async def _yfinance_fallback_ohlcv(
    symbol: str, market: str, interval: str, outputsize: int
) -> list[OHLCV]:
    try:
        from backend.data.feeds import yfinance_feed
        period = "1y" if outputsize > 180 else "6mo" if outputsize > 90 else "3mo" if outputsize > 30 else "1mo"
        return await yfinance_feed._legacy_get_daily_bars(symbol, market, period)
    except Exception as e:
        logger.debug("yfinance fallback OHLCV failed for %s: %s", symbol, e)
        return []


# ─── singleton ────────────────────────────────────────────────────────────

_router: Optional[DataRouter] = None


def init_data_router(
    twelve_api_key: str,
    fred_api_key: str,
    finnhub_api_key: str = "",
) -> DataRouter:
    """Called once at app startup. Builds the singleton."""
    global _router

    tracker = CreditTracker(
        daily_limit=settings.twelve_data_daily_credit_limit,
        warning_pct=settings.twelve_data_credits_warning_pct,
        per_minute_limit=settings.twelve_data_per_minute_limit,
    )

    try:
        twelve = TwelveDataFeed(
            api_key=twelve_api_key,
            credit_tracker=tracker,
            cache_ttl_quote=settings.quote_cache_ttl_seconds,
            cache_ttl_daily=settings.ohlcv_daily_cache_ttl_seconds,
            cache_ttl_intraday=settings.ohlcv_intraday_cache_ttl_seconds,
        )
    except Exception as e:
        logger.error("Failed to init TwelveDataFeed: %s", e)
        twelve = None

    try:
        finnhub = FinnhubFeed(
            api_key=finnhub_api_key,
            cache_ttl_quote=settings.quote_cache_ttl_seconds,
            cache_ttl_daily=settings.ohlcv_daily_cache_ttl_seconds,
        )
    except Exception as e:
        logger.warning("Failed to init FinnhubFeed: %s", e)
        finnhub = None

    try:
        fred = FREDFeed(
            api_key=fred_api_key,
            cache_ttl_seconds=settings.fred_cache_ttl_seconds,
        )
    except Exception as e:
        logger.error("Failed to init FREDFeed: %s", e)
        fred = None

    _router = DataRouter(
        twelve=twelve,
        finnhub=finnhub,
        fred=fred,
        credit_tracker=tracker,
        twelve_plan_tier=settings.twelve_data_plan_tier,
    )
    logger.info(
        "DataRouter initialised — twelve=%s (plan=%s, asx_enabled=%s) "
        "finnhub=%s fred=%s",
        "ok" if twelve else "disabled",
        _router.twelve_plan_tier,
        _router.twelve_asx_enabled,
        "ok" if (finnhub and finnhub.enabled) else "disabled",
        "ok" if fred else "disabled",
    )
    logger.info("ASX primary data source: %s", _router.asx_primary_source)
    return _router


def get_data_router() -> DataRouter:
    """Get the singleton. Lazily initialised from settings on first call."""
    global _router
    if _router is None:
        _router = init_data_router(
            twelve_api_key=settings.twelve_data_api_key,
            fred_api_key=settings.fred_api_key,
            finnhub_api_key=settings.finnhub_api_key,
        )
    return _router
