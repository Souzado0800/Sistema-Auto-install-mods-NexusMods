"""
Design Tokens: Spacing & Density.
Supports 4px-grid spacing scale and dual density presets:
- COMFORTABLE (Standard desktop spacing, touch-friendly, generous breathing room)
- COMPACT (High-density information view, fits 40+ mods simultaneously)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class UIDensity(StrEnum):
    COMFORTABLE = "comfortable"
    COMPACT = "compact"


@dataclass(frozen=True)
class SpacingScale:
    """4px-grid based spacing primitives in pixels."""
    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True)
class DensityMetrics:
    """Component-level sizing metrics governed by UIDensity."""
    row_height: int
    row_padding_v: int
    row_padding_h: int
    item_gap: int
    button_height: int
    input_height: int
    badge_padding_v: int
    badge_padding_h: int


COMFORTABLE_METRICS = DensityMetrics(
    row_height=42,
    row_padding_v=8,
    row_padding_h=12,
    item_gap=10,
    button_height=34,
    input_height=34,
    badge_padding_v=3,
    badge_padding_h=8,
)

COMPACT_METRICS = DensityMetrics(
    row_height=30,
    row_padding_v=4,
    row_padding_h=8,
    item_gap=6,
    button_height=26,
    input_height=26,
    badge_padding_v=1,
    badge_padding_h=6,
)


@dataclass
class SpacingTokens:
    """Spacing token container."""
    scale: SpacingScale = SpacingScale()
    density: UIDensity = UIDensity.COMFORTABLE

    @property
    def metrics(self) -> DensityMetrics:
        if self.density == UIDensity.COMPACT:
            return COMPACT_METRICS
        return COMFORTABLE_METRICS
