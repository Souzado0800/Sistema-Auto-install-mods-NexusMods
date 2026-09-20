"""
View: Downloads & Installation Queue.
Live download telemetry with visual progress rows and dependency pipeline order.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.empty_state import EmptyState
from ui.desktop.components.header import SectionHeader
from ui.desktop.components.progress_row import ProgressRow
from ui.desktop.state import AppState


class DownloadsView(Gtk.ScrolledWindow):
    """Download manager and active transfer monitor."""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)

        header = SectionHeader(
            title="Downloads & Installation Queue",
            subtitle="Active network streams, local archive cache, and dependency installation sequence.",
        )
        self.main_box.append(header)

        # Active downloads list container
        self.downloads_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_box.append(self.downloads_box)

        self.set_child(self.main_box)

        # Subscribe to state changes
        self.state.subscribe("downloads", lambda _d: self._render_downloads())
        self._render_downloads()

    def _render_downloads(self) -> None:
        # Clear existing
        child = self.downloads_box.get_first_child()
        while child:
            next_ch = child.get_next_sibling()
            self.downloads_box.remove(child)
            child = next_ch

        items = list(self.state.downloads.values())
        if not items:
            empty = EmptyState(
                icon_name="folder-download-symbolic",
                title="No Active Downloads",
                description="All requested mods are installed and up to date. Open Nexus tabs in your browser to queue new downloads.",
            )
            self.downloads_box.append(empty)
            return

        for dl in items:
            row = ProgressRow(
                title=dl.name,
                initial_status=dl.status,
                total_bytes=dl.total_bytes,
            )
            row.update_progress(
                bytes_downloaded=dl.bytes_downloaded,
                total_bytes=dl.total_bytes,
                speed_bps=dl.speed_bps,
                status=dl.status,
                force=True,
            )
            self.downloads_box.append(row)
