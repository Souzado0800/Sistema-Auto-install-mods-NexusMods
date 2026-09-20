"""
Design Tokens: Radius & Geometry.
Disciplined geometric curvature:
Avoids hyper-rounded "bubble" interfaces; uses subtle, crisp chamfer-like radii.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RadiusTokens:
    """Border-radius tokens in pixels."""
    none: int = 0
    small: int = 4       # Badges, tags, miniature buttons, tooltips
    medium: int = 6      # Buttons, inputs, dropdowns, table cards
    large: int = 8       # Modals, drawers, major containers
    pill: int = 9999     # Rounded pill badges when explicitly requested
