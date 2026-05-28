from __future__ import annotations

from collections import defaultdict
from threading import Lock

from app.core.redis_client import get_redis_client


class SecurityMetrics:
    def __init__(self, redis_client=None, prefix: str = "security:metrics"):
        self.redis = redis_client
        self.prefix = prefix
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def increment(self, name: str, **labels: str | int | None) -> None:
        key = self._key(name, labels)
        redis_client = self.redis or get_redis_client()
        if redis_client is not None:
            redis_client.incr(key)
            return

        with self._lock:
            self._counts[key] += 1

    def get(self, name: str, **labels: str | int | None) -> int:
        key = self._key(name, labels)
        redis_client = self.redis or get_redis_client()
        if redis_client is not None:
            value = redis_client.get(key)
            return int(value or 0)

        with self._lock:
            return self._counts.get(key, 0)

    def clear(self) -> None:
        redis_client = self.redis or get_redis_client()
        if redis_client is not None:
            for key in redis_client.scan_iter(f"{self.prefix}:*"):
                redis_client.delete(key)
            return

        with self._lock:
            self._counts.clear()

    def _key(self, name: str, labels: dict[str, str | int | None]) -> str:
        parts = [self.prefix, name]
        for label, value in sorted(labels.items()):
            parts.append(f"{label}={value if value is not None else 'unknown'}")
        return ":".join(parts)


security_metrics = SecurityMetrics()
