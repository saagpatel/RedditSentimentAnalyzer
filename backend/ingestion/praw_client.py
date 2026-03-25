"""PRAW client with keyring auth and token-bucket rate limiter."""

from __future__ import annotations

import logging
import threading
import time
from typing import TypeVar

import keyring
import praw
from prawcore.exceptions import ResponseException

from backend.config import get_config

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Token-bucket rate limiter
# ---------------------------------------------------------------------------

class TokenBucketRateLimiter:
    """Thread-safe token bucket. Default: 80 tokens/minute, burst capacity 80."""

    def __init__(self, rate: float = 80.0, capacity: float = 80.0) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """Block until token available or timeout. Returns True if acquired."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                wait = (tokens - self.tokens) * (60.0 / self.rate)

            if time.monotonic() + wait > deadline:
                logger.warning("Rate limiter timeout — could not acquire token")
                return False
            time.sleep(min(wait, 0.5))

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * (self.rate / 60.0))
        self.last_refill = now


_rate_limiter: TokenBucketRateLimiter | None = None


def _get_rate_limiter() -> TokenBucketRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        config = get_config()
        rpm = config.ingestion.rate_limit_requests_per_min
        _rate_limiter = TokenBucketRateLimiter(rate=rpm, capacity=rpm)
    return _rate_limiter


# ---------------------------------------------------------------------------
# PRAW client
# ---------------------------------------------------------------------------

def get_reddit_client() -> praw.Reddit:
    """Create authenticated read-only PRAW client using keyring credentials."""
    client_id = keyring.get_password("reddit_sentiment", "client_id")
    client_secret = keyring.get_password("reddit_sentiment", "client_secret")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Reddit credentials not found in keyring. "
            "Run: python scripts/setup_keyring.py"
        )

    config = get_config()
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=config.user_agent,
    )


# ---------------------------------------------------------------------------
# Rate-limited fetching
# ---------------------------------------------------------------------------

def rate_limited_fetch(listing_generator: object, limit: int) -> list:
    """Consume a PRAW listing generator with rate limiting.

    Acquires a rate-limiter token every 100 items (one per Reddit API page).
    """
    limiter = _get_rate_limiter()
    limiter.acquire()  # first page

    results: list = []
    for item in listing_generator:
        results.append(item)
        if len(results) >= limit:
            break
        if len(results) % 100 == 0:
            limiter.acquire()

    return results


def fetch_with_backoff(
    fetch_fn: object,
    max_retries: int = 3,
) -> object:
    """Wrap a PRAW fetch call with exponential backoff on 429/5xx."""
    for attempt in range(max_retries + 1):
        try:
            return fetch_fn()
        except ResponseException as exc:
            status = exc.response.status_code
            if status == 429:
                wait = min(2**attempt * 5, 60)
                logger.warning(
                    "Rate limited (429). Retrying in %ds (attempt %d/%d)",
                    wait, attempt + 1, max_retries + 1,
                )
                time.sleep(wait)
            elif status >= 500:
                wait = min(2**attempt * 2, 30)
                logger.warning(
                    "Server error (%d). Retrying in %ds (attempt %d/%d)",
                    status, wait, attempt + 1, max_retries + 1,
                )
                time.sleep(wait)
            else:
                raise
        except Exception:
            if attempt == max_retries:
                raise
            wait = min(2**attempt * 2, 30)
            logger.warning(
                "Network error. Retrying in %ds (attempt %d/%d)",
                wait, attempt + 1, max_retries + 1,
            )
            time.sleep(wait)

    raise RuntimeError(f"Failed after {max_retries + 1} attempts")
