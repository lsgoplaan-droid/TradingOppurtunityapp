import asyncio
import time
import pytest
from packages.data_adapters.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_burst():
    limiter = TokenBucketRateLimiter(tokens_per_minute=60)
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, "5 requests from full bucket should complete in < 1s"


@pytest.mark.asyncio
async def test_rate_limiter_throttles():
    # With 6 tokens/min (0.1/sec), acquiring 3 tokens should take ~2s
    limiter = TokenBucketRateLimiter(tokens_per_minute=6)
    # drain the bucket
    for _ in range(6):
        await limiter.acquire()
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 8.0, f"Should wait ~10s for 1 token at 6/min, got {elapsed:.1f}s"
