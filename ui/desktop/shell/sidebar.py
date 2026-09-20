"""
Shell Component: Sidebar.
Clean desktop navigation sidebar with icon, label, and dynamic count badges.
"""

from __future__ import annotations

from collections.abc import Callable

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class SidebarItem(Gtk.Button):
    """Individual navigation button in the sidebar."""

    def __init__(
        self,
        page_id: str,
        label: str,
        icon_name: str,
        on_click: Callable[[str], None],
    ):
        super().__init__()
        self.page_id = page_id
        self.on_click = on_click
        self.add_css_class("sidebar-item")
        self.add_css_class("app-btn-flat")
        self.set_hexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_hexpand(True)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        box.append(icon)

        lbl = Gtk.Label(label=label)
        lbl.set_xalign(0.0)
        lbl.set_hexpand(True)
        box.append(lbl)

        self.badge = Gtk.Label(label="")
        self.badge.add_css_class("status-badge")
        self.badge.add_css_class("badge-neutral")
        self.badge.set_visible(False)
        box.append(self.badge)

        self.set_child(box)
        self.connect("clicked", lambda _b: self.on_click(self.page_id))

    def set_badge_count(self, count: int) -> None:
        if count > 0:
            self.badge.set_text(str(count))
            self.badge.set_visible(True)
        else:
            self.badge.set_visible(False)

    def set_active_state(self, is_active: bool) -> None:
        if is_active:
            self.add_css_class("active")
        else:
            self.remove_css_class("active")


class AppSidebar(Gtk.Box):
    """Desktop navigation sidebar container."""

    def __init__(self, on_page_changed: Callable[[str], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("sidebar")
        self.set_size_request(200, -1)
        self.on_page_changed = on_page_changed

        self.items: dict[str, SidebarItem] = {}

        # Brand header / Subtitle
        brand_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        brand_box.set_margin_top(8)
        brand_box.set_margin_bottom(12)
        brand_box.set_margin_start(10)

        lbl_app = Gtk.Label(label="MY SUMMER CAR")
        lbl_app.add_css_class("text-caption")
        lbl_app.add_css_class("text-muted")
        lbl_app.set_xalign(0.0)
        brand_box.append(lbl_app)

        lbl_sub = Gtk.Label(label="Mod AutoInstaller")
        lbl_sub.add_css_class("text-heading")
        lbl_sub.set_xalign(0.0)
        brand_box.append(lbl_sub)

        self.append(brand_box)

        # Navigation sections
        self._add_item("dashboard", "Dashboard", "user-home-symbolic")
        self._add_item("mods", "Mods", "package-x-generic-symbolic")
        self._add_item("downloads", "Downloads", "folder-download-symbolic")
        self._add_item("activity", "Activity", "utilities-terminal-symbolic")

        # Spacer to push settings to bottom
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        self.append(spacer)

        self._add_item("settings", "Settings", "emblem-system-symbolic")

    def _add_item(self, page_id: str, label: str, icon_name: str) -> None:
        item = SidebarItem(page_id, label, icon_name, self._handle_item_click)
        self.items[page_id] = item
        self.append(item)

    def _handle_item_click(self, page_id: str) -> None:
        self.set_active_page(page_id)
        self.on_page_changed(page_id)

    def set_active_page(self, active_id: str) -> None:
        for pid, item in self.items.items():
            item.set_active_state(pid == active_id)

    def update_badge(self, page_id: str, count: int) -> None:
        if page_id in self.items:
            self.items[page_id].set_badge_count(count)
