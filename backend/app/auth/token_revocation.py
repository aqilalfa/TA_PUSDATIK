from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from threading import Lock
from time import time

from app.config import settings
from app.core.redis_client import get_redis_client


class TokenRevocationStore:
    def __init__(self, redis_client=None, prefix: str = "security:revoked_token"):
        self.redis = redis_client
        self.prefix = prefix
        self._revoked_until: dict[str, float] = {}
        self._lock = Lock()

    def revoke(self, jti: str | None, exp: int | None) -> None:
        if not jti or not exp:
            return

        ttl = max(1, int(exp - datetime.now(timezone.utc).timestamp()))
        redis_client = self.redis or get_redis_client()
        if redis_client is not None:
            redis_client.setex(self._key(jti), ttl, "1")
            return

        with self._lock:
            self._revoked_until[jti] = time() + ttl

    def is_revoked(self, jti: str | None) -> bool:
        if not jti:
            return True

        redis_client = self.redis or get_redis_client()
        if redis_client is not None:
            return bool(redis_client.exists(self._key(jti)))

        now = time()
        with self._lock:
            expires_at = self._revoked_until.get(jti)
            if expires_at is None:
                return False
            if expires_at <= now:
                self._revoked_until.pop(jti, None)
                return False
            return True

    def clear(self) -> None:
        redis_client = self.redis or get_redis_client()
        if redis_client is not None:
            for key in redis_client.scan_iter(f"{self.prefix}:*"):
                redis_client.delete(key)
            return

        with self._lock:
            self._revoked_until.clear()

    def _key(self, jti: str) -> str:
        return f"{self.prefix}:{jti}"


token_revocation_store = TokenRevocationStore()
