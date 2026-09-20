"""
Component: EmptyState.
Calm, helpful empty state view with clear human instructions and optional action button.
Avoids oversized cartoon illustrations or AI-generic clip art.
"""

from __future__ import annotations

from collections.abc import Callable

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.button import AppButton


class EmptyState(Gtk.Box):
    """Clean technical empty state message."""

    def __init__(
        self,
        icon_name: str = "edit-find-symbolic",
        title: str = "No Items",
        description: str = "",
        action_label: str | None = None,
        on_action: Callable[[], None] | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_margin_top(40)
        self.set_margin_bottom(40)

        # 1. Subtle Icon
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(36)
        icon.add_css_class("text-muted")
        self.append(icon)

        # 2. Title
        lbl_title = Gtk.Label(label=title)
        lbl_title.add_css_class("text-heading")
        self.append(lbl_title)

        # 3. Description
        if description:
            lbl_desc = Gtk.Label(label=description)
            lbl_desc.add_css_class("text-caption")
            lbl_desc.add_css_class("text-muted")
            lbl_desc.set_justify(Gtk.Justification.CENTER)
            lbl_desc.set_wrap(True)
            lbl_desc.set_max_width_chars(45)
            self.append(lbl_desc)

        # 4. Action Button
        if action_label and on_action:
            btn = AppButton(label=action_label, variant="secondary", on_clicked=on_action)
            btn.set_halign(Gtk.Align.CENTER)
            btn.set_margin_top(6)
            self.append(btn)
