"""
Component: StatusBadge.
Standardized semantic badge combining:
[ ICON + TEXT LABEL + SEMANTIC COLOR TOKEN ]
Guarantees accessibility by never relying solely on color.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.state import ModStatus


class StatusBadge(Gtk.Box):
    """Accessible, semantic status badge with icon and label."""

    def __init__(self, status: ModStatus | str, custom_label: str | None = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.add_css_class("status-badge")

        status_str = status.value if isinstance(status, ModStatus) else str(status)
        label_text = custom_label or status_str

        icon_name = "dialog-information-symbolic"
        css_class = "badge-neutral"

        if status_str == ModStatus.INSTALLED or status_str.lower() == "installed":
            icon_name = "emblem-ok-symbolic"
            css_class = "badge-installed"
        elif status_str == ModStatus.UPDATE_AVAILABLE or "update" in status_str.lower():
            icon_name = "software-update-available-symbolic"
            css_class = "badge-update"
        elif status_str == ModStatus.UNMANAGED or "unmanaged" in status_str.lower():
            icon_name = "view-more-symbolic"
            css_class = "badge-unmanaged"
        elif status_str == ModStatus.FAILED or "failed" in status_str.lower() or "error" in status_str.lower():
            icon_name = "dialog-error-symbolic"
            css_class = "badge-failed"
        elif status_str == ModStatus.DOWNLOADING or "download" in status_str.lower():
            icon_name = "folder-download-symbolic"
            css_class = "badge-downloading"
        elif status_str == ModStatus.CONFLICT or "conflict" in status_str.lower():
            icon_name = "dialog-warning-symbolic"
            css_class = "badge-update"

        self.add_css_class(css_class)

        # 1. Icon
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(12)
        self.append(icon)

        # 2. Text Label
        label = Gtk.Label(label=label_text)
        label.set_xalign(0.0)
        self.append(label)
