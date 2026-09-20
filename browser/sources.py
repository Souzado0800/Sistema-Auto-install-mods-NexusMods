"""Pluggable mod URL input sources."""

import abc
import shutil
import subprocess
from pathlib import Path

from .cdp import CdpTabCollector
from .manual import parse_urls_from_file, parse_urls_from_text
from utils.logging import get_logger

logger = get_logger("nexus.sources")


class ModSource(abc.ABC):
    """Abstract interface for any source delivering Nexus Mods URLs to the pipeline."""

    @abc.abstractmethod
    async def collect(self) -> list[str]:
        """Collect and return raw URL strings from the source."""
        pass


class TextFileSource(ModSource):
    """Reads URLs from a text file (e.g. mods.txt)."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    async def collect(self) -> list[str]:
        if not self.file_path.is_file():
            logger.warning(f"File source not found: {self.file_path}")
            return []
        mods = parse_urls_from_file(self.file_path)
        return [m.original_url for m in mods]


class ManualURLSource(ModSource):
    """Ingests URLs provided directly via CLI arguments."""

    def __init__(self, urls: list[str]):
        self.urls = urls or []

    async def collect(self) -> list[str]:
        raw_text = "\n".join(self.urls)
        mods = parse_urls_from_text(raw_text)
        return [m.original_url for m in mods]


class BrowserTabsSource(ModSource):
    """Pulls open Nexus Mods tabs via the Chromium DevTools Protocol (CDP)."""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222"):
        self.collector = CdpTabCollector(endpoint_url=cdp_url)

    async def collect(self) -> list[str]:
        mods = await self.collector.collect_nexus_urls()
        return [m.original_url for m in mods]


class BrowserSessionSource(ModSource):
    """Pulls open Nexus Mods tabs by inspecting browser session files on disk in read-only mode."""

    def __init__(self, target_game: str = "mysummercar"):
        self.target_game = target_game

    async def collect(self) -> list[str]:
        from .session_reader import ChromiumSessionReader
        report = ChromiumSessionReader.extract_nexus_tabs(target_game=self.target_game)
        if report:
            logger.info(f"Discovered {len(report.unique_mods)} mod tabs in {report.browser_name} session.")
            return [m.canonical_url for m in report.unique_mods]
        return []


class AutoBrowserSource(ModSource):
    """
    Intelligent browser tab source:
    1. Tries CDP port 9222 first if active.
    2. Falls back to read-only browser session inspection on disk.
    """

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222", target_game: str = "mysummercar"):
        self.cdp_url = cdp_url
        self.target_game = target_game

    async def collect(self) -> list[str]:
        # 1. Try CDP
        cdp_source = BrowserTabsSource(cdp_url=self.cdp_url)
        try:
            urls = await cdp_source.collect()
            if urls:
                logger.info(f"Collected {len(urls)} tabs via CDP ({self.cdp_url}).")
                return urls
        except Exception as e:
            logger.debug(f"CDP connection failed: {e}")

        # 2. Try direct session reading
        session_source = BrowserSessionSource(target_game=self.target_game)
        session_urls = await session_source.collect()
        if session_urls:
            return session_urls

        return []


class ClipboardSource(ModSource):
    """Pulls URLs from system clipboard via wl-paste or xclip on Linux."""

    async def collect(self) -> list[str]:
        text = ""
        try:
            if shutil.which("wl-paste"):
                proc = subprocess.run(["wl-paste"], capture_output=True, text=True, timeout=2.0)
                if proc.returncode == 0:
                    text = proc.stdout
            elif shutil.which("xclip"):
                proc = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=2.0)
                if proc.returncode == 0:
                    text = proc.stdout
        except Exception as e:
            logger.debug(f"Failed to read clipboard: {e}")

        if not text:
            return []

        mods = parse_urls_from_text(text)
        return [m.original_url for m in mods]
