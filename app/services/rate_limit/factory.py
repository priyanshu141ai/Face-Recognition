from functools import lru_cache

from app.core.config import Settings
from app.services.rate_limit.base import RateLimiter
from app.services.rate_limit.memory import MemoryRateLimiter
from app.services.rate_limit.redis import RedisRateLimiter


@lru_cache(maxsize=8)
def _cached(backend: str, redis_url: str | None) -> RateLimiter:
    if backend == "redis" and redis_url:
        return RedisRateLimiter(redis_url)
    return MemoryRateLimiter()


def build_rate_limiter(settings: Settings) -> RateLimiter:
    return _cached(settings.rate_limit_backend, settings.redis_url)
