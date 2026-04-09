"""Credit tracker for rate-limited data providers (primarily Twelve Data).

Stores daily usage in Redis. Each source has its own key. TTL is 25h so the
counter expires an hour after UTC midnight rollover.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.db.redis import get_redis

logger = logging.getLogger(__name__)


def _today_key(source: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"credits:{source}:{today}"


def _minute_key(source: str) -> str:
    minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return f"credits:{source}:minute:{minute}"


class CreditTracker:
    def __init__(
        self,
        daily_limit: int = 800,
        warning_pct: int = 80,
        per_minute_limit: int = 8,
    ):
        self.daily_limit = daily_limit
        self.warning_pct = warning_pct
        # Twelve Data free tier: 8 credits/minute. Pro: 500/min.
        # Set to a large number on paid plans via env to disable throttling.
        self.per_minute_limit = per_minute_limit

    async def throttle(self, cost: int, source: str = "twelve_data") -> None:
        """Sleep if the upcoming `cost` would exceed the per-minute limit.

        This is the key rate-limit guard that prevents Twelve Data free
        tier from firing 'run out of API credits for the current minute'
        errors during bulk scans.
        """
        try:
            redis = await get_redis()
            key = _minute_key(source)
            used = int(await redis.get(key) or 0)
            if used + cost > self.per_minute_limit:
                # Wait until the next minute rolls over
                now = datetime.now(timezone.utc)
                seconds_left = 60 - now.second + 1
                logger.info(
                    "[throttle] %s would exceed %d/min (used=%d, cost=%d); sleeping %ds",
                    source, self.per_minute_limit, used, cost, seconds_left,
                )
                await asyncio.sleep(seconds_left)
        except Exception as e:
            logger.debug("credit_tracker.throttle soft-fail: %s", e)

    async def consume(self, credits: int, source: str = "twelve_data") -> int:
        """Add credits to daily + per-minute counters. Returns new daily total."""
        try:
            redis = await get_redis()
            # Daily counter
            day_key = _today_key(source)
            new_total = await redis.incrby(day_key, credits)
            await redis.expire(day_key, 90_000)  # 25h
            # Per-minute counter
            min_key = _minute_key(source)
            await redis.incrby(min_key, credits)
            await redis.expire(min_key, 65)
            pct = (new_total / self.daily_limit * 100) if self.daily_limit else 0
            if pct >= self.warning_pct:
                logger.warning(
                    "%s credits at %.0f%% of daily limit (%d/%d)",
                    source, pct, new_total, self.daily_limit,
                )
            else:
                logger.debug(
                    "%s credits consumed +%d → %d/%d",
                    source, credits, new_total, self.daily_limit,
                )
            return int(new_total)
        except Exception as e:
            logger.warning("credit_tracker.consume failed: %s", e)
            return 0

    async def get_used(self, source: str = "twelve_data") -> int:
        try:
            redis = await get_redis()
            val = await redis.get(_today_key(source))
            return int(val) if val else 0
        except Exception as e:
            logger.warning("credit_tracker.get_used failed: %s", e)
            return 0

    async def get_remaining(self, source: str = "twelve_data") -> int:
        used = await self.get_used(source)
        return max(0, self.daily_limit - used)

    async def check_quota(self, required: int, source: str = "twelve_data") -> bool:
        return (await self.get_remaining(source)) >= required

    async def get_status(self, source: str = "twelve_data") -> dict:
        used = await self.get_used(source)
        remaining = max(0, self.daily_limit - used)
        pct = (used / self.daily_limit * 100) if self.daily_limit else 0
        return {
            "source": source,
            "used": used,
            "remaining": remaining,
            "limit": self.daily_limit,
            "pct_used": round(pct, 1),
        }
