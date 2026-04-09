"""Twelve Data feed — primary source for ASX OHLCV/quotes/indicators/earnings/forex.

Free tier: 800 credits/day, REST only. Batch endpoints are used aggressively
to stay within quota. All responses are cached in Redis.

All API calls are wrapped with tenacity retry (3 attempts, exponential backoff)
and route exceptions through DataFeedError.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.data.cache import cache_get, cache_set
from backend.data.feeds.credit_tracker import CreditTracker
from backend.data.feeds.exceptions import DataFeedError, FeedUnavailableError
from backend.data.normalizer import OHLCV, Quote

logger = logging.getLogger(__name__)


def _strip_ax(symbol: str) -> str:
    return symbol[:-3] if symbol.endswith(".AX") else symbol


def _td_exchange(market: str) -> Optional[str]:
    """Twelve Data `exchange` parameter for each market."""
    if market == "ASX":
        return "ASX"
    return None  # US symbols use no exchange override


def _td_timezone(market: str) -> str:
    if market == "ASX":
        return "Australia/Sydney"
    return "America/New_York"


def _parse_ts(ts_str: str) -> datetime:
    """Parse Twelve Data timestamp — returns UTC."""
    try:
        if "T" in ts_str or " " in ts_str:
            dt = datetime.fromisoformat(ts_str.replace(" ", "T"))
        else:
            dt = datetime.strptime(ts_str, "%Y-%m-%d")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


class TwelveDataFeed:
    def __init__(
        self,
        api_key: str,
        credit_tracker: CreditTracker,
        cache_ttl_quote: int = 900,
        cache_ttl_daily: int = 86400,
        cache_ttl_intraday: int = 900,
    ):
        if not api_key:
            raise FeedUnavailableError("TwelveDataFeed requires TWELVE_DATA_API_KEY")
        try:
            from twelvedata import TDClient
        except ImportError as e:
            raise FeedUnavailableError(f"twelvedata package not installed: {e}")
        self._api_key = api_key
        self.client = TDClient(apikey=api_key)
        self.credit_tracker = credit_tracker
        self.cache_ttl_quote = cache_ttl_quote
        self.cache_ttl_daily = cache_ttl_daily
        self.cache_ttl_intraday = cache_ttl_intraday
        self._last_ok: Optional[datetime] = None

    # ─── utility ──────────────────────────────────────────────────────────

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
    async def _quote_call(self, symbol: str, exchange: Optional[str]) -> dict:
        def _blocking():
            q = self.client.quote(symbol=symbol, exchange=exchange) if exchange else self.client.quote(symbol=symbol)
            return q.as_json()
        return await asyncio.to_thread(_blocking)

    async def get_quote(self, symbol: str, market: str) -> Quote:
        symbol = _strip_ax(symbol)
        cache_key = f"quote:{market}:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            logger.debug("cache-hit quote %s/%s", market, symbol)
            return Quote(**{k: v for k, v in cached.items() if k != "timestamp"},
                         timestamp=_parse_ts(cached.get("timestamp", "")))

        exchange = _td_exchange(market)
        logger.info("Fetching quote %s/%s from Twelve Data", market, symbol)
        try:
            data = await self._quote_call(symbol, exchange)
        except Exception as e:
            raise DataFeedError(f"TwelveData quote {symbol} failed: {e}")

        await self.credit_tracker.consume(1)
        self._mark_ok()

        if not data or "code" in data:
            raise DataFeedError(f"TwelveData quote {symbol} bad response: {data}")

        try:
            price = float(data.get("close") or data.get("price") or 0)
            prev = float(data.get("previous_close") or price)
            change = float(data.get("change") or (price - prev))
            change_pct = float(data.get("percent_change") or 0)
            volume = int(float(data.get("volume") or 0))
            avg_vol = int(float(data.get("average_volume") or volume))
            market_cap = float(data.get("market_cap")) if data.get("market_cap") else None
            pe = float(data.get("pe")) if data.get("pe") else None
        except Exception as e:
            raise DataFeedError(f"TwelveData quote {symbol} parse error: {e}")

        quote = Quote(
            symbol=symbol,
            market=market,
            price=round(price, 4),
            change=round(change, 4),
            change_pct=round(change_pct, 4),
            volume=volume,
            avg_volume_20d=avg_vol,
            market_cap=market_cap,
            pe_ratio=pe,
            timestamp=datetime.now(timezone.utc),
        )
        await cache_set(cache_key, asdict(quote), self.cache_ttl_quote)
        return quote

    async def get_quotes_batch(self, symbols: list[str], market: str) -> dict[str, Quote]:
        """Batched quote fetcher. Splits into 100-symbol chunks.

        CRITICAL: use this from scan cycles. Never loop get_quote in a strategy.
        """
        symbols = [_strip_ax(s) for s in symbols]
        results: dict[str, Quote] = {}
        to_fetch: list[str] = []

        # Prefer cache
        for s in symbols:
            cached = await cache_get(f"quote:{market}:{s}")
            if cached:
                try:
                    results[s] = Quote(
                        **{k: v for k, v in cached.items() if k != "timestamp"},
                        timestamp=_parse_ts(cached.get("timestamp", "")),
                    )
                except Exception:
                    to_fetch.append(s)
            else:
                to_fetch.append(s)

        if not to_fetch:
            return results

        # Quota check — if insufficient, degrade to cache-only
        if not await self.credit_tracker.check_quota(len(to_fetch)):
            logger.warning(
                "Twelve Data quota insufficient for batch (%d needed, %d remaining) — cache-only",
                len(to_fetch), await self.credit_tracker.get_remaining(),
            )
            return results

        exchange = _td_exchange(market)
        CHUNK = 100

        for i in range(0, len(to_fetch), CHUNK):
            chunk = to_fetch[i:i + CHUNK]
            sym_list = ",".join(chunk)
            logger.info(
                "Fetching %d quotes from Twelve Data (chunk %d/%d)",
                len(chunk), i // CHUNK + 1, (len(to_fetch) + CHUNK - 1) // CHUNK,
            )
            try:
                def _blocking(sl=sym_list, ex=exchange):
                    q = self.client.quote(symbol=sl, exchange=ex) if ex else self.client.quote(symbol=sl)
                    return q.as_json()
                data = await asyncio.to_thread(_blocking)
            except Exception as e:
                logger.error("Twelve Data batch call failed: %s", e)
                continue

            await self.credit_tracker.consume(len(chunk))
            self._mark_ok()

            # Batch response is dict[symbol] = {...} or single dict if only one
            if not isinstance(data, dict):
                continue
            if "close" in data and len(chunk) == 1:
                data = {chunk[0]: data}
            for sym, payload in data.items():
                try:
                    if not isinstance(payload, dict) or "close" not in payload:
                        continue
                    price = float(payload.get("close") or 0)
                    change = float(payload.get("change") or 0)
                    change_pct = float(payload.get("percent_change") or 0)
                    volume = int(float(payload.get("volume") or 0))
                    avg_vol = int(float(payload.get("average_volume") or volume))
                    quote = Quote(
                        symbol=sym,
                        market=market,
                        price=round(price, 4),
                        change=round(change, 4),
                        change_pct=round(change_pct, 4),
                        volume=volume,
                        avg_volume_20d=avg_vol,
                        market_cap=float(payload.get("market_cap")) if payload.get("market_cap") else None,
                        pe_ratio=float(payload.get("pe")) if payload.get("pe") else None,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await cache_set(f"quote:{market}:{sym}", asdict(quote), self.cache_ttl_quote)
                    results[sym] = quote
                except Exception as e:
                    logger.warning("Failed to parse quote for %s: %s", sym, e)

        return results

    # ─── OHLCV ────────────────────────────────────────────────────────────

    async def get_ohlcv(
        self,
        symbol: str,
        market: str,
        interval: str = "1day",
        outputsize: int = 365,
    ) -> list[OHLCV]:
        symbol = _strip_ax(symbol)
        is_daily = interval in ("1day", "1week", "1month")
        cache_key = f"ohlcv:{interval}:{market}:{symbol}:{outputsize}"
        cached = await cache_get(cache_key)
        if cached:
            logger.debug("cache-hit ohlcv %s/%s %s", market, symbol, interval)
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

        exchange = _td_exchange(market)
        tz = _td_timezone(market)
        logger.info("Fetching OHLCV %s/%s %s (%d bars)", market, symbol, interval, outputsize)

        @retry(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
        )
        def _blocking():
            ts = self.client.time_series(
                symbol=symbol,
                interval=interval,
                outputsize=outputsize,
                timezone=tz,
                exchange=exchange,
            )
            return ts.as_json()

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"TwelveData time_series {symbol} failed: {e}")

        # Batch-ish: outputsize credits. Use outputsize as a rough proxy.
        await self.credit_tracker.consume(max(1, outputsize // 50))
        self._mark_ok()

        if not raw:
            return []

        bars: list[OHLCV] = []
        for row in raw:
            try:
                high = float(row["high"])
                low = float(row["low"])
                if high < low:
                    logger.warning("Invalid bar for %s at %s: high<low", symbol, row.get("datetime"))
                    continue
                volume = int(float(row.get("volume", 0) or 0))
                if volume == 0 and is_daily:
                    continue  # skip gap days / halts
                bar = OHLCV(
                    symbol=symbol,
                    market=market,
                    timestamp=_parse_ts(row["datetime"]),
                    open=round(float(row["open"]), 4),
                    high=round(high, 4),
                    low=round(low, 4),
                    close=round(float(row["close"]), 4),
                    volume=volume,
                    adj_close=round(float(row["close"]), 4),
                )
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Skipping malformed bar for %s: %s", symbol, e)
                continue

        # Twelve Data returns newest-first — reverse to oldest-first to match strategies
        bars.reverse()

        if bars:
            ttl = self.cache_ttl_daily if is_daily else self.cache_ttl_intraday
            await cache_set(
                cache_key,
                [{**asdict(b), "timestamp": b.timestamp.isoformat()} for b in bars],
                ttl,
            )
        return bars

    # ─── indicators ───────────────────────────────────────────────────────

    async def get_indicators(self, symbol: str, market: str) -> dict:
        """Pre-computed technicals from Twelve Data. Latest bar only."""
        symbol = _strip_ax(symbol)
        cache_key = f"indicators:{market}:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            logger.debug("cache-hit indicators %s/%s", market, symbol)
            return cached

        exchange = _td_exchange(market)
        tz = _td_timezone(market)
        logger.info("Fetching indicators %s/%s from Twelve Data", market, symbol)

        def _blocking():
            ts = (
                self.client.time_series(
                    symbol=symbol,
                    interval="1day",
                    outputsize=5,
                    timezone=tz,
                    exchange=exchange,
                )
                .with_rsi(time_period=14)
                .with_macd(fast_period=12, slow_period=26, signal_period=9)
                .with_bbands(time_period=20, sd=2)
                .with_adx(time_period=14)
                .with_atr(time_period=14)
                .with_ema(time_period=20)
                .with_ema(time_period=50)
                .with_ema(time_period=200)
            )
            return ts.as_json()

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"TwelveData indicators {symbol} failed: {e}")

        # Indicator chains cost ~1 credit per indicator × bars. 8 × 5 = 40
        await self.credit_tracker.consume(40)
        self._mark_ok()

        if not raw:
            return {}

        latest = raw[0] if isinstance(raw, list) and raw else {}

        def _f(key: str) -> Optional[float]:
            val = latest.get(key)
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        result = {
            "rsi": _f("rsi"),
            "macd": _f("macd"),
            "macd_signal": _f("macd_signal"),
            "macd_hist": _f("macd_hist"),
            "bb_upper": _f("upper_band"),
            "bb_middle": _f("middle_band"),
            "bb_lower": _f("lower_band"),
            "adx": _f("adx"),
            "atr": _f("atr"),
            "ema_20": _f("ema1") or _f("ema"),
            "ema_50": _f("ema2"),
            "ema_200": _f("ema3"),
        }
        await cache_set(cache_key, result, self.cache_ttl_quote)
        return result

    # ─── earnings calendar ────────────────────────────────────────────────

    async def get_earnings_calendar(self, market: str) -> list[dict]:
        cache_key = f"earnings_calendar:{market}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        exchange_param = "ASX" if market == "ASX" else "NYSE,NASDAQ"
        logger.info("Fetching earnings calendar for %s", exchange_param)

        def _blocking():
            return self.client.get_earnings_calendar(exchange=exchange_param).as_json()

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            logger.warning("Earnings calendar fetch failed: %s", e)
            raise DataFeedError(f"TwelveData earnings_calendar failed: {e}")

        await self.credit_tracker.consume(1)
        self._mark_ok()

        result: list[dict] = []
        if isinstance(raw, dict) and "earnings" in raw:
            events = raw.get("earnings", [])
        elif isinstance(raw, list):
            events = raw
        else:
            events = []

        for ev in events:
            if not isinstance(ev, dict):
                continue
            result.append({
                "symbol": ev.get("symbol", ""),
                "company_name": ev.get("name") or ev.get("company_name") or "",
                "date": ev.get("date") or ev.get("datetime") or "",
                "eps_estimate": ev.get("eps_estimate"),
                "revenue_estimate": ev.get("revenue_estimate"),
                "fiscal_period": ev.get("fiscal_period") or ev.get("quarter") or "",
            })

        await cache_set(cache_key, result, 3600)
        return result

    # ─── forex ────────────────────────────────────────────────────────────

    async def get_forex_rate(
        self, from_currency: str = "AUD", to_currency: str = "USD"
    ) -> float:
        cache_key = f"forex:{from_currency}:{to_currency}"
        cached = await cache_get(cache_key)
        if cached and "rate" in cached:
            return float(cached["rate"])

        logger.info("Fetching forex %s/%s from Twelve Data", from_currency, to_currency)

        def _blocking():
            return self.client.exchange_rate(
                symbol=f"{from_currency}/{to_currency}"
            ).as_json()

        try:
            raw = await asyncio.to_thread(_blocking)
        except Exception as e:
            raise DataFeedError(f"TwelveData forex {from_currency}/{to_currency} failed: {e}")

        await self.credit_tracker.consume(1)
        self._mark_ok()

        rate = float(raw.get("rate") or 0)
        if rate == 0:
            raise DataFeedError(f"TwelveData forex {from_currency}/{to_currency} returned 0")
        await cache_set(cache_key, {"rate": rate}, 900)
        return rate
