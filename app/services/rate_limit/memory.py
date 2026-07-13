import math
import threading
import time
from collections import defaultdict, deque

from app.services.rate_limit.base import RateLimiter


class MemoryRateLimiter(RateLimiter):
    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str, limit: int, window_seconds: int) -> int | None:
        if limit <= 0:
            return None
        now, cutoff = time.monotonic(), time.monotonic() - window_seconds
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= limit:
                return max(1, math.ceil(window_seconds - (now - attempts[0])))
            attempts.append(now)
            self._last_seen[key] = now
            if len(self._last_seen) > 10_000:
                stale = [item for item, seen in self._last_seen.items() if seen <= cutoff]
                for item in stale:
                    self._last_seen.pop(item, None)
                    self._attempts.pop(item, None)
            return None
