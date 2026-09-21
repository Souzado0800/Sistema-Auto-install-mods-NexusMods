"""
Shell Component: MainWindow.
Native Adw.ApplicationWindow orchestrating Sidebar, View Stack,
Toast notifications, and Status Bar.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from ui.desktop.components.button import IconButton
from ui.desktop.components.toast import ToastService
from ui.desktop.shell.sidebar import AppSidebar
from ui.desktop.shell.status_bar import AppStatusBar
from ui.desktop.state import AppState
from ui.desktop.theme.manager import ThemeManager
from ui.desktop.views.activity_view import ActivityView
from ui.desktop.views.dashboard_view import DashboardView
from ui.desktop.views.downloads_view import DownloadsView
from ui.desktop.views.mods_view import ModsView
from ui.desktop.views.preview_view import ComponentPreviewView
from ui.desktop.views.settings_view import SettingsView


class MainWindow(Adw.ApplicationWindow):
    """Main desktop application window."""

    def __init__(
        self,
        app: Adw.Application,
        state: AppState,
        theme_mgr: ThemeManager,
        initial_page: str = "dashboard",
    ):
        super().__init__(application=app)
        self.state = state
        self.theme_mgr = theme_mgr

        self.set_title("AutoInstallModMySummerCar")
        self.set_default_size(1040, 680)
        self.set_size_request(840, 520)

        # Apply active stylesheet to the display
        self.theme_mgr.apply_theme(self.theme_mgr.current_theme)

        # Root vertical container
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # 1. HeaderBar
        self.header_bar = Adw.HeaderBar()
        self.header_bar.add_css_class("adw-header-bar")

        title_widget = Adw.WindowTitle(title="AutoInstallModMySummerCar", subtitle="Precision Mod Engine")
        self.header_bar.set_title_widget(title_widget)

        btn_theme = IconButton(
            icon_name="weather-clear-night-symbolic",
            tooltip="Toggle Light / Dark Mode",
            on_clicked=self._toggle_light_dark,
        )
        self.header_bar.pack_end(btn_theme)
        root_box.append(self.header_bar)

        # 2. Toast Overlay wrapping content and status bar
        self.toast_overlay = Adw.ToastOverlay()
        ToastService.register_overlay(self.toast_overlay)

        middle_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        middle_box.set_vexpand(True)

        # Main horizontal workspace (Sidebar + Content Stack)
        workspace = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        workspace.set_hexpand(True)
        workspace.set_vexpand(True)

        # Sidebar
        self.sidebar = AppSidebar(on_page_changed=self._on_sidebar_navigate)
        self.sidebar.set_hexpand(False)
        workspace.append(self.sidebar)

        # Content Stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)

        # Register views
        self.view_dashboard = DashboardView(self.state)
        self.view_mods = ModsView(self.state)
        self.view_downloads = DownloadsView(self.state)
        self.view_activity = ActivityView(self.state)
        self.view_settings = SettingsView(self.state, self.theme_mgr)
        self.view_preview = ComponentPreviewView(self.theme_mgr)

        self.stack.add_named(self.view_dashboard, "dashboard")
        self.stack.add_named(self.view_mods, "mods")
        self.stack.add_named(self.view_downloads, "downloads")
        self.stack.add_named(self.view_activity, "activity")
        self.stack.add_named(self.view_settings, "settings")
        self.stack.add_named(self.view_preview, "preview")

        workspace.append(self.stack)
        middle_box.append(workspace)

        # 3. Status Bar
        self.status_bar = AppStatusBar()
        middle_box.append(self.status_bar)

        self.toast_overlay.set_child(middle_box)
        root_box.append(self.toast_overlay)

        self.set_content(root_box)

        # Initial navigation
        self.sidebar.set_active_page(initial_page)
        self.stack.set_visible_child_name(initial_page)

        # Sync telemetry
        self.state.subscribe("system", lambda s: self.status_bar.update_status(s))
        self.state.subscribe("mods", lambda m: self._sync_counts())
        self.state.subscribe("downloads", lambda d: self._sync_counts())
        self._sync_counts()

    def _on_sidebar_navigate(self, page_id: str) -> None:
        self.stack.set_visible_child_name(page_id)

    def _sync_counts(self) -> None:
        self.sidebar.update_badge("mods", len(self.state.mods))
        active_dl = sum(1 for d in self.state.downloads.values() if d.status == "Downloading")
        self.sidebar.update_badge("downloads", active_dl)

    def _toggle_light_dark(self) -> None:
        cur = self.theme_mgr.current_theme
        themes = self.theme_mgr.list_available_themes()
        target_name = "Workshop Light" if cur.meta.is_dark else "Garage Dark"
        target = next((t for t in themes if t.meta.name == target_name), None)
        if target:
            self.theme_mgr.apply_theme(target)
            ToastService.show(f"Theme switched to {target.meta.name}")
