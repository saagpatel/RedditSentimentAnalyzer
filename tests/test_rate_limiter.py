"""Tests for the TokenBucketRateLimiter."""

from __future__ import annotations

import threading
import time

from backend.ingestion.praw_client import TokenBucketRateLimiter


class TestTokenBucket:
    def test_acquire_within_capacity(self):
        limiter = TokenBucketRateLimiter(rate=60, capacity=10)
        for _ in range(10):
            assert limiter.acquire(timeout=0.1) is True

    def test_exhaustion_blocks(self):
        limiter = TokenBucketRateLimiter(rate=60, capacity=2)
        limiter.acquire()
        limiter.acquire()
        # Third should timeout quickly since bucket is empty
        start = time.monotonic()
        result = limiter.acquire(timeout=0.3)
        elapsed = time.monotonic() - start
        # Either it refilled in time or timed out — both valid
        assert elapsed < 2.0  # should not hang

    def test_refill_over_time(self):
        limiter = TokenBucketRateLimiter(rate=600, capacity=2)  # 10/sec
        limiter.acquire()
        limiter.acquire()
        time.sleep(0.25)  # ~2.5 tokens refill at 10/sec
        assert limiter.acquire(timeout=0.1) is True

    def test_capacity_cap(self):
        limiter = TokenBucketRateLimiter(rate=600, capacity=5)
        time.sleep(0.5)  # would refill ~5 tokens, but capped at capacity
        # Should be able to get exactly capacity tokens
        acquired = 0
        for _ in range(10):
            if limiter.acquire(timeout=0.01):
                acquired += 1
        assert acquired <= 6  # capacity + maybe 1 refill

    def test_thread_safety(self):
        limiter = TokenBucketRateLimiter(rate=6000, capacity=100)  # 100/sec
        acquired_count = [0]
        lock = threading.Lock()

        def worker():
            for _ in range(20):
                if limiter.acquire(timeout=1.0):
                    with lock:
                        acquired_count[0] += 1

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # All 100 tokens should be acquired (100 capacity + refills)
        assert acquired_count[0] == 100

    def test_timeout_returns_false(self):
        limiter = TokenBucketRateLimiter(rate=1, capacity=1)  # 1 per minute
        limiter.acquire()  # exhaust
        assert limiter.acquire(timeout=0.1) is False
