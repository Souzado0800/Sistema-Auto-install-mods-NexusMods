"""
Component: AppButton & IconButton.
Standardized buttons adhering to design token geometry and interactive states.
Variants: primary, secondary, flat, danger.
"""

from __future__ import annotations

from collections.abc import Callable

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class AppButton(Gtk.Button):
    """General desktop action button."""

    def __init__(
        self,
        label: str = "",
        variant: str = "secondary",  # primary, secondary, flat, danger
        icon_name: str | None = None,
        on_clicked: Callable[[], None] | None = None,
        tooltip: str | None = None,
    ):
        super().__init__()
        self.add_css_class("app-btn")
        self.add_css_class(f"app-btn-{variant}")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_halign(Gtk.Align.CENTER)

        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(14)
            box.append(icon)

        if label:
            lbl = Gtk.Label(label=label)
            box.append(lbl)

        self.set_child(box)

        if tooltip:
            self.set_tooltip_text(tooltip)

        if on_clicked:
            self.connect("clicked", lambda _btn: on_clicked())


class IconButton(Gtk.Button):
    """Icon-only compact tool button."""

    def __init__(
        self,
        icon_name: str,
        tooltip: str | None = None,
        on_clicked: Callable[[], None] | None = None,
        flat: bool = True,
    ):
        super().__init__()
        self.add_css_class("app-btn")
        if flat:
            self.add_css_class("app-btn-flat")
        else:
            self.add_css_class("app-btn-secondary")

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(14)
        self.set_child(icon)

        if tooltip:
            self.set_tooltip_text(tooltip)

        if on_clicked:
            self.connect("clicked", lambda _btn: on_clicked())
