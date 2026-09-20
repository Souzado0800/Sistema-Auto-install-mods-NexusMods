"""
View: Activity Timeline.
Clean human-readable event log, keeping raw technical logs separate.
"""

from __future__ import annotations

import os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.button import AppButton
from ui.desktop.components.empty_state import EmptyState
from ui.desktop.components.header import SectionHeader
from ui.desktop.state import AppState


class ActivityView(Gtk.ScrolledWindow):
    """Clean human activity timeline."""

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

        btn_log = AppButton(
            label="Open Technical Log",
            variant="secondary",
            icon_name="text-x-generic-symbolic",
            on_clicked=self._open_log_file,
        )

        header = SectionHeader(
            title="Activity Timeline",
            subtitle="Human-readable log of mod installations, scans, and system verifications.",
            action_widget=btn_log,
        )
        self.main_box.append(header)

        # Scrolled card
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.card.add_css_class("surface-card")
        self.main_box.append(self.card)

        self.set_child(self.main_box)

        # Subscribe to state changes
        self.state.subscribe("activities", lambda _a: self._render_activities())
        self._render_activities()

    def _render_activities(self) -> None:
        child = self.card.get_first_child()
        while child:
            next_ch = child.get_next_sibling()
            self.card.remove(child)
            child = next_ch

        if not self.state.activities:
            empty = EmptyState(
                icon_name="document-properties-symbolic",
                title="No Events Recorded",
                description="Activity records will appear here as mods are scanned, downloaded, and installed.",
            )
            self.card.append(empty)
            return

        for item in self.state.activities:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
            row.set_margin_top(4)
            row.set_margin_bottom(4)

            lbl_ts = Gtk.Label(label=item.timestamp)
            lbl_ts.add_css_class("text-caption")
            lbl_ts.add_css_class("text-mono")
            lbl_ts.add_css_class("text-muted")
            lbl_ts.set_xalign(0.0)
            row.append(lbl_ts)

            # Dot indicator based on level
            dot = Gtk.Label(label="●")
            if item.level == "SUCCESS":
                dot.add_css_class("status-dot-green")
            elif item.level == "WARNING":
                dot.add_css_class("status-dot-amber")
            elif item.level == "ERROR":
                dot.add_css_class("badge-failed")
            else:
                dot.add_css_class("status-dot-gray")
            row.append(dot)

            lbl_msg = Gtk.Label(label=item.message)
            lbl_msg.add_css_class("text-body")
            lbl_msg.set_xalign(0.0)
            lbl_msg.set_hexpand(True)
            lbl_msg.set_wrap(True)
            row.append(lbl_msg)

            self.card.append(row)

    def _open_log_file(self) -> None:
        log_path = Path("data/logs/installer.log")
        if log_path.exists():
            os.system(f"xdg-open '{log_path.resolve()}' &")
