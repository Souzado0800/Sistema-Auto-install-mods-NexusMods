"""
View: Component Preview (Storybook-like component testbed).
Displays all design tokens, components, badges, buttons, progress rows,
and interactive controls for visual QA and design validation.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.badge import StatusBadge
from ui.desktop.components.button import AppButton, IconButton
from ui.desktop.components.empty_state import EmptyState
from ui.desktop.components.header import SectionHeader
from ui.desktop.components.mod_row import ModRow
from ui.desktop.components.progress_row import ProgressRow
from ui.desktop.components.search_field import SearchField
from ui.desktop.state import ModItemState, ModStatus
from ui.desktop.theme.manager import ThemeManager
from ui.desktop.tokens.spacing import UIDensity


class ComponentPreviewView(Gtk.ScrolledWindow):
    """Interactive component gallery for UI design review."""

    def __init__(self, theme_mgr: ThemeManager):
        super().__init__()
        self.theme_mgr = theme_mgr
        self.set_hexpand(True)
        self.set_vexpand(True)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)

        # Header with live theme switcher controls
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        for theme in self.theme_mgr.list_available_themes():
            btn = AppButton(
                label=theme.meta.name,
                variant="secondary",
                on_clicked=lambda t=theme: self.theme_mgr.apply_theme(t),
            )
            ctrl_box.append(btn)

        btn_density = AppButton(
            label="Toggle Density",
            variant="secondary",
            on_clicked=self._toggle_density,
        )
        ctrl_box.append(btn_density)

        header = SectionHeader(
            title="Design System & Component Gallery",
            subtitle="Live validation of tokens, typography, geometric density, and component states.",
            action_widget=ctrl_box,
        )
        main_box.append(header)

        # 1. Typography Scale
        main_box.append(self._build_typography_section())

        # 2. Status Badges
        main_box.append(self._build_badges_section())

        # 3. Action Buttons
        main_box.append(self._build_buttons_section())

        # 4. Search & Inputs
        main_box.append(self._build_inputs_section())

        # 5. Progress Rows
        main_box.append(self._build_progress_section())

        # 6. Mod Rows (High Density)
        main_box.append(self._build_mod_rows_section())

        # 7. Empty State
        main_box.append(self._build_empty_state_section())

        self.set_child(main_box)

    def _toggle_density(self) -> None:
        cur = self.theme_mgr.current_theme.density
        new_d = UIDensity.COMPACT if cur == UIDensity.COMFORTABLE else UIDensity.COMFORTABLE
        self.theme_mgr.set_density(new_d)

    def _build_typography_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="TYPOGRAPHY SCALE")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        samples = [
            ("Display (18pt / Semibold)", "text-display", "My Summer Car Mod Manager"),
            ("Heading (14pt / Semibold)", "text-heading", "Lights On Switches v2.0.1"),
            ("Body (13pt / Regular)", "text-body", "Automated installation pipeline with dependency sorting."),
            ("Caption (11pt / Medium)", "text-caption", "Uploaded 2026-09-20 · 48.3 KB · SHA-256 Validated"),
            ("Monospace (12pt)", "text-mono", "/home/souza/My Summer Car/Mods/LightsOnSwitches.dll"),
        ]

        for desc, cls_name, text in samples:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            lbl_desc = Gtk.Label(label=desc)
            lbl_desc.set_size_request(220, -1)
            lbl_desc.set_xalign(0.0)
            lbl_desc.add_css_class("text-caption")
            lbl_desc.add_css_class("text-muted")
            row.append(lbl_desc)

            lbl_val = Gtk.Label(label=text)
            lbl_val.add_css_class(cls_name)
            lbl_val.set_xalign(0.0)
            row.append(lbl_val)
            card.append(row)

        return card

    def _build_badges_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="STATUS BADGES (ICON + LABEL + COLOR)")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        badge_box.append(StatusBadge(ModStatus.INSTALLED))
        badge_box.append(StatusBadge(ModStatus.UPDATE_AVAILABLE))
        badge_box.append(StatusBadge(ModStatus.UNMANAGED))
        badge_box.append(StatusBadge(ModStatus.DOWNLOADING))
        badge_box.append(StatusBadge(ModStatus.FAILED))
        badge_box.append(StatusBadge(ModStatus.CONFLICT))
        badge_box.append(StatusBadge(ModStatus.CACHED))

        card.append(badge_box)
        return card

    def _build_buttons_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="BUTTON VARIANTS")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.append(AppButton(label="Install All Mods", variant="primary", icon_name="emblem-ok-symbolic"))
        btn_box.append(AppButton(label="Scan Nexus Tabs", variant="secondary", icon_name="edit-find-symbolic"))
        btn_box.append(AppButton(label="Flat Action", variant="flat", icon_name="view-refresh-symbolic"))
        btn_box.append(AppButton(label="Remove Mod", variant="danger", icon_name="user-trash-symbolic"))
        btn_box.append(IconButton(icon_name="emblem-system-symbolic", tooltip="Settings"))
        btn_box.append(IconButton(icon_name="view-refresh-symbolic", tooltip="Reload", flat=False))

        card.append(btn_box)
        return card

    def _build_inputs_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="DEBOUNCED SEARCH & FORM CONTROLS")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        search = SearchField(placeholder="Filter by mod name, author, or ID...")
        search.set_hexpand(True)
        box.append(search)

        card.append(box)
        return card

    def _build_progress_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="THROTTLED PROGRESS ROWS")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        row1 = ProgressRow(title="Fifth Gear - Animated v0.7.2", initial_status="Downloading", total_bytes=248000)
        row1.update_progress(bytes_downloaded=186000, total_bytes=248000, speed_bps=1200000, status="Downloading", force=True)
        card.append(row1)

        row2 = ProgressRow(title="Tangerine FZ-120 Pickup v1.2.0", initial_status="Installing", total_bytes=15840000)
        row2.update_progress(bytes_downloaded=15840000, total_bytes=15840000, speed_bps=0, status="Installing", force=True)
        card.append(row2)

        return card

    def _build_mod_rows_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("mod-table")

        # Table header
        th = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        th.add_css_class("mod-table-header")

        lbl_name = Gtk.Label(label="NAME")
        lbl_name.set_xalign(0.0)
        lbl_name.set_hexpand(True)
        th.append(lbl_name)

        lbl_ver = Gtk.Label(label="VERSION")
        lbl_ver.set_size_request(90, -1)
        lbl_ver.set_xalign(0.0)
        th.append(lbl_ver)

        lbl_src = Gtk.Label(label="SOURCE")
        lbl_src.set_size_request(80, -1)
        lbl_src.set_xalign(0.0)
        th.append(lbl_src)

        lbl_st = Gtk.Label(label="STATUS")
        lbl_st.set_size_request(130, -1)
        lbl_st.set_xalign(1.0)
        th.append(lbl_st)

        card.append(th)

        # Sample rows
        m1 = ModItemState(mod_id=868, name="Lights On Switches", version="2.0.1", author="Spirithaven", status=ModStatus.INSTALLED)
        m2 = ModItemState(mod_id=221, name="Fifth Gear - Animated", version="0.6.0", latest_version="0.7.2", author="tommojphillips", status=ModStatus.UPDATE_AVAILABLE)
        m3 = ModItemState(mod_id=9901, name="Custom Stereo Cassettes", version="1.0.0", author="Local Workshop", status=ModStatus.UNMANAGED, source="Manual")

        card.append(ModRow(m1))
        card.append(ModRow(m2))
        card.append(ModRow(m3))

        return card

    def _build_empty_state_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("surface-card")

        empty = EmptyState(
            icon_name="view-refresh-symbolic",
            title="No Nexus Mod Pages Detected",
            description="Open your desired mod pages in Brave or Chrome. They will appear here automatically ready to install.",
            action_label="Scan Open Tabs",
            on_action=lambda: None,
        )
        card.append(empty)
        return card
