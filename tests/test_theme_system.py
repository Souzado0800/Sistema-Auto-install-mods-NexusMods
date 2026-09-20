"""Unit tests for UI Design Tokens, Themes, and CSS compilation."""


from ui.desktop.theme.manager import ThemeManager
from ui.desktop.tokens.colors import (
    contrast_ratio,
    derive_interactive_shades,
)
from ui.desktop.tokens.spacing import SpacingTokens, UIDensity


def test_color_contrast_calculation():
    """Verify WCAG contrast calculation."""
    # White on black should have maximum contrast ~21:1
    ratio = contrast_ratio("#ffffff", "#000000")
    assert ratio >= 20.0

    # Same color should have 1:1 contrast
    ratio_same = contrast_ratio("#131518", "#131518")
    assert 0.99 <= ratio_same <= 1.01


def test_interactive_shades_derivation():
    """Verify that interactive states (hover, pressed) are calculated properly."""
    shades = derive_interactive_shades("#e58e26", is_dark_theme=True)
    assert shades.base == "#e58e26"
    assert shades.hover != shades.base
    assert shades.pressed != shades.base
    # High-contrast text on bright amber should be dark
    assert shades.text_on_accent in ("#ffffff", "#111315")


def test_theme_presets_exist_and_load():
    """Verify built-in themes load from JSON presets."""
    tm = ThemeManager()
    themes = tm.list_available_themes()
    theme_names = [t.meta.name for t in themes]

    assert "Garage Dark" in theme_names
    assert "Graphite Monochrome" in theme_names
    assert "Workshop Light" in theme_names


def test_css_compilation():
    """Verify that ThemeManager compiles GTK 4 CSS properly."""
    tm = ThemeManager()
    theme = tm.current_theme
    css = tm.compile_css(theme)

    assert "window, .background" in css
    assert "headerbar" in css
    assert ".sidebar" in css
    assert ".status-badge" in css
    assert ".mod-row" in css
    assert ".app-btn-primary" in css
    assert theme.colors.background in css


def test_density_mode_toggle():
    """Verify switching density alters metrics."""
    tokens = SpacingTokens()
    assert tokens.metrics.row_height == 42

    tokens.density = UIDensity.COMPACT
    assert tokens.metrics.row_height == 30
