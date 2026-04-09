"""Finnhub feed — US quotes, news sentiment, VIX, forex backup, earnings, insider.

Gracefully degrades if FINNHUB_API_KEY is unset — all methods raise
FeedUnavailableError which the DataRouter catches and falls back.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.data.cache import cache_get, cache_set
from backend.data.feeds.exceptions import DataFeedError, FeedUnavailableError
from backend.data.normalizer import OHLCV, Quote

logger = logging.getLogger(__name__)


def _parse_ts(ts_str) -> datetime:
    if isinstance(ts_str, (int, float)):
        return datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
    try:
        if "T" in ts_str or " " in ts_str:
            dt = datetime.fromisoformat(str(ts_str).replace(" ", "T"))
        else:
            dt = datetime.strptime(str(ts_str), "%Y-%m-%d")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


class FinnhubFeed:
    def __init__(
        self,
        api_key: Optional[str],
        cache_ttl_quote: int = 900,
        cache_ttl_daily: int = 86400,
    ):
        self.enabled = bool(api_key)
        self._api_key = api_key or ""
        self.cache_ttl_quote = cache_ttl_quote
        self.cache_ttl_daily = cache_ttl_daily
        self.client = None
        self._last_ok: Optional[datetime] = None

        if self.enabled:
            try:
                import finnhub
                self.client = finnhub.Client(api_key=self._api_key)
            except ImportError as e:
                logger.warning("finnhub-python not installed: %s", e)
                self.enabled = False

    def _require(self) -> None:
        if not self.enabled:
            raise FeedUnavailableError("FinnhubFeed disabled — no FINNHUB_API_KEY")

    def _mark_ok(self) -> None:
        self._last_ok = datetime.now(timezone.utc)

    @property
    def last_successful_call(self) -> Optional[datetime]:
        return self._last_ok

    # ─── quotes ───────────────────────────────────────────────────────────

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    async def _quote_call(self, symbol: str) -> dict:
        def _blocking():
            return self.client.quote(symbol)
        return await asyncio.to_thread(_blocking)

    async def get_quote_us(self, symbol: str) -> Quote:
        self._require()
        cache_key = f"quote:US:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            logger.debug("cache-hit finnhub quote %s", symbol)
            return Quote(
                **{k: v for k, v in cached.items() if k != "timestamp"},
                timestamp=_parse_ts(cached.get("timestamp", "")),
            )

        logger.info("Fetching Finnhub quote %s", symbol)
        try:
            data = await self._quote_call(symbol)
        except Exception as e:
            raise DataFeedError(f"Finnhub quote {symbol} failed: {e}")

        if not data or data.get("c") in (0, None):
            raise DataFeedError(f"Finnhub quote {symbol} returned no data")

        self._mark_ok()
        price = float(data["c"])
        prev = float(data.get("pc") or price)
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0
        quote = Quote(
            symbol=symbol,
            market="NYSE",
            price=round(price, 4),
            change=round(change, 4),
            change_pct=round(change_pct, 4),
            volume=int(float(data.get("v") or 0)),
            avg_volume_20d=int(float(data.get("v") or 0)),
            market_cap=None,
            pe_ratio=None,
            timestamp=datetime.now(timezone.utc),
        )
        await cache_set(cache_key, asdict(quote), self.cache_ttl_quote)
        return quote

    # ─── OHLCV ────────────────────────────────────────────────────────────

    async def get_candles_us(
        self,
        symbol: str,
        resolution: str = "D",
        days_back: int = 365,
    ) -> list[OHLCV]:
        self._require()
        cache_key = f"ohlcv:daily:US:{symbol}:{days_back}"
        cached = await cache_get(cache_key)
        if cached:
            logger.debug("cache-hit finnhub candles %s", symbol)
            return [
                OHLCV(
                    symbol=b["symbol"],
                    market=b["market"],
                    timestamp=_parse_ts(b["timestamp"]),
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

        now = datetime.now(timezone.utc)
        from_ts = int((now - timedelta(days=days_back)).timestamp())
        to_ts = int(now.timestamp())

        logger.info("Fetching Finnhub candles %s (%d days)", symbol, days_back)

        def _blocking():
            return self.client.stock_candles(symbol, resolution, from_ts, to_ts)

        try:
            data = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"Finnhub candles {symbol} failed: {e}")

        if not data or data.get("s") != "ok":
            raise DataFeedError(
                f"Finnhub candles {symbol} status={data.get('s') if data else 'None'}"
            )

        self._mark_ok()

        bars: list[OHLCV] = []
        times = data.get("t") or []
        opens = data.get("o") or []
        highs = data.get("h") or []
        lows = data.get("l") or []
        closes = data.get("c") or []
        volumes = data.get("v") or []

        for i in range(len(times)):
            try:
                if highs[i] < lows[i] or volumes[i] == 0:
                    continue
                bars.append(OHLCV(
                    symbol=symbol,
                    market="NYSE",
                    timestamp=datetime.fromtimestamp(times[i], tz=timezone.utc),
                    open=round(float(opens[i]), 4),
                    high=round(float(highs[i]), 4),
                    low=round(float(lows[i]), 4),
                    close=round(float(closes[i]), 4),
                    volume=int(volumes[i]),
                    adj_close=round(float(closes[i]), 4),
                ))
            except (IndexError, ValueError, TypeError) as e:
                logger.warning("Skipping malformed candle for %s: %s", symbol, e)
                continue

        if bars:
            await cache_set(
                cache_key,
                [{**asdict(b), "timestamp": b.timestamp.isoformat()} for b in bars],
                self.cache_ttl_daily,
            )
        return bars

    # ─── news / sentiment ─────────────────────────────────────────────────

    async def get_company_news(self, symbol: str, days_back: int = 3) -> list[dict]:
        self._require()
        cache_key = f"news:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        now = datetime.now(timezone.utc).date()
        def _blocking():
            return self.client.company_news(
                symbol,
                _from=(now - timedelta(days=days_back)).isoformat(),
                to=now.isoformat(),
            )

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"Finnhub news {symbol} failed: {e}")

        self._mark_ok()
        items = []
        for art in (raw or [])[:10]:
            items.append({
                "headline": art.get("headline", ""),
                "summary": art.get("summary", ""),
                "url": art.get("url", ""),
                "sentiment_score": 0.0,  # Finnhub free tier has no per-article sentiment
                "published_at": _parse_ts(art.get("datetime", 0)).isoformat(),
            })
        await cache_set(cache_key, items, 3600)
        return items

    async def get_market_news_sentiment(self, symbol: str) -> float:
        self._require()
        cache_key = f"news_sentiment:{symbol}"
        cached = await cache_get(cache_key)
        if cached is not None and "score" in cached:
            return float(cached["score"])

        def _blocking():
            return self.client.news_sentiment(symbol)

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            logger.warning("Finnhub news_sentiment failed: %s", e)
            return 0.0

        self._mark_ok()
        sent = raw.get("sentiment", {}) if isinstance(raw, dict) else {}
        bullish = float(sent.get("bullishPercent") or 0)
        bearish = float(sent.get("bearishPercent") or 0)
        score = bullish - bearish
        await cache_set(cache_key, {"score": score}, 3600)
        return score

    # ─── VIX ──────────────────────────────────────────────────────────────

    async def get_vix(self) -> float:
        self._require()
        cache_key = "vix:current"
        cached = await cache_get(cache_key)
        if cached and "value" in cached:
            return float(cached["value"])

        def _blocking():
            return self.client.quote("^VIX")

        try:
            data = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"Finnhub VIX failed: {e}")

        value = float(data.get("c") or 0)
        if value == 0:
            raise DataFeedError("Finnhub VIX returned 0")
        self._mark_ok()
        await cache_set(cache_key, {"value": value}, 1800)
        return value

    # ─── forex ────────────────────────────────────────────────────────────

    async def get_forex_audusd(self) -> float:
        self._require()
        cache_key = "forex:AUD:USD:finnhub"
        cached = await cache_get(cache_key)
        if cached and "rate" in cached:
            return float(cached["rate"])

        def _blocking():
            return self.client.forex_rates(base="AUD")

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"Finnhub forex failed: {e}")

        rate = float((raw or {}).get("quote", {}).get("USD") or 0)
        if rate == 0:
            raise DataFeedError("Finnhub AUD/USD returned 0")
        self._mark_ok()
        await cache_set(cache_key, {"rate": rate}, 900)
        return rate

    # ─── earnings calendar ────────────────────────────────────────────────

    async def get_earnings_calendar_us(self, days_ahead: int = 7) -> list[dict]:
        self._require()
        cache_key = f"earnings_calendar:US:{days_ahead}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        today = datetime.now(timezone.utc).date()
        def _blocking():
            return self.client.earnings_calendar(
                _from=today.isoformat(),
                to=(today + timedelta(days=days_ahead)).isoformat(),
                symbol="",
            )

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"Finnhub earnings_calendar failed: {e}")

        self._mark_ok()
        events = (raw or {}).get("earningsCalendar", []) if isinstance(raw, dict) else []
        result = [
            {
                "symbol": e.get("symbol", ""),
                "date": e.get("date", ""),
                "eps_estimate": e.get("epsEstimate"),
                "revenue_estimate": e.get("revenueEstimate"),
            }
            for e in events
        ]
        await cache_set(cache_key, result, 3600)
        return result

    # ─── insider transactions ────────────────────────────────────────────

    async def get_insider_transactions(self, symbol: str) -> list[dict]:
        self._require()
        cache_key = f"insider:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        def _blocking():
            return self.client.stock_insider_transactions(symbol)

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            logger.warning("Finnhub insider_transactions %s failed: %s", symbol, e)
            return []

        self._mark_ok()
        ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).date()
        transactions = (raw or {}).get("data", []) if isinstance(raw, dict) else []
        result = []
        for t in transactions:
            try:
                tx_date = datetime.fromisoformat(t.get("transactionDate", "")).date()
                if tx_date < ninety_days_ago:
                    continue
                result.append({
                    "name": t.get("name", ""),
                    "shares": t.get("share", 0),
                    "transaction_type": t.get("transactionCode", ""),
                    "date": t.get("transactionDate", ""),
                    "value": t.get("transactionPrice", 0) * (t.get("share") or 0),
                })
            except (ValueError, TypeError):
                continue
        await cache_set(cache_key, result, 21600)
        return result
