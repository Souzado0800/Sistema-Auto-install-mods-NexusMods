"""
Read-only Chromium/Brave session tab parser for Linux desktop environments.
Implements structural SNSS command parsing and origin confidence scoring.
"""

import logging
import re
import struct
import time
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

import psutil

from browser.normalizer import NormalizedModUrl, normalize_nexus_url

logger = logging.getLogger(__name__)


class TabOrigin(StrEnum):
    LIVE_CDP = "LIVE_CDP"
    ACTIVE_SESSION = "ACTIVE_SESSION"
    RECOVERED_SESSION = "RECOVERED_SESSION"
    TEXT_FILE = "TEXT_FILE"
    MANUAL = "MANUAL"


KNOWN_BROWSER_PATHS = [
    ("Brave", Path.home() / ".config" / "BraveSoftware" / "Brave-Browser"),
    ("Google Chrome", Path.home() / ".config" / "google-chrome"),
    ("Chromium", Path.home() / ".config" / "chromium"),
    ("Brave (Flatpak)", Path.home() / ".var" / "app" / "com.brave.Browser" / "config" / "BraveSoftware" / "Brave-Browser"),
    ("Chrome (Flatpak)", Path.home() / ".var" / "app" / "com.google.Chrome" / "config" / "google-chrome"),
]

NEXUS_URL_REGEX = re.compile(
    rb"https?://(?:www\.)?nexusmods\.com/[a-zA-Z0-9_\-]+/mods/\d+[a-zA-Z0-9_\-\./\?\=\&\%\+]*",
    re.IGNORECASE,
)


class ExtractedTabReport(NamedTuple):
    browser_name: str
    session_file: Path
    total_nexus_urls: int
    unique_mods: list[NormalizedModUrl]
    origin: TabOrigin = TabOrigin.ACTIVE_SESSION


