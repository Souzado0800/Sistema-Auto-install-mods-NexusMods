"""Async retry logic with exponential backoff, jitter, and error classification."""

import asyncio
import random
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

from .logging import get_logger

logger = get_logger("nexus.retry")

T = TypeVar("T")

# HTTP status codes that are permanent and should NOT be retried
NON_RETRYABLE_STATUS_CODES: set[int] = {400, 401, 403, 404, 410, 422}


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


class FatalError(Exception):
    """Exception indicating an operation failed permanently and must not be retried."""


def is_transient_error(exc: Exception) -> bool:
    """Determine whether an exception is transient (retryable) or permanent."""
    if isinstance(exc, FatalError):
        return False

    # Check for HTTP status attributes on httpx / aiohttp exceptions
    status_code = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    if status_code is not None:
        if status_code in NON_RETRYABLE_STATUS_CODES:
            return False
        if status_code in {429, 500, 502, 503, 504}:
            return True

    # Generic network and timeout errors are retryable
    exc_name = type(exc).__name__.lower()
    if any(k in exc_name for k in ("timeout", "connection", "reset", "remotedisconnected", "temporarily")):
        return True

    return True


async def retry_async(
    func: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    config: RetryConfig | None = None,
    op_name: str = "operation",
    **kwargs: Any,
) -> T:
    """
    Execute an async function with exponential backoff and jitter for transient errors.
    """
    cfg = config or RetryConfig()
    delay = cfg.initial_delay
    last_exc: Exception | None = None

    for attempt in range(1, cfg.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc

            if not is_transient_error(exc):
                logger.error(f"{op_name} encountered permanent error ({type(exc).__name__}: {exc}). Aborting retries.")
                raise

            if attempt >= cfg.max_retries:
                logger.error(f"{op_name} failed after {attempt} attempts: {exc}")
                raise

            # Check if exception has a Retry-After header
            retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("retry-after")
            if retry_after and retry_after.isdigit():
                sleep_time = float(retry_after) + 0.5
            else:
                sleep_time = min(delay, cfg.max_delay)
                if cfg.jitter:
                    sleep_time = sleep_time * (0.5 + random.random())

            logger.warning(
                f"{op_name} failed attempt {attempt}/{cfg.max_retries} ({type(exc).__name__}: {exc}). "
                f"Retrying in {sleep_time:.2f}s..."
            )
            await asyncio.sleep(sleep_time)
            delay *= cfg.backoff_factor

    assert last_exc is not None
    raise last_exc
