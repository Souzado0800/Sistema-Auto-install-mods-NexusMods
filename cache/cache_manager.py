"""High-performance two-tier cache with TTL, memory LRU, and SQLite persistence."""

import time
from collections import OrderedDict
from typing import Any

from database.repositories import CacheRepository
from utils.logging import get_logger

logger = get_logger("nexus.cache")


class CacheManager:
    """
    Tier-1 In-memory LRU cache + Tier-2 Persistent SQLite cache with TTL.
    Tracks cache hits, misses, and observability stats.
    """

    def __init__(
        self,
        cache_repo: CacheRepository,
        default_ttl: int = 3600,
        max_memory_items: int = 1000,
    ):
        self.repo = cache_repo
        self.default_ttl = default_ttl
        self.max_memory_items = max_memory_items
        self._memory_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.hits: int = 0
        self.misses: int = 0

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve item from Tier-1 (memory) or Tier-2 (SQLite) if not expired."""
        now = time.time()

        # Check Tier-1 (Memory)
        if key in self._memory_cache:
            item = self._memory_cache[key]
            if item["expires_at"] > now:
                self.hits += 1
                self._memory_cache.move_to_end(key)
                return item["data"]
            else:
                del self._memory_cache[key]

        # Check Tier-2 (SQLite)
        db_val = self.repo.get(key)
        if db_val is not None:
            self.hits += 1
            # Promote to Tier-1
            self._set_memory(key, db_val, self.default_ttl)
            return db_val

        self.misses += 1
        return None

    def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        """Store item in both memory and persistent storage."""
        actual_ttl = ttl if ttl is not None else self.default_ttl
        self._set_memory(key, value, actual_ttl)
        try:
            self.repo.set(key, value, actual_ttl)
        except Exception as e:
            logger.warning(f"Failed to persist cache entry {key}: {e}")

    def _set_memory(self, key: str, value: dict[str, Any], ttl: int) -> None:
        expires_at = time.time() + ttl
        if key in self._memory_cache:
            del self._memory_cache[key]
        elif len(self._memory_cache) >= self.max_memory_items:
            self._memory_cache.popitem(last=False)  # Evict LRU

        self._memory_cache[key] = {"data": value, "expires_at": expires_at}

    def stats(self) -> dict[str, Any]:
        """Return cache hit/miss and efficiency metrics."""
        total = self.hits + self.misses
        ratio = (self.hits / total * 100.0) if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_queries": total,
            "hit_ratio_percent": round(ratio, 2),
            "memory_items": len(self._memory_cache),
        }
