"""
View: Dashboard (Home).
Displays high-level system diagnostics, game & loader detection,
open browser tabs count, and the primary installation action.
"""

from __future__ import annotations

from collections.abc import Callable

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.button import AppButton
from ui.desktop.components.header import SectionHeader
from ui.desktop.state import AppState


class DashboardView(Gtk.ScrolledWindow):
    """Home dashboard screen."""

    def __init__(
        self,
        state: AppState,
        on_scan_clicked: Callable[[], None] | None = None,
        on_install_clicked: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.state = state
        self.on_scan_clicked = on_scan_clicked
        self.on_install_clicked = on_install_clicked

        self.set_hexpand(True)
        self.set_vexpand(True)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.main_box.set_margin_top(24)
        self.main_box.set_margin_bottom(24)
        self.main_box.set_margin_start(24)
        self.main_box.set_margin_end(24)

        # 1. Header
        header = SectionHeader(
            title="Dashboard",
            subtitle="My Summer Car mod status, browser session telemetry, and execution pipeline.",
        )
        self.main_box.append(header)

        # 2. Hero Action Banner
        self.banner_card = self._build_hero_card()
        self.main_box.append(self.banner_card)

        # 3. System Diagnostics Grid
        self.diag_grid = self._build_diagnostics_grid()
        self.main_box.append(self.diag_grid)

        # 4. Recent Activity
        self.activity_box = self._build_activity_card()
        self.main_box.append(self.activity_box)

        self.set_child(self.main_box)

        # Subscribe to state changes
        self.state.subscribe("system", lambda _s: self._refresh())
        self.state.subscribe("mods", lambda _m: self._refresh())

    def _build_hero_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        card.add_css_class("surface-card")
        card.set_margin_top(4)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_hexpand(True)

        lbl_title = Gtk.Label(label="Autonomous Mod Pipeline")
        lbl_title.add_css_class("text-heading")
        lbl_title.set_xalign(0.0)
        vbox.append(lbl_title)

        self.lbl_pipeline_desc = Gtk.Label(
            label="Open your desired mod pages in Brave or Chrome. Click Install to download and configure everything automatically."
        )
        self.lbl_pipeline_desc.add_css_class("text-body")
        self.lbl_pipeline_desc.add_css_class("text-muted")
        self.lbl_pipeline_desc.set_xalign(0.0)
        self.lbl_pipeline_desc.set_wrap(True)
        vbox.append(self.lbl_pipeline_desc)

        card.append(vbox)

        # Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_valign(Gtk.Align.CENTER)

        self.btn_scan = AppButton(
            label="Scan Nexus Tabs",
            variant="secondary",
            icon_name="edit-find-symbolic",
            on_clicked=self._on_scan,
        )
        btn_box.append(self.btn_scan)

        self.btn_install = AppButton(
            label="Install Detected Mods",
            variant="primary",
            icon_name="emblem-ok-symbolic",
            on_clicked=self._on_install,
        )
        btn_box.append(self.btn_install)

        card.append(btn_box)
        return card

    def _build_diagnostics_grid(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        box.set_hexpand(True)

        self.card_game = self._create_metric_card("GAME ENVIRONMENT", "My Summer Car", "Detected (/home/souza/.../Mods)", "emblem-ok-symbolic")
        self.card_loader = self._create_metric_card("MOD LOADER", "MSCLoader", "Ready & Operational", "emblem-ok-symbolic")
        self.card_nexus = self._create_metric_card("NEXUS ACCOUNT", "Matheushopi", "Supporter Tier (Active)", "emblem-ok-symbolic")
        self.card_mods = self._create_metric_card("INSTALLED MODS", f"{len(self.state.mods)} Mods", "All dependencies satisfied", "package-x-generic-symbolic")

        box.append(self.card_game)
        box.append(self.card_loader)
        box.append(self.card_nexus)
        box.append(self.card_mods)

        return box

    def _create_metric_card(self, category: str, primary: str, secondary: str, icon_name: str) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("surface-card")
        card.set_hexpand(True)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_cat = Gtk.Label(label=category)
        lbl_cat.add_css_class("text-caption")
        lbl_cat.add_css_class("text-muted")
        lbl_cat.set_xalign(0.0)
        lbl_cat.set_hexpand(True)
        top.append(lbl_cat)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(12)
        top.append(icon)
        card.append(top)

        lbl_pri = Gtk.Label(label=primary)
        lbl_pri.add_css_class("text-heading")
        lbl_pri.set_xalign(0.0)
        card.append(lbl_pri)

        lbl_sec = Gtk.Label(label=secondary)
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        lbl_sec.set_ellipsize(3)
        card.append(lbl_sec)

        return card

    def _build_activity_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("surface-card")

        lbl_title = Gtk.Label(label="RECENT ACTIVITY")
        lbl_title.add_css_class("text-caption")
        lbl_title.add_css_class("text-muted")
        lbl_title.set_xalign(0.0)
        card.append(lbl_title)

        self.activity_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.append(self.activity_rows)
        self._refresh_activity()

        return card

    def _refresh_activity(self) -> None:
        child = self.activity_rows.get_first_child()
        while child:
            next_ch = child.get_next_sibling()
            self.activity_rows.remove(child)
            child = next_ch

        for item in self.state.activities[:5]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            lbl_ts = Gtk.Label(label=item.timestamp)
            lbl_ts.add_css_class("text-caption")
            lbl_ts.add_css_class("text-mono")
            lbl_ts.add_css_class("text-muted")
            lbl_ts.set_xalign(0.0)
            row.append(lbl_ts)

            lbl_msg = Gtk.Label(label=item.message)
            lbl_msg.add_css_class("text-body")
            lbl_msg.set_xalign(0.0)
            lbl_msg.set_hexpand(True)
            row.append(lbl_msg)

            self.activity_rows.append(row)

    def _refresh(self) -> None:
        self._refresh_activity()

    def _on_scan(self) -> None:
        if self.on_scan_clicked:
            self.on_scan_clicked()

    def _on_install(self) -> None:
        if self.on_install_clicked:
            self.on_install_clicked()
