"""Market data feed using yfinance."""

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import yfinance as yf

from backend.data.normalizer import OHLCV, Quote
from backend.data.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

# Cache TTLs
DAILY_BAR_TTL = 86400       # 24 hours
INTRADAY_TTL = 900          # 15 minutes
QUOTE_TTL = 60              # 1 minute


def _to_yf_symbol(symbol: str, market: str) -> str:
    """Convert internal symbol to yfinance format."""
    if market == "ASX" and not symbol.endswith(".AX"):
        return f"{symbol}.AX"
    return symbol


def _from_yf_symbol(symbol: str) -> str:
    """Strip .AX suffix for internal use."""
    return symbol.replace(".AX", "")


def _detect_market(symbol: str) -> str:
    """Detect market from yfinance ticker info."""
    if symbol.endswith(".AX"):
        return "ASX"
    return "NYSE"  # Default; could be NASDAQ


async def get_daily_bars(
    symbol: str,
    market: str,
    period: str = "1y",
    use_cache: bool = True,
) -> list[OHLCV]:
    """Fetch daily OHLCV bars."""
    cache_key = f"daily_bars:{market}:{symbol}:{period}"

    if use_cache:
        cached = await cache_get(cache_key)
        if cached:
            return [OHLCV(**bar) for bar in cached]

    yf_symbol = _to_yf_symbol(symbol, market)
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, auto_adjust=True)

        if df.empty:
            logger.warning("No data returned for %s", yf_symbol)
            return []

        bars = []
        for idx, row in df.iterrows():
            # Validate: reject rows where high < low or volume == 0
            if row["High"] < row["Low"]:
                logger.warning("Invalid bar for %s at %s: high < low", symbol, idx)
                continue
            if row["Volume"] == 0:
                continue

            bar = OHLCV(
                symbol=symbol,
                market=market,
                timestamp=idx.to_pydatetime().replace(tzinfo=timezone.utc),
                open=round(float(row["Open"]), 4),
                high=round(float(row["High"]), 4),
                low=round(float(row["Low"]), 4),
                close=round(float(row["Close"]), 4),
                volume=int(row["Volume"]),
                adj_close=round(float(row["Close"]), 4),
            )
            bars.append(bar)

        if bars and use_cache:
            from dataclasses import asdict
            await cache_set(cache_key, [asdict(b) for b in bars], DAILY_BAR_TTL)

        return bars

    except Exception as e:
        logger.error("Failed to fetch daily bars for %s: %s", yf_symbol, e)
        return []


async def get_quote(symbol: str, market: str) -> Optional[Quote]:
    """Get current quote for a symbol."""
    cache_key = f"quote:{market}:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return Quote(**cached)

    yf_symbol = _to_yf_symbol(symbol, market)
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        quote = Quote(
            symbol=symbol,
            market=market,
            price=float(info.get("currentPrice", info.get("regularMarketPrice", 0))),
            change=float(info.get("regularMarketChange", 0)),
            change_pct=float(info.get("regularMarketChangePercent", 0)),
            volume=int(info.get("regularMarketVolume", 0)),
            avg_volume_20d=int(info.get("averageDailyVolume10Day", 0)),
            market_cap=float(info.get("marketCap", 0)) if info.get("marketCap") else None,
            pe_ratio=float(info.get("trailingPE", 0)) if info.get("trailingPE") else None,
            timestamp=datetime.now(timezone.utc),
        )

        from dataclasses import asdict
        await cache_set(cache_key, asdict(quote), QUOTE_TTL)
        return quote

    except Exception as e:
        logger.error("Failed to get quote for %s: %s", yf_symbol, e)
        return None


async def get_fx_rate(pair: str = "AUDUSD=X") -> float:
    """Get current FX rate (default AUD/USD)."""
    cache_key = f"fx:{pair}"
    cached = await cache_get(cache_key)
    if cached:
        return cached.get("rate", 0.65)

    try:
        ticker = yf.Ticker(pair)
        info = ticker.info
        rate = float(info.get("regularMarketPrice", 0.65))
        await cache_set(cache_key, {"rate": rate}, 300)  # 5 min TTL
        return rate
    except Exception as e:
        logger.error("Failed to get FX rate %s: %s", pair, e)
        return 0.65  # Fallback
