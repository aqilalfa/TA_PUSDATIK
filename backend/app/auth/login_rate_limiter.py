from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import ceil
from threading import Lock
from time import time
from typing import Any

from app.config import settings
from app.core.redis_client import get_redis_client


@dataclass
class LoginRateLimiter:
    """In-memory failed-login limiter for single-process deployments/tests.

    Production deployments with multiple backend instances should replace this
    storage with Redis so counters are shared across workers.
    """

    max_failures: int = 5
    window_seconds: int = 60
    key_prefix: str = "security:rate_limit"
    redis_client: Any | None = None
    _failures: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))
    _lock: Lock = field(default_factory=Lock)

    def get_retry_after(self, key: str) -> int | None:
        redis_retry_after = self._redis_retry_after(key)
        if redis_retry_after is not None:
            return redis_retry_after

        now = time()
        with self._lock:
            attempts = self._failures[key]
            self._prune(attempts, now)
            if len(attempts) < self.max_failures:
                return None
            return self._retry_after(attempts, now)

    def record_failure(self, key: str) -> None:
        if self._redis_record(key):
            return

        now = time()
        with self._lock:
            attempts = self._failures[key]
            self._prune(attempts, now)
            attempts.append(now)

    def reset(self, key: str) -> None:
        redis_client = self._redis()
        if redis_client is not None:
            redis_client.delete(self._key(key))
            return

        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        redis_client = self._redis()
        if redis_client is not None:
            for key in redis_client.scan_iter(f"{self.key_prefix}:*"):
                redis_client.delete(key)
            return

        with self._lock:
            self._failures.clear()

    def _prune(self, attempts: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()

    def _retry_after(self, attempts: deque[float], now: float) -> int:
        if not attempts:
            return self.window_seconds
        return max(1, ceil(self.window_seconds - (now - attempts[0])))

    def _redis(self) -> Any | None:
        return self.redis_client or get_redis_client()

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def _redis_retry_after(self, key: str) -> int | None:
        redis_client = self._redis()
        if redis_client is None:
            return None

        count = int(redis_client.get(self._key(key)) or 0)
        if count < self.max_failures:
            return None
        ttl = redis_client.ttl(self._key(key))
        return max(1, int(ttl if ttl and ttl > 0 else self.window_seconds))

    def _redis_record(self, key: str) -> bool:
        redis_client = self._redis()
        if redis_client is None:
            return False

        redis_key = self._key(key)
        count = redis_client.incr(redis_key)
        if count == 1:
            redis_client.expire(redis_key, self.window_seconds)
        return True


login_failed_rate_limiter = LoginRateLimiter(
    max_failures=settings.FAILED_LOGIN_RATE_LIMIT,
    window_seconds=settings.FAILED_LOGIN_RATE_WINDOW_SECONDS,
    key_prefix="security:rate_limit:failed_login",
)
chat_rate_limiter = LoginRateLimiter(
    max_failures=settings.CHAT_RATE_LIMIT,
    window_seconds=settings.CHAT_RATE_WINDOW_SECONDS,
    key_prefix="security:rate_limit:chat",
)
