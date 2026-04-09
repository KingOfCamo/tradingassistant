"""Shim that preserves the historical public API while routing through DataRouter.

Historically, every strategy imported:
    from backend.data.feeds.yfinance_feed import get_daily_bars, get_quote, get_fx_rate

These names are preserved. The implementations now call the DataRouter
singleton (Twelve Data for ASX, Finnhub for US). Actual yfinance calls only
occur in the `_legacy_*` helpers which DataRouter uses as a last-resort
cold-start fallback.

This keeps the strategy layer unchanged while ensuring yfinance is never on
a live signal path.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from backend.data.cache import cache_get, cache_set
from backend.data.normalizer import OHLCV, Quote

logger = logging.getLogger(__name__)

# Cache TTLs (kept for legacy fallback path only)
DAILY_BAR_TTL = 86400
INTRADAY_TTL = 900
QUOTE_TTL = 900

# period → outputsize mapping shared with DataRouter
_PERIOD_TO_OUTPUTSIZE = {
    "1d": 1,
    "5d": 5,
    "1mo": 22,
    "3mo": 66,
    "6mo": 132,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
}


def _strip_ax(symbol: str) -> str:
    return symbol[:-3] if symbol.endswith(".AX") else symbol


# ─── Public API — routes through DataRouter ───────────────────────────────


async def get_daily_bars(
    symbol: str,
    market: str,
    period: str = "1y",
    use_cache: bool = True,
) -> list[OHLCV]:
    """Fetch daily OHLCV bars via DataRouter.

    Signature preserved for historical callers. The `period` string is
    translated to Twelve Data's `outputsize` integer.
    """
    from backend.data.feeds.data_router import get_data_router
    outputsize = _PERIOD_TO_OUTPUTSIZE.get(period, 365)
    try:
        router = get_data_router()
        bars = await router.get_ohlcv(_strip_ax(symbol), market, "1day", outputsize)
        return bars
    except Exception as e:
        logger.warning("DataRouter OHLCV failed for %s/%s: %s — falling back to yfinance", market, symbol, e)
        return await _legacy_get_daily_bars(symbol, market, period)


async def get_quote(symbol: str, market: str) -> Optional[Quote]:
    from backend.data.feeds.data_router import get_data_router
    try:
        return await get_data_router().get_quote(_strip_ax(symbol), market)
    except Exception as e:
        logger.warning("DataRouter quote failed for %s/%s: %s — falling back to yfinance", market, symbol, e)
        return await _legacy_get_quote(symbol, market)


async def get_fx_rate(pair: str = "AUDUSD=X") -> float:
    from backend.data.feeds.data_router import get_data_router
    try:
        return await get_data_router().get_forex_audusd()
    except Exception as e:
        logger.warning("DataRouter FX failed: %s — falling back", e)
        return await _legacy_get_fx_rate(pair)


# ─── Legacy yfinance implementations (fallback only) ──────────────────────

def _to_yf_symbol(symbol: str, market: str) -> str:
    if market == "ASX" and not symbol.endswith(".AX"):
        return f"{symbol}.AX"
    return symbol


async def _legacy_get_daily_bars(symbol: str, market: str, period: str = "1y") -> list[OHLCV]:
    """Original yfinance implementation — used only as last-resort fallback."""
    cache_key = f"legacy_daily_bars:{market}:{symbol}:{period}"
    cached = await cache_get(cache_key)
    if cached:
        return [
            OHLCV(
                symbol=b["symbol"],
                market=b["market"],
                timestamp=datetime.fromisoformat(b["timestamp"]) if isinstance(b["timestamp"], str) else b["timestamp"],
                open=b["open"],
                high=b["high"],
                low=b["low"],
                close=b["close"],
                volume=b["volume"],
                adj_close=b.get("adj_close"),
                vwap=b.get("vwap"),
            )
            for b in cached
        ]

    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed and no primary feed worked")
        return []

    yf_symbol = _to_yf_symbol(_strip_ax(symbol), market)
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, auto_adjust=True)
        if df.empty:
            return []
        bars = []
        for idx, row in df.iterrows():
            if row["High"] < row["Low"] or row["Volume"] == 0:
                continue
            bar = OHLCV(
                symbol=_strip_ax(symbol),
                market=market,
                timestamp=idx.to_pydatetime().replace(tzinfo=timezone.utc) if idx.tzinfo is None else idx.to_pydatetime().astimezone(timezone.utc),
                open=round(float(row["Open"]), 4),
                high=round(float(row["High"]), 4),
                low=round(float(row["Low"]), 4),
                close=round(float(row["Close"]), 4),
                volume=int(row["Volume"]),
                adj_close=round(float(row["Close"]), 4),
            )
            bars.append(bar)
        if bars:
            await cache_set(
                cache_key,
                [{**asdict(b), "timestamp": b.timestamp.isoformat()} for b in bars],
                DAILY_BAR_TTL,
            )
        return bars
    except Exception as e:
        logger.error("yfinance fallback failed for %s: %s", yf_symbol, e)
        return []


async def _legacy_get_quote(symbol: str, market: str) -> Optional[Quote]:
    cache_key = f"legacy_quote:{market}:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        try:
            ts = cached.get("timestamp")
            return Quote(
                **{k: v for k, v in cached.items() if k != "timestamp"},
                timestamp=datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.now(timezone.utc),
            )
        except Exception:
            pass

    try:
        import yfinance as yf
    except ImportError:
        return None

    yf_symbol = _to_yf_symbol(_strip_ax(symbol), market)
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        quote = Quote(
            symbol=_strip_ax(symbol),
            market=market,
            price=float(info.get("currentPrice") or info.get("regularMarketPrice") or 0),
            change=float(info.get("regularMarketChange") or 0),
            change_pct=float(info.get("regularMarketChangePercent") or 0),
            volume=int(info.get("regularMarketVolume") or 0),
            avg_volume_20d=int(info.get("averageDailyVolume10Day") or 0),
            market_cap=float(info.get("marketCap")) if info.get("marketCap") else None,
            pe_ratio=float(info.get("trailingPE")) if info.get("trailingPE") else None,
            timestamp=datetime.now(timezone.utc),
        )
        await cache_set(cache_key, {**asdict(quote), "timestamp": quote.timestamp.isoformat()}, QUOTE_TTL)
        return quote
    except Exception as e:
        logger.error("yfinance fallback quote failed for %s: %s", yf_symbol, e)
        return None


async def _legacy_get_fx_rate(pair: str = "AUDUSD=X") -> float:
    try:
        import yfinance as yf
        ticker = yf.Ticker(pair)
        info = ticker.info
        rate = float(info.get("regularMarketPrice", 0.65))
        return rate or 0.65
    except Exception:
        return 0.65
