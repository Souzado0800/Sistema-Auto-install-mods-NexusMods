"""
Shell Component: StatusBar.
Discreet bottom status bar displaying global system diagnostics.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.state import SystemStatus


class AppStatusBar(Gtk.Box):
    """Bottom telemetry and status bar."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.add_css_class("status-bar")
        self.set_hexpand(True)

        # Nexus status
        self.lbl_nexus = Gtk.Label(label="Nexus: Checking...")
        self.lbl_nexus.set_xalign(0.0)
        self.append(self.lbl_nexus)

        self.append(self._create_sep())

        # MSCLoader status
        self.lbl_loader = Gtk.Label(label="MSCLoader: Checking...")
        self.lbl_loader.set_xalign(0.0)
        self.append(self.lbl_loader)

        self.append(self._create_sep())

        # Browser status
        self.lbl_browser = Gtk.Label(label="Browser: Idle")
        self.lbl_browser.set_xalign(0.0)
        self.append(self.lbl_browser)

        # Expanding spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.append(spacer)

        # Engine activity state
        self.lbl_engine = Gtk.Label(label="● Ready")
        self.lbl_engine.add_css_class("status-dot-green")
        self.lbl_engine.set_xalign(1.0)
        self.append(self.lbl_engine)

    def _create_sep(self) -> Gtk.Label:
        sep = Gtk.Label(label="│")
        sep.add_css_class("text-muted")
        return sep

    def update_status(self, system: SystemStatus) -> None:
        """Refreshes status bar telemetry."""
        # Nexus
        if system.nexus_authenticated:
            self.lbl_nexus.set_text(f"Nexus: {system.nexus_user} ({system.nexus_tier})")
        else:
            self.lbl_nexus.set_text("Nexus: Disconnected")

        # MSCLoader
        if system.msc_loader_present:
            self.lbl_loader.set_text("MSCLoader: Ready")
        elif system.msc_detected:
            self.lbl_loader.set_text("MSCLoader: Missing")
        else:
            self.lbl_loader.set_text("MSC: Not Found")

        # Browser
        if system.browser_detected:
            tabs_text = f"{system.browser_tabs_count} tabs" if system.browser_tabs_count > 0 else "Ready"
            self.lbl_browser.set_text(f"Browser: {system.browser_detected} ({tabs_text})")
        else:
            self.lbl_browser.set_text("Browser: Idle")

        # Engine
        self.lbl_engine.set_text(f"● {system.engine_state}")
        if system.engine_state in ("Downloading", "Installing", "Scanning"):
            self.lbl_engine.remove_css_class("status-dot-green")
            self.lbl_engine.add_css_class("status-dot-amber")
        else:
            self.lbl_engine.remove_css_class("status-dot-amber")
            self.lbl_engine.add_css_class("status-dot-green")
