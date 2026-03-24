"""Redis caching layer for market data."""

import json
import logging
from typing import Optional

from backend.db.redis import get_redis

logger = logging.getLogger(__name__)


async def cache_get(key: str) -> Optional[dict]:
    try:
        redis = await get_redis()
        data = await redis.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning("Cache get failed for %s: %s", key, e)
    return None


async def cache_set(key: str, data: dict, ttl_seconds: int = 3600) -> None:
    try:
        redis = await get_redis()
        await redis.setex(key, ttl_seconds, json.dumps(data, default=str))
    except Exception as e:
        logger.warning("Cache set failed for %s: %s", key, e)


async def cache_delete(key: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(key)
    except Exception as e:
        logger.warning("Cache delete failed for %s: %s", key, e)
