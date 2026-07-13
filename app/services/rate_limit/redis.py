from __future__ import annotations

import redis

from app.services.rate_limit.base import RateLimiter


class RedisRateLimiter(RateLimiter):
    _SCRIPT = """
    local count = redis.call('INCR', KEYS[1])
    if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
    return {count, redis.call('TTL', KEYS[1])}
    """

    def __init__(self, url: str) -> None:
        self.client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)

    def retry_after(self, key: str, limit: int, window_seconds: int) -> int | None:
        if limit <= 0:
            return None
        redis_key = f"face-api:limit:{key}"
        count, ttl = self.client.eval(self._SCRIPT, 1, redis_key, window_seconds)
        return max(1, int(ttl)) if int(count) > limit else None

    def ping(self) -> bool:
        return bool(self.client.ping())
