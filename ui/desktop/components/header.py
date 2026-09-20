"""
Component: SectionHeader & ViewHeader.
Provides clean hierarchical titles, descriptions, and action slots.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class SectionHeader(Gtk.Box):
    """Section header with title, optional count/badge, and right-aligned actions."""

    def __init__(
        self,
        title: str,
        subtitle: str | None = None,
        count: int | None = None,
        action_widget: Gtk.Widget | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_hexpand(True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vbox.set_hexpand(True)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_title = Gtk.Label(label=title)
        lbl_title.add_css_class("text-display")
        lbl_title.set_xalign(0.0)
        title_box.append(lbl_title)

        if count is not None:
            lbl_count = Gtk.Label(label=str(count))
            lbl_count.add_css_class("status-badge")
            lbl_count.add_css_class("badge-neutral")
            title_box.append(lbl_count)

        vbox.append(title_box)

        if subtitle:
            lbl_sub = Gtk.Label(label=subtitle)
            lbl_sub.add_css_class("text-caption")
            lbl_sub.add_css_class("text-muted")
            lbl_sub.set_xalign(0.0)
            vbox.append(lbl_sub)

        self.append(vbox)

        if action_widget:
            action_widget.set_valign(Gtk.Align.CENTER)
            self.append(action_widget)
