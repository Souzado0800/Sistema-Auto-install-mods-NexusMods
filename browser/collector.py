"""Unified mod URL collector."""

from pathlib import Path

from utils.logging import get_logger

from .cdp import CdpTabCollector
from .manual import parse_urls_from_file, parse_urls_from_text
from .normalizer import CanonicalModKey, NormalizedModUrl

logger = get_logger("nexus.collector")


class ModCollector:
    """Coordinates mod URL gathering across file inputs, CLI strings, and browser CDP."""

    def __init__(self, cdp_endpoint: str = "http://127.0.0.1:9222"):
        self.cdp_collector = CdpTabCollector(endpoint_url=cdp_endpoint)

    async def collect(
        self,
        file_path: str | Path | None = None,
        raw_urls: list[str] | None = None,
        use_cdp: bool = False,
    ) -> list[NormalizedModUrl]:
        """Collect and deduplicate mods from all active sources."""
        seen: dict[CanonicalModKey, NormalizedModUrl] = {}

        # 1. Collect from text file if provided
        if file_path:
            for mod in parse_urls_from_file(file_path):
                if mod.key not in seen or (mod.nxm_key and not seen[mod.key].nxm_key):
                    seen[mod.key] = mod

        # 2. Collect from raw URLs list / CLI args
        if raw_urls:
            raw_text = "\n".join(raw_urls)
            for mod in parse_urls_from_text(raw_text):
                if mod.key not in seen or (mod.nxm_key and not seen[mod.key].nxm_key):
                    seen[mod.key] = mod

        # 3. Collect from Browser CDP if requested
        if use_cdp:
            cdp_mods = await self.cdp_collector.collect_nexus_urls()
            for mod in cdp_mods:
                if mod.key not in seen or (mod.nxm_key and not seen[mod.key].nxm_key):
                    seen[mod.key] = mod

        logger.info(f"Total unique mods collected: {len(seen)}")
        return list(seen.values())
