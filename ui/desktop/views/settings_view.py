"""
View: Settings (Preferences & Live Theme Customization).
Provides full visual appearance personalization (theme, accent color, density, radius),
path configurations, and safe reset capabilities.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.button import AppButton
from ui.desktop.components.header import SectionHeader
from ui.desktop.components.toast import ToastService
from ui.desktop.state import AppState
from ui.desktop.theme.manager import ThemeManager
from ui.desktop.tokens.spacing import UIDensity


class SettingsView(Gtk.ScrolledWindow):
    """Full categorized application and appearance settings."""

    def __init__(self, state: AppState, theme_mgr: ThemeManager):
        super().__init__()
        self.state = state
        self.theme_mgr = theme_mgr
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(24)
        self.main_box.set_margin_start(24)
        self.main_box.set_margin_end(24)

        header = SectionHeader(
            title="Settings",
            subtitle="Configure desktop appearance, design tokens, paths, and automation preferences.",
        )
        self.main_box.append(header)

        # 1. Appearance & Theme Customizer
        self.main_box.append(self._build_appearance_section())

        # 2. Game & Environment
        self.main_box.append(self._build_game_section())

        # 3. Automation & Browser
        self.main_box.append(self._build_automation_section())

        # 4. Safe Reset Section
        self.main_box.append(self._build_reset_section())

        self.set_child(self.main_box)

    def _build_appearance_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="APPEARANCE & VISUAL IDENTITY")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        # Theme preset buttons
        theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_t = Gtk.Label(label="Theme Preset:")
        lbl_t.add_css_class("text-body")
        lbl_t.set_xalign(0.0)
        theme_box.append(lbl_t)

        for th in self.theme_mgr.list_available_themes():
            btn = AppButton(
                label=th.meta.name,
                variant="secondary",
                on_clicked=lambda t=th: self._select_theme(t),
            )
            theme_box.append(btn)

        card.append(theme_box)

        # UI Density
        density_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_d = Gtk.Label(label="UI Density:")
        lbl_d.add_css_class("text-body")
        lbl_d.set_xalign(0.0)
        density_box.append(lbl_d)

        btn_comf = AppButton(
            label="Comfortable",
            variant="primary" if self.theme_mgr.current_theme.density == UIDensity.COMFORTABLE else "secondary",
            on_clicked=lambda: self._set_density(UIDensity.COMFORTABLE),
        )
        btn_compact = AppButton(
            label="Compact (High Density)",
            variant="primary" if self.theme_mgr.current_theme.density == UIDensity.COMPACT else "secondary",
            on_clicked=lambda: self._set_density(UIDensity.COMPACT),
        )
        self.btn_density_comf = btn_comf
        self.btn_density_comp = btn_compact
        density_box.append(btn_comf)
        density_box.append(btn_compact)
        card.append(density_box)

        # Accent Color quick swatches
        accent_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_a = Gtk.Label(label="Accent Swatch:")
        lbl_a.add_css_class("text-body")
        lbl_a.set_xalign(0.0)
        accent_box.append(lbl_a)

        swatches = [
            ("Rally Amber", "#e58e26"),
            ("Garage Cyan", "#00d2d3"),
            ("Precision Blue", "#3498db"),
            ("Mechanic Green", "#2ecc71"),
            ("Tungsten Red", "#e74c3c"),
        ]
        for name, hex_val in swatches:
            btn_s = AppButton(
                label=name,
                variant="secondary",
                on_clicked=lambda h=hex_val: self._set_accent(h),
            )
            accent_box.append(btn_s)

        card.append(accent_box)

        # Corner Radius Slider
        rad_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_r = Gtk.Label(label="Corner Radius:")
        lbl_r.add_css_class("text-body")
        lbl_r.set_xalign(0.0)
        rad_box.append(lbl_r)

        scale_rad = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 2, 12, 1)
        scale_rad.set_value(self.theme_mgr.current_theme.corner_radius)
        scale_rad.set_hexpand(True)
        scale_rad.connect("value-changed", self._on_radius_slider_changed)
        rad_box.append(scale_rad)
        card.append(rad_box)

        return card

    def _select_theme(self, theme) -> None:
        self.theme_mgr.apply_theme(theme)
        ToastService.show(f"Theme applied: {theme.meta.name}")

    def _set_density(self, density: UIDensity) -> None:
        self.theme_mgr.set_density(density)
        self.btn_density_comf.remove_css_class("app-btn-primary" if density == UIDensity.COMPACT else "app-btn-secondary")
        self.btn_density_comf.add_css_class("app-btn-secondary" if density == UIDensity.COMPACT else "app-btn-primary")
        self.btn_density_comp.remove_css_class("app-btn-secondary" if density == UIDensity.COMPACT else "app-btn-primary")
        self.btn_density_comp.add_css_class("app-btn-primary" if density == UIDensity.COMPACT else "app-btn-secondary")
        ToastService.show(f"Density mode: {density.value.capitalize()}")

    def _set_accent(self, hex_val: str) -> None:
        self.theme_mgr.set_accent_color(hex_val)
        ToastService.show("Accent color updated.")

    def _on_radius_slider_changed(self, scale: Gtk.Scale) -> None:
        val = int(scale.get_value())
        self.theme_mgr.set_corner_radius(val)

    def _build_game_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="GAME & DIRECTORIES")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_p = Gtk.Label(label="Mods Directory:")
        lbl_p.add_css_class("text-body")
        row.append(lbl_p)

        lbl_val = Gtk.Label(label=self.state.system.mods_dir or "/home/souza/My Summer Car/Mods")
        lbl_val.add_css_class("text-mono")
        lbl_val.add_css_class("text-muted")
        lbl_val.set_xalign(0.0)
        lbl_val.set_hexpand(True)
        row.append(lbl_val)

        card.append(row)
        return card

    def _build_automation_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="AUTOMATION & BROWSER INTEGRATION")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        r1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl1 = Gtk.Label(label="Close Browser Tab After Download:")
        lbl1.add_css_class("text-body")
        lbl1.set_xalign(0.0)
        lbl1.set_hexpand(True)
        r1.append(lbl1)

        sw = Gtk.Switch()
        sw.set_active(True)
        r1.append(sw)
        card.append(r1)

        return card

    def _build_reset_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("surface-card")

        lbl_sec = Gtk.Label(label="MAINTENANCE & RESET")
        lbl_sec.add_css_class("text-caption")
        lbl_sec.add_css_class("text-muted")
        lbl_sec.set_xalign(0.0)
        card.append(lbl_sec)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_desc = Gtk.Label(label="Reset appearance preferences to factory defaults (Preserves your mods and database).")
        lbl_desc.add_css_class("text-caption")
        lbl_desc.add_css_class("text-muted")
        lbl_desc.set_xalign(0.0)
        lbl_desc.set_hexpand(True)
        row.append(lbl_desc)

        btn_reset = AppButton(
            label="Reset Appearance",
            variant="secondary",
            on_clicked=self._on_reset_appearance,
        )
        row.append(btn_reset)
        card.append(row)

        return card

    def _on_reset_appearance(self) -> None:
        default_theme = self.theme_mgr._load_default_theme()
        self.theme_mgr.apply_theme(default_theme)
        ToastService.show("Appearance reset to factory defaults.")
