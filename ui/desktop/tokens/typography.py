"""
Design Tokens: Typography.
Strict 5-level typographic scale with font families, weights, and line heights.
Uses native Linux/system font stacks with zero proprietary font dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeStyle:
    """Attributes of a typographic style."""
    size_pt: int
    size_px: int
    weight: int          # CSS font-weight: 300, 400, 500, 600, 700
    line_height: float   # Relative line height multiplier
    letter_spacing_px: float = 0.0


@dataclass(frozen=True)
class TypographyTokens:
    """Strict typographic scale."""
    # Font Families
    font_sans: str = 'system-ui, -apple-system, Cantarell, "Ubuntu", "Segoe UI", Roboto, "Helvetica Neue", sans-serif'
    font_mono: str = '"Source Code Pro", "Fira Code", "Liberation Mono", "DejaVu Sans Mono", monospace'

    # Global Font Scale Multiplier (e.g. 1.0 for normal, 1.15 for high accessibility)
    scale_factor: float = 1.0

    # Strict Typographic Levels
    display: TypeStyle = TypeStyle(size_pt=14, size_px=19, weight=600, line_height=1.25, letter_spacing_px=-0.2)
    heading: TypeStyle = TypeStyle(size_pt=11, size_px=15, weight=600, line_height=1.3)
    body: TypeStyle = TypeStyle(size_pt=10, size_px=13, weight=400, line_height=1.4)
    caption: TypeStyle = TypeStyle(size_pt=9, size_px=11, weight=500, line_height=1.3, letter_spacing_px=0.1)
    monospace: TypeStyle = TypeStyle(size_pt=9, size_px=12, weight=400, line_height=1.4)
