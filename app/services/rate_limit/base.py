from abc import ABC, abstractmethod


class RateLimiter(ABC):
    @abstractmethod
    def retry_after(self, key: str, limit: int, window_seconds: int) -> int | None:
        raise NotImplementedError
