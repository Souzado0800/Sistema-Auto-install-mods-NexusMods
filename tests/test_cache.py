"""Tests for persistent two-tier metadata caching."""

import time

from cache.cache_manager import CacheManager
from database.repositories import CacheRepository


def test_cache_hit_and_miss(repositories):
    cache_repo: CacheRepository = repositories["cache"]
    mgr = CacheManager(cache_repo, default_ttl=60)

    # Initially miss
    assert mgr.get("mod:skyrim:100") is None
    assert mgr.misses == 1
    assert mgr.hits == 0

    # Set value
    sample_data = {"name": "SkyUI", "version": "5.2"}
    mgr.set("mod:skyrim:100", sample_data)

    # Now hit
    cached = mgr.get("mod:skyrim:100")
    assert cached == sample_data
    assert mgr.hits == 1

    stats = mgr.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_ratio_percent"] == 50.0


def test_cache_expiration(repositories):
    cache_repo: CacheRepository = repositories["cache"]
    mgr = CacheManager(cache_repo, default_ttl=1)  # 1 second TTL

    mgr.set("short_lived", {"foo": "bar"}, ttl=1)
    assert mgr.get("short_lived") is not None

    time.sleep(1.2)  # Wait for expiration
    assert mgr.get("short_lived") is None


def test_cache_persistence_across_instances(repositories):
    cache_repo: CacheRepository = repositories["cache"]

    mgr1 = CacheManager(cache_repo, default_ttl=60)
    mgr1.set("persisted_key", {"data": 12345})

    # Create completely new manager instance with clean memory
    mgr2 = CacheManager(cache_repo, default_ttl=60)
    result = mgr2.get("persisted_key")
    assert result == {"data": 12345}
