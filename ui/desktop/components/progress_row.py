"""
Component: ProgressRow.
Visual download and installation progress row with visual throttling
to prevent UI redraw stalls during high-speed transfers.
"""

from __future__ import annotations

import time

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.badge import StatusBadge


def _format_bytes(num_bytes: int) -> str:
    """Formats bytes to clean KB / MB / GB."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class ProgressRow(Gtk.Box):
    """Row displaying download or installation status and throttled progress."""

    def __init__(
        self,
        title: str,
        initial_status: str = "Pending",
        total_bytes: int = 0,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("surface-card")
        self.set_margin_bottom(6)

        self._last_update_ts = 0.0
        self._total_bytes = total_bytes

        # Top line: Title + Status Badge
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_box.set_hexpand(True)

        self.lbl_title = Gtk.Label(label=title)
        self.lbl_title.add_css_class("text-heading")
        self.lbl_title.set_xalign(0.0)
        self.lbl_title.set_hexpand(True)
        top_box.append(self.lbl_title)

        self.badge_box = Gtk.Box()
        self.set_status(initial_status)
        top_box.append(self.badge_box)

        self.append(top_box)

        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(0.0)
        self.append(self.progress_bar)

        # Bottom info line: Progress text (e.g. 1.2 MB / 4.5 MB - 84%) + Speed
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_box.set_hexpand(True)

        self.lbl_progress = Gtk.Label(label="Queued")
        self.lbl_progress.add_css_class("text-caption")
        self.lbl_progress.add_css_class("text-muted")
        self.lbl_progress.set_xalign(0.0)
        self.lbl_progress.set_hexpand(True)
        bottom_box.append(self.lbl_progress)

        self.lbl_speed = Gtk.Label(label="")
        self.lbl_speed.add_css_class("text-caption")
        self.lbl_speed.add_css_class("text-mono")
        self.lbl_speed.set_xalign(1.0)
        bottom_box.append(self.lbl_speed)

        self.append(bottom_box)

    def set_status(self, status: str) -> None:
        """Replaces the status badge."""
        child = self.badge_box.get_first_child()
        if child:
            self.badge_box.remove(child)
        self.badge_box.append(StatusBadge(status))

    def update_progress(
        self,
        bytes_downloaded: int,
        total_bytes: int,
        speed_bps: float = 0.0,
        status: str = "Downloading",
        force: bool = False,
    ) -> None:
        """Throttled progress update (max 10 updates per second unless forced)."""
        now = time.time()
        if not force and (now - self._last_update_ts) < 0.1:
            return
        self._last_update_ts = now

        pct = bytes_downloaded / max(1, total_bytes)
        self.progress_bar.set_fraction(min(1.0, max(0.0, pct)))

        str_done = _format_bytes(bytes_downloaded)
        str_total = _format_bytes(total_bytes) if total_bytes > 0 else "Unknown size"
        self.lbl_progress.set_text(f"{str_done} / {str_total} ({int(pct * 100)}%)")

        if speed_bps > 0:
            self.lbl_speed.set_text(f"{_format_bytes(int(speed_bps))}/s")
        else:
            self.lbl_speed.set_text("")

        self.set_status(status)
