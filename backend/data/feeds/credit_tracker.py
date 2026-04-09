"""Credit tracker for rate-limited data providers (primarily Twelve Data).

Stores daily usage in Redis. Each source has its own key. TTL is 25h so the
counter expires an hour after UTC midnight rollover.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.db.redis import get_redis

logger = logging.getLogger(__name__)


def _today_key(source: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"credits:{source}:{today}"


class CreditTracker:
    def __init__(self, daily_limit: int = 800, warning_pct: int = 80):
        self.daily_limit = daily_limit
        self.warning_pct = warning_pct

    async def consume(self, credits: int, source: str = "twelve_data") -> int:
        """Add credits to the daily counter. Returns the new total used."""
        try:
            redis = await get_redis()
            key = _today_key(source)
            new_total = await redis.incrby(key, credits)
            await redis.expire(key, 90_000)  # 25h
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
