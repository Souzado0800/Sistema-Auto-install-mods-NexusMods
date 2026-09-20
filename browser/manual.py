"""Manual URL and file collection parser."""

from pathlib import Path

from utils.logging import get_logger

from .normalizer import CanonicalModKey, NormalizedModUrl, normalize_nexus_url

logger = get_logger("nexus.collector.manual")


def parse_urls_from_text(text: str) -> list[NormalizedModUrl]:
    """Parse raw multiline text containing Nexus Mods URLs."""
    seen: dict[CanonicalModKey, NormalizedModUrl] = {}
    for line in text.splitlines():
        normalized = normalize_nexus_url(line)
        if normalized:
            if normalized.key not in seen:
                seen[normalized.key] = normalized
            elif normalized.nxm_key and not seen[normalized.key].nxm_key:
                # Prefer NXM link with credentials if encountered
                seen[normalized.key] = normalized
        elif line.strip() and not line.strip().startswith("#"):
            logger.debug(f"Ignored non-mod line: {line.strip()}")
    return list(seen.values())


def parse_urls_from_file(file_path: str | Path) -> list[NormalizedModUrl]:
    """Read and parse URLs from a text file (e.g. mods.txt)."""
    p = Path(file_path)
    if not p.is_file():
        logger.error(f"Input file not found: {p}")
        return []

    content = p.read_text(encoding="utf-8")
    return parse_urls_from_text(content)
