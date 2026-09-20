"""
Reactive Application State.
Contains strongly typed state models and an Observer notification mechanism
to decouple UI views from domain events and background worker threads.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from collections.abc import Callable

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


class ModStatus(StrEnum):
    INSTALLED = "Installed"
    UPDATE_AVAILABLE = "Update available"
    DOWNLOADING = "Downloading"
    INSTALLING = "Installing"
    UNMANAGED = "Unmanaged"
    CACHED = "Cached"
    FAILED = "Failed"
    CONFLICT = "Conflict"


@dataclass
class ModItemState:
    """State representation of a single mod."""
    mod_id: int
    name: str
    version: str = "1.0"
    latest_version: str | None = None
    author: str = "Unknown"
    status: ModStatus = ModStatus.INSTALLED
    source: str = "Nexus"  # "Nexus", "Manual", "System"
    file_name: str = ""
    file_size_bytes: int = 0
    dependencies: list[str] = field(default_factory=list)
    required_by: list[str] = field(default_factory=list)
    installed_files: list[str] = field(default_factory=list)
    nexus_url: str | None = None
    description: str = ""

    @property
    def has_update(self) -> bool:
        return bool(self.latest_version and self.latest_version != self.version)


@dataclass
class DownloadItemState:
    """State representation of an active or queued download."""
    mod_id: int
    file_id: int
    name: str
    status: str = "Pending"  # Pending, Downloading, Cached, Completed, Failed
    bytes_downloaded: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    progress: float = 0.0    # 0.0 to 1.0
    error_message: str | None = None


@dataclass
class ActivityLogItem:
    """Human-readable timeline log item."""
    timestamp: str
    message: str
    level: str = "INFO"  # INFO, SUCCESS, WARNING, ERROR
    details: str | None = None


@dataclass
class SystemStatus:
    """System-level diagnostic status."""
    msc_detected: bool = False
    msc_loader_present: bool = False
    mods_dir: str = ""
    nexus_authenticated: bool = False
    nexus_user: str = "Guest"
    nexus_tier: str = "Free"
    browser_detected: str | None = None
    browser_tabs_count: int = 0
    engine_state: str = "Idle"  # Idle, Scanning, Downloading, Installing, Completed


class AppState:
    """Observable global state store for the desktop UI."""

    def __init__(self):
        self.system = SystemStatus()
        self.mods: dict[int, ModItemState] = {}
        self.downloads: dict[int, DownloadItemState] = {}
        self.activities: list[ActivityLogItem] = []

        # Filter & UI State
        self.search_query: str = ""
        self.selected_filter: str = "All"
        self.selected_mod_id: int | None = None

        self._subscribers: dict[str, list[Callable[[Any], None]]] = {
            "system": [],
            "mods": [],
            "downloads": [],
            "activities": [],
            "selection": [],
        }

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        """Subscribes a listener to a specific topic."""
        if topic in self._subscribers:
            self._subscribers[topic].append(callback)

    def _notify(self, topic: str, payload: Any = None) -> None:
        """Dispatches notification on the GLib main thread safely."""
        listeners = list(self._subscribers.get(topic, []))
        def _dispatch():
            for cb in listeners:
                try:
                    cb(payload)
                except Exception:
                    pass
            return False
        GLib.idle_add(_dispatch)

    def update_system_status(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self.system, k):
                setattr(self.system, k, v)
        self._notify("system", self.system)

    def set_mods(self, mod_list: list[ModItemState]) -> None:
        self.mods = {m.mod_id: m for m in mod_list}
        self._notify("mods", self.mods)

    def upsert_mod(self, mod: ModItemState) -> None:
        self.mods[mod.mod_id] = mod
        self._notify("mods", self.mods)

    def set_downloads(self, download_list: list[DownloadItemState]) -> None:
        self.downloads = {d.mod_id: d for d in download_list}
        self._notify("downloads", self.downloads)

    def update_download_progress(
        self,
        mod_id: int,
        bytes_downloaded: int,
        total_bytes: int,
        speed_bps: float = 0.0,
        status: str = "Downloading",
    ) -> None:
        if mod_id in self.downloads:
            d = self.downloads[mod_id]
            d.bytes_downloaded = bytes_downloaded
            d.total_bytes = total_bytes
            d.speed_bps = speed_bps
            d.status = status
            d.progress = bytes_downloaded / max(1, total_bytes)
            self._notify("downloads", self.downloads)

    def add_activity(self, message: str, level: str = "INFO", details: str | None = None) -> None:
        ts = time.strftime("%H:%M:%S")
        item = ActivityLogItem(timestamp=ts, message=message, level=level, details=details)
        self.activities.insert(0, item)
        # Keep maximum 200 items in memory
        if len(self.activities) > 200:
            self.activities.pop()
        self._notify("activities", self.activities)

    def select_mod(self, mod_id: int | None) -> None:
        self.selected_mod_id = mod_id
        self._notify("selection", mod_id)

    def get_filtered_mods(self) -> list[ModItemState]:
        """Returns mods matching current search query and status filter."""
        items = list(self.mods.values())
        query = self.search_query.strip().lower()

        if query:
            items = [
                m for m in items
                if query in m.name.lower() or query in str(m.mod_id) or query in m.author.lower()
            ]

        if self.selected_filter == "Installed":
            items = [m for m in items if m.status == ModStatus.INSTALLED]
        elif self.selected_filter == "Updates":
            items = [m for m in items if m.status == ModStatus.UPDATE_AVAILABLE]
        elif self.selected_filter == "Unmanaged":
            items = [m for m in items if m.status == ModStatus.UNMANAGED]
        elif self.selected_filter == "Failed":
            items = [m for m in items if m.status == ModStatus.FAILED]

        return items
