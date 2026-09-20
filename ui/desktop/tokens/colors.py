"""
Design Tokens: Colors & Palette.
Provides strictly typed color definitions, WCAG contrast calculation,
and automatic derivation of interactive states (hover, pressed, focus, disabled).
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, field


def _hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    """Converts #RRGGBB or #RGB to normalized (r, g, b) between 0.0 and 1.0."""
    hex_clean = hex_str.strip().lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    if len(hex_clean) != 6:
        raise ValueError(f"Invalid hex color string: {hex_str}")
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0
    return (r, g, b)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    """Converts normalized (r, g, b) to #RRGGBB."""
    ir = max(0, min(255, int(round(r * 255.0))))
    ig = max(0, min(255, int(round(g * 255.0))))
    ib = max(0, min(255, int(round(b * 255.0))))
    return f"#{ir:02x}{ig:02x}{ib:02x}"


def relative_luminance(hex_str: str) -> float:
    """Calculates WCAG relative luminance of a color."""
    r, g, b = _hex_to_rgb(hex_str)

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(hex_fg: str, hex_bg: str) -> float:
    """Calculates WCAG 2.1 contrast ratio between two colors (1:1 to 21:1)."""
    l1 = relative_luminance(hex_fg)
    l2 = relative_luminance(hex_bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def adjust_lightness(hex_str: str, delta: float) -> str:
    """Adjusts lightness (HLS) by delta (-1.0 to 1.0)."""
    r, g, b = _hex_to_rgb(hex_str)
    h, l_val, s = colorsys.rgb_to_hls(r, g, b)
    new_l = max(0.0, min(1.0, l_val + delta))
    nr, ng, nb = colorsys.hls_to_rgb(h, new_l, s)
    return _rgb_to_hex(nr, ng, nb)


def with_alpha(hex_str: str, alpha: float) -> str:
    """Converts hex to rgba(r, g, b, alpha) string."""
    r, g, b = _hex_to_rgb(hex_str)
    ir, ig, ib = int(r * 255), int(g * 255), int(b * 255)
    return f"rgba({ir}, {ig}, {ib}, {max(0.0, min(1.0, alpha)):.2f})"


@dataclass(frozen=True)
class SemanticColors:
    """Status and semantic communication colors."""
    installed: str = "#2ecc71"      # Calm moss green
    update_available: str = "#e58e26"  # Vintage rally amber
    unmanaged: str = "#74b9ff"      # Cold steel cyan
    failed: str = "#e74c3c"         # Industrial alarm crimson
    neutral: str = "#8b949e"        # Calibrated zinc slate
    cached: str = "#a29bfe"         # Subdued iris
    active_download: str = "#00d2d3" # Fast telemetry cyan


@dataclass(frozen=True)
class InteractiveShades:
    """Automatically derived interactive states for an accent or surface color."""
    base: str
    hover: str
    pressed: str
    focus: str
    subtle: str
    text_on_accent: str


def derive_interactive_shades(base_hex: str, is_dark_theme: bool = True) -> InteractiveShades:
    """Derives hover, pressed, focus, subtle, and high-contrast text color."""
    delta_hover = 0.07 if is_dark_theme else -0.07
    delta_pressed = -0.06 if is_dark_theme else 0.06

    hover = adjust_lightness(base_hex, delta_hover)
    pressed = adjust_lightness(base_hex, delta_pressed)
    focus = base_hex
    subtle = with_alpha(base_hex, 0.15 if is_dark_theme else 0.12)

    # Pick white or black text based on highest WCAG contrast
    contrast_white = contrast_ratio("#ffffff", base_hex)
    contrast_dark = contrast_ratio("#111315", base_hex)
    text_on_accent = "#ffffff" if contrast_white >= contrast_dark else "#111315"

    return InteractiveShades(
        base=base_hex,
        hover=hover,
        pressed=pressed,
        focus=focus,
        subtle=subtle,
        text_on_accent=text_on_accent,
    )


@dataclass
class ColorTokens:
    """Complete color token schema for the application."""
    # Base canvas
    background: str = "#131518"         # Deep workshop slate
    surface: str = "#1a1d21"            # Machine panel surface
    surface_raised: str = "#23282f"     # Elevated container / item background
    surface_hover: str = "#2b313a"      # Row & card hover state
    surface_active: str = "#323943"     # Selected row state

    # Dividers & Structural Borders
    border: str = "#2d333b"             # Hairline border
    border_subtle: str = "#22272e"      # Subtle separator
    border_strong: str = "#444c56"      # Focused / highlighted border

    # Typography & Content
    text_primary: str = "#e6edf3"       # Zinc white
    text_secondary: str = "#8b949e"     # Brushed aluminum
    text_muted: str = "#656d76"         # Dim metadata
    text_disabled: str = "#484f58"      # Disabled state

    # Accent / Brand
    accent: str = "#e58e26"             # Vintage rally amber / tungsten

    # Semantic Status
    semantic: SemanticColors = field(default_factory=SemanticColors)

    # Derived interactive accent shades
    is_dark: bool = True

    def get_accent_shades(self) -> InteractiveShades:
        return derive_interactive_shades(self.accent, is_dark_theme=self.is_dark)
