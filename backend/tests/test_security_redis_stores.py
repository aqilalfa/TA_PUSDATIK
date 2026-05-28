import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.auth.login_rate_limiter import LoginRateLimiter
from app.auth.token_revocation import TokenRevocationStore
from app.core.security_metrics import SecurityMetrics


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key, seconds):
        self.ttls[key] = seconds

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    def exists(self, key):
        return key in self.values

    def scan_iter(self, pattern):
        prefix = pattern.rstrip("*")
        return [key for key in list(self.values) if key.startswith(prefix)]

    def delete(self, key):
        self.values.pop(key, None)
        self.ttls.pop(key, None)


def test_rate_limiter_uses_redis_counter_and_ttl():
    redis = FakeRedis()
    limiter = LoginRateLimiter(max_failures=2, window_seconds=60, key_prefix="test:limit", redis_client=redis)

    assert limiter.get_retry_after("user:1") is None
    limiter.record_failure("user:1")
    limiter.record_failure("user:1")

    assert limiter.get_retry_after("user:1") == 60
    assert redis.values["test:limit:user:1"] == 2
    assert redis.ttls["test:limit:user:1"] == 60


def test_token_revocation_store_uses_redis_setex():
    redis = FakeRedis()
    store = TokenRevocationStore(redis_client=redis, prefix="test:revoked")

    store.revoke("jti-1", 4102444800)

    assert store.is_revoked("jti-1") is True
    assert "test:revoked:jti-1" in redis.values


def test_security_metrics_use_redis_incr():
    redis = FakeRedis()
    metrics = SecurityMetrics(redis_client=redis, prefix="test:metrics")

    metrics.increment("http.429", endpoint="chat")
    metrics.increment("http.429", endpoint="chat")

    assert metrics.get("http.429", endpoint="chat") == 2
