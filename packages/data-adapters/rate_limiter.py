"""Token bucket rate limiter for API adapters."""
import asyncio
import time


class TokenBucketRateLimiter:
    """Thread-safe async token bucket. Blocks callers when tokens are exhausted."""

    def __init__(self, tokens_per_minute: int):
        self._capacity = tokens_per_minute
        self._tokens = float(tokens_per_minute)
        self._refill_rate = tokens_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self._capacity,
                self._tokens + elapsed * self._refill_rate
            )
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) / self._refill_rate
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1
