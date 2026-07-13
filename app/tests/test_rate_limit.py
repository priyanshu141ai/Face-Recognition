from app.core.rate_limit import SlidingWindowRateLimiter


def test_sliding_window_rate_limit() -> None:
    limiter = SlidingWindowRateLimiter()
    assert limiter.retry_after("client", limit=2) is None
    assert limiter.retry_after("client", limit=2) is None
    assert limiter.retry_after("client", limit=2) is not None


def test_disabled_rate_limit_allows_requests() -> None:
    limiter = SlidingWindowRateLimiter()
    assert limiter.retry_after("client", limit=0) is None
