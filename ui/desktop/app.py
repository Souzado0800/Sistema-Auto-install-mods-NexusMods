"""
Desktop Application Entrypoint.
Orchestrates Adw.Application lifecycle, theme initialization,
and switches between production, mock-demo, and storybook-preview modes.
"""

from __future__ import annotations

import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from ui.desktop.mock.demo_data import populate_demo_state
from ui.desktop.shell.window import MainWindow
from ui.desktop.state import AppState
from ui.desktop.theme.manager import ThemeManager


class DesktopApplication(Adw.Application):
    """Main desktop application class."""

    def __init__(
        self,
        is_demo_mode: bool = False,
        is_preview_mode: bool = False,
    ):
        super().__init__(
            application_id="com.msc.autoinstaller",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.is_demo_mode = is_demo_mode
        self.is_preview_mode = is_preview_mode

        self.state = AppState()
        self.theme_mgr = ThemeManager()
        self.window: MainWindow | None = None

        if self.is_demo_mode or self.is_preview_mode:
            populate_demo_state(self.state)

    def do_activate(self) -> None:
        """Called when the application is activated/launched."""
        if not self.window:
            initial_page = "preview" if self.is_preview_mode else "dashboard"
            self.window = MainWindow(
                app=self,
                state=self.state,
                theme_mgr=self.theme_mgr,
                initial_page=initial_page,
            )

        self.window.present()


def run_desktop_app(demo: bool = False, preview: bool = False) -> int:
    """Launches the desktop GUI application."""
    Adw.init()
    app = DesktopApplication(is_demo_mode=demo, is_preview_mode=preview)
    return app.run([sys.argv[0]])
