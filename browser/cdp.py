"""Chromium DevTools Protocol (CDP) tab collector."""

from typing import Any

import httpx

from utils.logging import get_logger

from .normalizer import CanonicalModKey, NormalizedModUrl, normalize_nexus_url

logger = get_logger("nexus.collector.cdp")


class CdpTabCollector:
    """
    Connects to a running Chromium-based browser (Chrome, Brave, Edge, Chromium)
    via the official DevTools debugging port to safely collect open Nexus Mods tabs.
    """

    def __init__(self, endpoint_url: str = "http://127.0.0.1:9222"):
        self.endpoint_url = endpoint_url.rstrip("/")

    async def fetch_open_tabs(self, timeout: float = 3.0) -> list[dict[str, Any]]:
        """Fetch open targets from the browser's CDP JSON endpoint."""
        url = f"{self.endpoint_url}/json/list"
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError:
                logger.debug(
                    f"Could not connect to browser at {self.endpoint_url}. "
                    "CDP debugging port is not open."
                )
                return []
            except Exception as e:
                logger.warning(f"Error querying CDP endpoint {url}: {e}")
                return []

    async def collect_nexus_urls(self, timeout: float = 3.0) -> list[NormalizedModUrl]:
        """Query browser tabs and return deduplicated normalized Nexus Mods URLs."""
        targets = await self.fetch_open_tabs(timeout=timeout)
        seen: dict[CanonicalModKey, NormalizedModUrl] = {}

        for target in targets:
            # Filter for active web pages
            if target.get("type") == "page":
                tab_url = target.get("url", "")
                if "nexusmods.com" in tab_url:
                    normalized = normalize_nexus_url(tab_url)
                    if normalized and normalized.key not in seen:
                        seen[normalized.key] = normalized
                        logger.debug(f"Collected tab: {normalized.canonical_url}")

        logger.info(f"Collected {len(seen)} unique Nexus Mods URLs from browser tabs.")
        return list(seen.values())
