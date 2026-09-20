"""Adaptive rate limiter tracking official Nexus Mods rate limit headers."""

import asyncio
import time

import httpx

from utils.logging import get_logger

from .models import RateLimitStatus

logger = get_logger("nexus.rate_limiter")


class NexusRateLimiter:
    """
    Monitors Nexus Mods rate limit headers across responses and enforces polite request pacing.
    Respects x-rl-hourly-remaining, x-rl-daily-remaining, and Retry-After.
    """

    def __init__(self, min_request_interval: float = 0.1, safety_margin: int = 5):
        self.min_request_interval = min_request_interval
        self.safety_margin = safety_margin
        self.status = RateLimitStatus()
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

    def update_from_headers(self, headers: httpx.Headers) -> None:
        """Update rate limit counters from official Nexus Mods response headers."""
        try:
            if "x-rl-hourly-limit" in headers:
                self.status.hourly_limit = int(headers["x-rl-hourly-limit"])
            if "x-rl-hourly-remaining" in headers:
                self.status.hourly_remaining = int(headers["x-rl-hourly-remaining"])
            if "x-rl-hourly-reset" in headers:
                self.status.hourly_reset = headers["x-rl-hourly-reset"]

            if "x-rl-daily-limit" in headers:
                self.status.daily_limit = int(headers["x-rl-daily-limit"])
            if "x-rl-daily-remaining" in headers:
                self.status.daily_remaining = int(headers["x-rl-daily-remaining"])
            if "x-rl-daily-reset" in headers:
                self.status.daily_reset = headers["x-rl-daily-reset"]

            # Log warnings if approaching limits
            if self.status.hourly_remaining <= self.safety_margin:
                logger.warning(
                    f"Nexus API hourly quota almost exhausted: {self.status.hourly_remaining}/{self.status.hourly_limit} remaining!"
                )
        except Exception as e:
            logger.debug(f"Error parsing rate limit headers: {e}")

    async def acquire(self) -> None:
        """Wait if necessary to ensure polite pacing or respect remaining quotas."""
        async with self._lock:
            # Check if quotas are dangerously low
            if self.status.hourly_remaining <= 1:
                logger.warning("Hourly quota exhausted. Backing off for 60 seconds...")
                await asyncio.sleep(60.0)

            # Enforce minimum interval between requests
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - elapsed)
            self._last_request_time = time.time()

    async def handle_rate_limited(self, response: httpx.Response) -> float:
        """Handle an HTTP 429 response by extracting Retry-After or backing off."""
        retry_after = response.headers.get("retry-after")
        if retry_after and retry_after.isdigit():
            delay = float(retry_after) + 1.0
        else:
            delay = 30.0  # Default fallback wait

        logger.warning(f"Rate limited by Nexus Mods (HTTP 429). Backing off for {delay:.1f}s.")
        await asyncio.sleep(delay)
        return delay
