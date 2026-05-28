from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any

from loguru import logger

from app.config import settings


@lru_cache(maxsize=1)
def get_redis_client() -> Any | None:
    """Return a Redis client when enabled and reachable, otherwise None."""
    if not settings.REDIS_ENABLED:
        return None

    try:
        redis = import_module("redis")
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        logger.warning(f"Redis unavailable; falling back to local security store: {exc}")
        return None
