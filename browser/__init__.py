"""Browser automation and input collection package."""

from .cdp import CdpTabCollector
from .collector import ModCollector
from .manual import parse_urls_from_file, parse_urls_from_text
from .normalizer import CanonicalModKey, NormalizedModUrl, normalize_nexus_url
from .auto_downloader import BrowserDownloadAutomator
from .cdp_client import CdpClient
from .download_watcher import DownloadWatcher
from .sources import (
    AutoBrowserSource,
    BrowserSessionSource,
    BrowserTabsSource,
    ClipboardSource,
    ManualURLSource,
    ModSource,
    TextFileSource,
)

__all__ = [
    "CanonicalModKey",
    "NormalizedModUrl",
    "normalize_nexus_url",
    "parse_urls_from_file",
    "parse_urls_from_text",
    "CdpTabCollector",
    "ModCollector",
    "ModSource",
    "TextFileSource",
    "ManualURLSource",
    "BrowserTabsSource",
    "BrowserSessionSource",
    "AutoBrowserSource",
    "ClipboardSource",
    "BrowserDownloadAutomator",
    "DownloadWatcher",
    "CdpClient",
]
