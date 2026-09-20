"""
Theme schema definition and validation.
Enables full theme export/import via human-readable JSON files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ui.desktop.tokens.colors import ColorTokens, SemanticColors
from ui.desktop.tokens.spacing import UIDensity


@dataclass
class ThemeMetadata:
    """Metadata describing a theme."""
    id: str
    name: str
    author: str = "System"
    description: str = ""
    version: str = "1.0.0"
    is_dark: bool = True
    is_builtin: bool = False


@dataclass
class ThemeDefinition:
    """Full theme configuration."""
    meta: ThemeMetadata
    colors: ColorTokens = field(default_factory=ColorTokens)
    density: UIDensity = UIDensity.COMFORTABLE
    font_scale: float = 1.0
    corner_radius: int = 6  # medium default

    def to_dict(self) -> dict[str, Any]:
        """Serializes theme to a clean dictionary."""
        return {
            "schema_version": 1,
            "meta": {
                "id": self.meta.id,
                "name": self.meta.name,
                "author": self.meta.author,
                "description": self.meta.description,
                "version": self.meta.version,
                "is_dark": self.meta.is_dark,
                "is_builtin": self.meta.is_builtin,
            },
            "appearance": {
                "density": self.density.value,
                "font_scale": self.font_scale,
                "corner_radius": self.corner_radius,
            },
            "colors": {
                "background": self.colors.background,
                "surface": self.colors.surface,
                "surface_raised": self.colors.surface_raised,
                "surface_hover": self.colors.surface_hover,
                "surface_active": self.colors.surface_active,
                "border": self.colors.border,
                "border_subtle": self.colors.border_subtle,
                "border_strong": self.colors.border_strong,
                "text_primary": self.colors.text_primary,
                "text_secondary": self.colors.text_secondary,
                "text_muted": self.colors.text_muted,
                "text_disabled": self.colors.text_disabled,
                "accent": self.colors.accent,
            },
            "semantic": {
                "installed": self.colors.semantic.installed,
                "update_available": self.colors.semantic.update_available,
                "unmanaged": self.colors.semantic.unmanaged,
                "failed": self.colors.semantic.failed,
                "neutral": self.colors.semantic.neutral,
                "cached": self.colors.semantic.cached,
                "active_download": self.colors.semantic.active_download,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThemeDefinition:
        """Parses a dictionary into a ThemeDefinition."""
        meta_d = data.get("meta", {})
        meta = ThemeMetadata(
            id=meta_d.get("id", "custom"),
            name=meta_d.get("name", "Custom Theme"),
            author=meta_d.get("author", "User"),
            description=meta_d.get("description", ""),
            version=meta_d.get("version", "1.0.0"),
            is_dark=bool(meta_d.get("is_dark", True)),
            is_builtin=bool(meta_d.get("is_builtin", False)),
        )

        app_d = data.get("appearance", {})
        density_str = app_d.get("density", "comfortable")
        density = UIDensity.COMPACT if density_str == "compact" else UIDensity.COMFORTABLE
        font_scale = float(app_d.get("font_scale", 1.0))
        corner_radius = int(app_d.get("corner_radius", 6))

        c_d = data.get("colors", {})
        sem_d = data.get("semantic", {})
        semantic = SemanticColors(
            installed=sem_d.get("installed", "#2ecc71"),
            update_available=sem_d.get("update_available", "#e58e26"),
            unmanaged=sem_d.get("unmanaged", "#74b9ff"),
            failed=sem_d.get("failed", "#e74c3c"),
            neutral=sem_d.get("neutral", "#8b949e"),
            cached=sem_d.get("cached", "#a29bfe"),
            active_download=sem_d.get("active_download", "#00d2d3"),
        )

        colors = ColorTokens(
            background=c_d.get("background", "#131518"),
            surface=c_d.get("surface", "#1a1d21"),
            surface_raised=c_d.get("surface_raised", "#23282f"),
            surface_hover=c_d.get("surface_hover", "#2b313a"),
            surface_active=c_d.get("surface_active", "#323943"),
            border=c_d.get("border", "#2d333b"),
            border_subtle=c_d.get("border_subtle", "#22272e"),
            border_strong=c_d.get("border_strong", "#444c56"),
            text_primary=c_d.get("text_primary", "#e6edf3"),
            text_secondary=c_d.get("text_secondary", "#8b949e"),
            text_muted=c_d.get("text_muted", "#656d76"),
            text_disabled=c_d.get("text_disabled", "#484f58"),
            accent=c_d.get("accent", "#e58e26"),
            semantic=semantic,
            is_dark=meta.is_dark,
        )

        return cls(
            meta=meta,
            colors=colors,
            density=density,
            font_scale=font_scale,
            corner_radius=corner_radius,
        )

    def save_to_file(self, path: Path) -> None:
        """Saves theme to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> ThemeDefinition:
        """Loads a theme from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
