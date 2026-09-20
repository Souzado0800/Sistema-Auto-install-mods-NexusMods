"""
Component: SearchField.
Debounced search input with icon, placeholder, and clear button.
"""

from __future__ import annotations

from collections.abc import Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, Gtk


class SearchField(Gtk.SearchEntry):
    """Search input with automatic debouncing to prevent lagging large lists."""

    def __init__(
        self,
        placeholder: str = "Search mods...",
        on_search_changed: Callable[[str], None] | None = None,
        debounce_ms: int = 150,
    ):
        super().__init__()
        self.set_placeholder_text(placeholder)
        self._debounce_ms = debounce_ms
        self._on_search_changed = on_search_changed
        self._timer_id: int | None = None

        self.connect("search-changed", self._on_input_changed)

    def _on_input_changed(self, _entry: Gtk.SearchEntry) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

        text = self.get_text()
        if self._on_search_changed:
            self._timer_id = GLib.timeout_add(self._debounce_ms, self._fire_callback, text)

    def _fire_callback(self, text: str) -> bool:
        self._timer_id = None
        if self._on_search_changed:
            self._on_search_changed(text)
        return False
