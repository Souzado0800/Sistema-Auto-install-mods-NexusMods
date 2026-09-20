"""
Component: ModRow.
High-density row representing an installed, discovered, or updating mod.
Adheres to design token row heights and density presets.
"""

from __future__ import annotations

from collections.abc import Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, Gtk

from ui.desktop.components.badge import StatusBadge
from ui.desktop.state import ModItemState


class ModRow(Gtk.Box):
    """High-density list row for a mod item."""

    def __init__(
        self,
        mod: ModItemState,
        on_selected: Callable[[int], None] | None = None,
        on_context_action: Callable[[str, ModItemState], None] | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.mod = mod
        self.on_selected = on_selected
        self.on_context_action = on_context_action

        self.add_css_class("mod-row")
        self.set_hexpand(True)

        # 1. Mod Name & Author
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name_box.set_hexpand(True)

        lbl_name = Gtk.Label(label=mod.name)
        lbl_name.add_css_class("text-heading")
        lbl_name.set_xalign(0.0)
        lbl_name.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        name_box.append(lbl_name)

        author_text = f"by {mod.author}" if mod.author and mod.author != "Unknown" else f"Nexus ID #{mod.mod_id}"
        lbl_author = Gtk.Label(label=author_text)
        lbl_author.add_css_class("text-caption")
        lbl_author.add_css_class("text-muted")
        lbl_author.set_xalign(0.0)
        name_box.append(lbl_author)

        self.append(name_box)

        # 2. Version Column
        ver_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        ver_box.set_size_request(90, -1)

        lbl_ver = Gtk.Label(label=f"v{mod.version}")
        lbl_ver.add_css_class("text-body")
        lbl_ver.add_css_class("text-mono")
        lbl_ver.set_xalign(0.0)
        ver_box.append(lbl_ver)

        if mod.latest_version and mod.latest_version != mod.version:
            lbl_upd = Gtk.Label(label=f"latest: {mod.latest_version}")
            lbl_upd.add_css_class("text-caption")
            lbl_upd.add_css_class("text-muted")
            lbl_upd.set_xalign(0.0)
            ver_box.append(lbl_upd)

        self.append(ver_box)

        # 3. Source Column
        src_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        src_box.set_size_request(80, -1)
        lbl_src = Gtk.Label(label=mod.source)
        lbl_src.add_css_class("text-caption")
        lbl_src.add_css_class("text-muted")
        lbl_src.set_xalign(0.0)
        src_box.append(lbl_src)
        self.append(src_box)

        # 4. Status Badge
        badge = StatusBadge(mod.status)
        badge.set_size_request(130, -1)
        badge.set_halign(Gtk.Align.END)
        self.append(badge)

        # Click gesture
        gesture_click = Gtk.GestureClick.new()
        gesture_click.connect("pressed", self._on_pressed)
        self.add_controller(gesture_click)

    def _on_pressed(self, _gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        button = _gesture.get_current_button()
        if button == Gdk.BUTTON_PRIMARY and self.on_selected:
            self.on_selected(self.mod.mod_id)
        elif button == Gdk.BUTTON_SECONDARY and self.on_context_action:
            self._show_context_menu(x, y)

    def _show_context_menu(self, x: float, y: float) -> None:
        menu = Gio.Menu()
        menu.append("View Details", "mod.details")
        if self.mod.nexus_url or self.mod.mod_id > 0:
            menu.append("Open Nexus Page", "mod.nexus")
            menu.append("Copy Nexus ID", "mod.copy_id")
        menu.append("Open Installed Files", "mod.open_files")

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(self)
        popover.set_pointing_to(Gdk.Rectangle(x=int(x), y=int(y), width=1, height=1))
        popover.popup()