class ChromiumSessionReader:
    """Safely extracts open Nexus Mods tabs from browser session files in read-only mode."""

    @classmethod
    def detect_available_browsers(cls) -> list[tuple[str, Path]]:
        """Returns list of (browser_name, user_data_dir) that exist on disk."""
        found = []
        for name, path in KNOWN_BROWSER_PATHS:
            if path.is_dir():
                found.append((name, path))
        return found

    @classmethod
    def is_browser_running(cls, browser_name: str) -> bool:
        """Checks if a browser process is currently active."""
        name_lower = browser_name.lower().split()[0]
        try:
            for proc in psutil.process_iter(attrs=["name"]):
                pname = (proc.info["name"] or "").lower()
                if name_lower in pname:
                    return True
        except Exception:
            pass
        return False

    @classmethod
    def parse_snss_open_tabs(cls, data: bytes) -> dict[int, str]:
        """
        Parses Chromium SNSS binary format to track strictly open tabs.
        Commands:
          0: kCommandSetTabWindow (tab_id, window_id)
          3: kCommandTabClosed (tab_id)
          4: kCommandWindowClosed (window_id)
          6: kCommandUpdateTabNavigation (tab_id, ...)
        """
        if len(data) < 8 or data[:4] != b"SNSS":
            return {}

        tab_urls: dict[int, str] = {}
        tab_to_win: dict[int, int] = {}
        win_to_tabs: dict[int, set[int]] = {}

        offset = 8
        data_len = len(data)

        while offset + 3 <= data_len:
            try:
                size = struct.unpack("<H", data[offset : offset + 2])[0]
                cmd_id = data[offset + 2]
                payload = data[offset + 3 : offset + 2 + size]
                offset += 2 + size

                if cmd_id == 0 and len(payload) >= 8:
                    # SetTabWindow: tab_id (int32), win_id (int32)
                    tab_id, win_id = struct.unpack("<ii", payload[:8])
                    tab_to_win[tab_id] = win_id
                    win_to_tabs.setdefault(win_id, set()).add(tab_id)

                elif cmd_id == 3 and len(payload) >= 4:
                    # TabClosed: tab_id (int32)
                    tab_id = struct.unpack("<i", payload[:4])[0]
                    tab_urls.pop(tab_id, None)
                    if tab_id in tab_to_win:
                        win_id = tab_to_win.pop(tab_id)
                        if win_id in win_to_tabs:
                            win_to_tabs[win_id].discard(tab_id)

                elif cmd_id == 4 and len(payload) >= 4:
                    # WindowClosed: win_id (int32)
                    win_id = struct.unpack("<i", payload[:4])[0]
                    closed_tabs = win_to_tabs.pop(win_id, set())
                    for tid in closed_tabs:
                        tab_urls.pop(tid, None)
                        tab_to_win.pop(tid, None)

                elif cmd_id == 6 and len(payload) >= 4:
                    # UpdateTabNavigation: tab_id (int32)
                    tab_id = struct.unpack("<i", payload[:4])[0]
                    matches = NEXUS_URL_REGEX.findall(payload)
                    if matches:
                        try:
                            # Use the last clean Nexus URL found in navigation entry
                            url_str = matches[-1].decode("utf-8", errors="ignore").rstrip(".,;:)\"'<>")
                            tab_urls[tab_id] = url_str
                        except Exception:
                            pass

            except Exception:
                break

        return tab_urls

    @classmethod
    def extract_nexus_tabs(
        cls,
        target_game: str | None = "mysummercar",
        custom_browser_dir: Path | None = None,
    ) -> ExtractedTabReport | None:
        """
        Scans browser session files and extracts unique mod URLs for target_game.
        Distinguishes active open tabs from recovered/closed tabs.
        """
        browser_targets = []
        if custom_browser_dir and custom_browser_dir.is_dir():
            browser_targets.append(("Custom", custom_browser_dir))
        else:
            browser_targets = cls.detect_available_browsers()

        if not browser_targets:
            logger.debug("No Chromium-based browsers detected.")
            return None

        best_report: ExtractedTabReport | None = None

        for browser_name, base_dir in browser_targets:
            profile_dirs = [base_dir / "Default"] + list(base_dir.glob("Profile *"))

            for profile in profile_dirs:
                sessions_dir = profile / "Sessions"
                if not sessions_dir.is_dir():
                    continue

                session_files = list(sessions_dir.glob("Session_*"))
                if not session_files:
                    continue

                latest_session = max(session_files, key=lambda f: f.stat().st_mtime)

                try:
                    data = latest_session.read_bytes()
                except Exception as e:
                    logger.debug("Could not read %s: %s", latest_session, e)
                    continue

                # 1. Attempt structured SNSS command parsing
                open_tab_urls = cls.parse_snss_open_tabs(data)

                if open_tab_urls:
                    url_candidates = list(open_tab_urls.values())
                    total_urls = len(url_candidates)
                else:
                    # Fallback to byte stream scan if SNSS structure is unusual
                    raw_matches = NEXUS_URL_REGEX.findall(data)
                    url_candidates = [
                        r.decode("utf-8", errors="ignore").rstrip(".,;:)\"'<>")
                        for r in raw_matches
                    ]
                    total_urls = len(url_candidates)

                seen_mods: dict[int, NormalizedModUrl] = {}
                for u in url_candidates:
                    try:
                        norm = normalize_nexus_url(u)
                        if norm:
                            if target_game and norm.game_domain != target_game.lower():
                                continue
                            if norm.mod_id not in seen_mods:
                                seen_mods[norm.mod_id] = norm
                    except Exception:
                        continue

                if seen_mods:
                    # Determine origin confidence
                    is_running = cls.is_browser_running(browser_name)
                    file_age_seconds = time.time() - latest_session.stat().st_mtime
                    if is_running and file_age_seconds < 1800:  # < 30 mins
                        origin = TabOrigin.ACTIVE_SESSION
                    else:
                        origin = TabOrigin.RECOVERED_SESSION

                    report = ExtractedTabReport(
                        browser_name=browser_name,
                        session_file=latest_session,
                        total_nexus_urls=total_urls,
                        unique_mods=list(seen_mods.values()),
                        origin=origin,
                    )
                    if not best_report or len(report.unique_mods) > len(best_report.unique_mods):
                        best_report = report

        return best_report
