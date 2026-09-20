"""
Theme Manager: dynamic compilation of tokens into GTK 4 CSS and runtime application.
Provides live stylesheet re-injection without application restart.
"""

from __future__ import annotations

import logging
from pathlib import Path
from collections.abc import Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from ui.desktop.theme.schema import ThemeDefinition
from ui.desktop.tokens.colors import _hex_to_rgb
from ui.desktop.tokens.spacing import COMFORTABLE_METRICS, COMPACT_METRICS, UIDensity
from ui.desktop.tokens.typography import TypographyTokens

logger = logging.getLogger(__name__)


class ThemeManager:
    """Central manager for desktop styling, theme loading, and live CSS generation."""

    def __init__(
        self,
        presets_dir: Path | None = None,
        user_themes_dir: Path | None = None,
    ):
        self.presets_dir = presets_dir or Path(__file__).parent / "presets"
        self.user_themes_dir = user_themes_dir or Path.home() / ".config" / "AutoInstallModMySummerCar" / "themes"
        self.user_themes_dir.mkdir(parents=True, exist_ok=True)

        self._current_theme: ThemeDefinition = self._load_default_theme()
        self._css_provider: Gtk.CssProvider | None = None
        self._listeners: list[Callable[[ThemeDefinition], None]] = []

    def _load_default_theme(self) -> ThemeDefinition:
        """Loads the default Garage Dark preset or falls back to built-in tokens."""
        default_preset = self.presets_dir / "garage_dark.json"
        if default_preset.exists():
            try:
                return ThemeDefinition.load_from_file(default_preset)
            except Exception as e:
                logger.warning(f"Failed to load garage_dark preset: {e}")
        return ThemeDefinition.from_dict({
            "meta": {"id": "garage-dark", "name": "Garage Dark", "is_dark": True, "is_builtin": True}
        })

    @property
    def current_theme(self) -> ThemeDefinition:
        return self._current_theme

    def list_available_themes(self) -> list[ThemeDefinition]:
        """Returns all built-in presets and user-created custom themes."""
        themes: dict[str, ThemeDefinition] = {}

        # 1. Built-in presets
        if self.presets_dir.exists():
            for p in sorted(self.presets_dir.glob("*.json")):
                try:
                    t = ThemeDefinition.load_from_file(p)
                    themes[t.meta.id] = t
                except Exception as e:
                    logger.warning(f"Error loading preset {p.name}: {e}")

        # 2. User themes (can override presets by ID)
        if self.user_themes_dir.exists():
            for p in sorted(self.user_themes_dir.glob("*.json")):
                try:
                    t = ThemeDefinition.load_from_file(p)
                    themes[t.meta.id] = t
                except Exception as e:
                    logger.warning(f"Error loading user theme {p.name}: {e}")

        return list(themes.values())

    def apply_theme(self, theme: ThemeDefinition) -> None:
        """Sets the active theme, compiles CSS, and updates the display context."""
        self._current_theme = theme
        css_string = self.compile_css(theme)

        display = Gdk.Display.get_default()
        if display is not None:
            if self._css_provider is None:
                self._css_provider = Gtk.CssProvider()
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            self._css_provider.load_from_string(css_string)

            # Sync Libadwaita color scheme
            style_mgr = Adw.StyleManager.get_default()
            if style_mgr:
                style_mgr.set_color_scheme(
                    Adw.ColorScheme.FORCE_DARK if theme.meta.is_dark else Adw.ColorScheme.FORCE_LIGHT
                )

        logger.info(f"Theme '{theme.meta.name}' applied successfully.")
        for listener in self._listeners:
            try:
                listener(theme)
            except Exception as e:
                logger.error(f"Error notifying theme listener: {e}")

    def add_theme_changed_listener(self, callback: Callable[[ThemeDefinition], None]) -> None:
        """Registers a callback invoked whenever the theme changes."""
        self._listeners.append(callback)

    def set_density(self, density: UIDensity) -> None:
        """Updates density mode and reapplies CSS live."""
        self._current_theme.density = density
        self.apply_theme(self._current_theme)

    def set_accent_color(self, accent_hex: str) -> None:
        """Updates accent color and derives interactive shades live."""
        self._current_theme.colors.accent = accent_hex
        self.apply_theme(self._current_theme)

    def set_corner_radius(self, radius: int) -> None:
        """Updates corner radius live."""
        self._current_theme.corner_radius = radius
        self.apply_theme(self._current_theme)

    def compile_css(self, theme: ThemeDefinition) -> str:
        """Compiles a complete ThemeDefinition into clean, valid GTK 4 CSS."""
        c = theme.colors
        shades = c.get_accent_shades()
        metrics = COMPACT_METRICS if theme.density == UIDensity.COMPACT else COMFORTABLE_METRICS
        rad = theme.corner_radius
        typo = TypographyTokens(scale_factor=theme.font_scale)

        def _rgb_vals(hex_c: str) -> str:
            r, g, b = _hex_to_rgb(hex_c)
            return f"{int(r * 255)}, {int(g * 255)}, {int(b * 255)}"

        inst_rgb = _rgb_vals(c.semantic.installed)
        upd_rgb = _rgb_vals(c.semantic.update_available)
        unm_rgb = _rgb_vals(c.semantic.unmanaged)
        fail_rgb = _rgb_vals(c.semantic.failed)
        neut_rgb = _rgb_vals(c.semantic.neutral)
        down_rgb = _rgb_vals(c.semantic.active_download)

        css = f"""
        /* AutoInstallModMySummerCar - Compiled Dynamic Theme: {theme.meta.name} */

        window, .background {{
            background-color: {c.background};
            color: {c.text_primary};
            font-family: {typo.font_sans};
            font-size: {int(typo.body.size_pt * typo.scale_factor)}pt;
        }}

        /* Headerbar & Navigation Split */
        headerbar, .adw-header-bar {{
            background-color: {c.surface};
            border-bottom: 1px solid {c.border};
            color: {c.text_primary};
            box-shadow: none;
            padding: 2px 6px;
        }}

        .navigation-sidebar, .sidebar {{
            background-color: {c.surface};
            border-right: 1px solid {c.border};
            padding: 8px 6px;
        }}

        /* Sidebar Navigation Items */
        .sidebar-item {{
            padding: {metrics.row_padding_v}px {metrics.row_padding_h}px;
            border-radius: {rad}px;
            color: {c.text_secondary};
            font-weight: 500;
            margin: 2px 0px;
            border: 1px solid transparent;
            transition: all 120ms ease;
        }}

        .sidebar-item:hover {{
            background-color: {c.surface_hover};
            color: {c.text_primary};
        }}

        .sidebar-item:active, .sidebar-item.active, .sidebar-item:selected {{
            background-color: {c.surface_raised};
            color: {c.text_primary};
            border-left: 3px solid {shades.base};
            font-weight: 600;
        }}

        /* Surface Containers & Cards */
        .surface-card {{
            background-color: {c.surface};
            border: 1px solid {c.border};
            border-radius: {rad}px;
            padding: 12px;
        }}

        .surface-raised {{
            background-color: {c.surface_raised};
            border: 1px solid {c.border_subtle};
            border-radius: {rad}px;
        }}

        /* Buttons */
        .app-btn {{
            font-size: {int(typo.body.size_pt * typo.scale_factor)}pt;
            min-height: {metrics.button_height}px;
            padding: {metrics.row_padding_v}px {metrics.row_padding_h}px;
            border-radius: {rad}px;
            font-weight: 500;
            transition: all 120ms ease;
        }}

        .app-btn-primary {{
            background-color: {shades.base};
            color: {shades.text_on_accent};
            border: none;
            font-weight: 600;
        }}

        .app-btn-primary:hover {{
            background-color: {shades.hover};
        }}

        .app-btn-primary:active {{
            background-color: {shades.pressed};
        }}

        .app-btn-secondary {{
            background-color: {c.surface_raised};
            color: {c.text_primary};
            border: 1px solid {c.border};
        }}

        .app-btn-secondary:hover {{
            background-color: {c.surface_hover};
            border-color: {c.border_strong};
        }}

        .app-btn-flat {{
            background-color: transparent;
            color: {c.text_secondary};
            border: none;
        }}

        .app-btn-flat:hover {{
            background-color: {c.surface_hover};
            color: {c.text_primary};
        }}

        .app-btn-danger {{
            background-color: rgba({fail_rgb}, 0.18);
            color: {c.semantic.failed};
            border: 1px solid rgba({fail_rgb}, 0.4);
        }}

        .app-btn-danger:hover {{
            background-color: rgba({fail_rgb}, 0.28);
        }}

        /* Status Badges */
        .status-badge {{
            font-size: {int(typo.caption.size_pt * typo.scale_factor)}pt;
            font-weight: 600;
            padding: {metrics.badge_padding_v}px {metrics.badge_padding_h}px;
            border-radius: {max(2, rad - 2)}px;
            letter-spacing: 0.2px;
        }}

        .badge-installed {{
            background-color: rgba({inst_rgb}, 0.15);
            color: {c.semantic.installed};
            border: 1px solid rgba({inst_rgb}, 0.35);
        }}

        .badge-update {{
            background-color: rgba({upd_rgb}, 0.15);
            color: {c.semantic.update_available};
            border: 1px solid rgba({upd_rgb}, 0.35);
        }}

        .badge-unmanaged {{
            background-color: rgba({unm_rgb}, 0.15);
            color: {c.semantic.unmanaged};
            border: 1px solid rgba({unm_rgb}, 0.35);
        }}

        .badge-failed {{
            background-color: rgba({fail_rgb}, 0.15);
            color: {c.semantic.failed};
            border: 1px solid rgba({fail_rgb}, 0.35);
        }}

        .badge-neutral {{
            background-color: rgba({neut_rgb}, 0.15);
            color: {c.semantic.neutral};
            border: 1px solid rgba({neut_rgb}, 0.35);
        }}

        .badge-downloading {{
            background-color: rgba({down_rgb}, 0.15);
            color: {c.semantic.active_download};
            border: 1px solid rgba({down_rgb}, 0.35);
        }}

        /* Table & Mod Rows */
        .mod-table {{
            background-color: {c.surface};
            border: 1px solid {c.border};
            border-radius: {rad}px;
        }}

        .mod-table-header {{
            background-color: {c.surface_raised};
            border-bottom: 1px solid {c.border};
            font-weight: 600;
            font-size: {int(typo.caption.size_pt * typo.scale_factor)}pt;
            color: {c.text_secondary};
            padding: {metrics.row_padding_v}px {metrics.row_padding_h}px;
        }}

        .mod-row {{
            background-color: {c.surface};
            border-bottom: 1px solid {c.border_subtle};
            padding: {metrics.row_padding_v}px {metrics.row_padding_h}px;
            min-height: {metrics.row_height}px;
            transition: background-color 80ms ease;
        }}

        .mod-row:hover {{
            background-color: {c.surface_hover};
        }}

        .mod-row:selected {{
            background-color: {c.surface_active};
            border-left: 3px solid {shades.base};
        }}

        /* Form Inputs & Search */
        entry, search-entry {{
            background-color: {c.surface_raised};
            border: 1px solid {c.border};
            border-radius: {rad}px;
            color: {c.text_primary};
            padding: 4px 8px;
            min-height: {metrics.input_height}px;
            box-shadow: none;
        }}

        entry:focus, search-entry:focus {{
            border-color: {shades.base};
            outline: 2px solid {shades.subtle};
        }}

        /* Progress Bars */
        progressbar trough {{
            background-color: {c.surface_raised};
            border: 1px solid {c.border_subtle};
            border-radius: {max(2, rad - 2)}px;
            min-height: 5px;
        }}

        progressbar progress {{
            background-color: {shades.base};
            border-radius: {max(2, rad - 2)}px;
            min-height: 5px;
        }}

        /* Status Bar (Bottom) */
        .status-bar {{
            background-color: {c.surface};
            border-top: 1px solid {c.border};
            font-size: {int(typo.caption.size_pt * typo.scale_factor)}pt;
            color: {c.text_secondary};
            padding: 4px 12px;
            min-height: 24px;
        }}

        .status-pill {{
            padding: 2px 6px;
            border-radius: {rad}px;
        }}

        .status-dot-green {{
            color: {c.semantic.installed};
        }}

        .status-dot-amber {{
            color: {c.semantic.update_available};
        }}

        .status-dot-gray {{
            color: {c.semantic.neutral};
        }}

        /* Typography Utilities */
        .text-display {{
            font-size: {int(typo.display.size_pt * typo.scale_factor)}pt;
            font-weight: 600;
            color: {c.text_primary};
        }}

        .text-heading {{
            font-size: {int(typo.heading.size_pt * typo.scale_factor)}pt;
            font-weight: 600;
            color: {c.text_primary};
        }}

        .text-body {{
            font-size: {int(typo.body.size_pt * typo.scale_factor)}pt;
            font-weight: 400;
            color: {c.text_primary};
        }}

        .text-caption {{
            font-size: {int(typo.caption.size_pt * typo.scale_factor)}pt;
            font-weight: 500;
            color: {c.text_secondary};
        }}

        .text-muted {{
            color: {c.text_muted};
        }}

        .text-mono {{
            font-family: {typo.font_mono};
            font-size: {int(typo.monospace.size_pt * typo.scale_factor)}pt;
        }}
        """
        return css
