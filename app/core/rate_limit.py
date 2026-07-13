import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, key: str, limit: int, window_seconds: int = 60) -> int | None:
        if limit <= 0:
            return None
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= limit:
                return max(1, math.ceil(window_seconds - (now - attempts[0])))
            attempts.append(now)
            return None


_client_validation_limiter = SlidingWindowRateLimiter()


def require_client_validation_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    limit = get_settings().client_validation_rate_limit_per_minute
    retry_after = _client_validation_limiter.retry_after(client_ip, limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limit_exceeded", "message": "Too many client validation attempts"},
            headers={"Retry-After": str(retry_after)},
        )
