"""
View: Mods (Management & Details).
High-density mods table with search, filtering, and details drawer.
"""

from __future__ import annotations

import webbrowser

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.desktop.components.badge import StatusBadge
from ui.desktop.components.button import AppButton, IconButton
from ui.desktop.components.empty_state import EmptyState
from ui.desktop.components.header import SectionHeader
from ui.desktop.components.mod_row import ModRow
from ui.desktop.components.search_field import SearchField
from ui.desktop.state import AppState, ModItemState


class ModsView(Gtk.Box):
    """Mods list and inspection view."""

    def __init__(self, state: AppState):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.state = state
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Left Column: Search, Filters, and Table
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        left_box.set_margin_top(20)
        left_box.set_margin_bottom(20)
        left_box.set_margin_start(20)
        left_box.set_margin_end(20)
        left_box.set_hexpand(True)

        # 1. Header with search bar
        search = SearchField(
            placeholder="Search mods by name, author, or ID...",
            on_search_changed=self._on_search_changed,
        )
        search.set_hexpand(True)

        self.header = SectionHeader(
            title="Mods",
            subtitle="Managed mods, local files, updates, and integrity status.",
            action_widget=search,
        )
        left_box.append(self.header)

        # 2. Filter Bar
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.filter_buttons: dict[str, AppButton] = {}

        for f_name in ["All", "Installed", "Updates", "Unmanaged", "Failed"]:
            btn = AppButton(
                label=f_name,
                variant="secondary",
                on_clicked=lambda fn=f_name: self._set_filter(fn),
            )
            self.filter_buttons[f_name] = btn
            filter_box.append(btn)

        self._update_filter_styles()
        left_box.append(filter_box)

        # 3. Scrolled Table Container
        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)

        self.table_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.table_card.add_css_class("mod-table")

        # Table Header
        th = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        th.add_css_class("mod-table-header")

        lbl_name = Gtk.Label(label="NAME")
        lbl_name.set_xalign(0.0)
        lbl_name.set_hexpand(True)
        th.append(lbl_name)

        lbl_ver = Gtk.Label(label="VERSION")
        lbl_ver.set_size_request(90, -1)
        lbl_ver.set_xalign(0.0)
        th.append(lbl_ver)

        lbl_src = Gtk.Label(label="SOURCE")
        lbl_src.set_size_request(80, -1)
        lbl_src.set_xalign(0.0)
        th.append(lbl_src)

        lbl_st = Gtk.Label(label="STATUS")
        lbl_st.set_size_request(120, -1)
        lbl_st.set_xalign(0.5)
        lbl_st.set_margin_end(8)
        th.append(lbl_st)

        self.table_card.append(th)

        self.rows_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.table_card.append(self.rows_container)
        scroller.set_child(self.table_card)

        left_box.append(scroller)
        self.append(left_box)

        # Right Column: Mod Details Drawer (Hidden when none selected)
        self.drawer = self._build_details_drawer()
        self.append(self.drawer)

        # Subscribe to state
        self.state.subscribe("mods", lambda _m: self._render_mods())
        self.state.subscribe("selection", lambda _s: self._render_details())

        self._render_mods()

    def _set_filter(self, f_name: str) -> None:
        self.state.selected_filter = f_name
        self._update_filter_styles()
        self._render_mods()

    def _update_filter_styles(self) -> None:
        for name, btn in self.filter_buttons.items():
            if name == self.state.selected_filter:
                btn.remove_css_class("app-btn-secondary")
                btn.add_css_class("app-btn-primary")
            else:
                btn.remove_css_class("app-btn-primary")
                btn.add_css_class("app-btn-secondary")

    def _on_search_changed(self, text: str) -> None:
        self.state.search_query = text
        self._render_mods()

    def _render_mods(self) -> None:
        # Clear existing rows
        child = self.rows_container.get_first_child()
        while child:
            next_ch = child.get_next_sibling()
            self.rows_container.remove(child)
            child = next_ch

        mods = self.state.get_filtered_mods()
        if not mods:
            empty = EmptyState(
                icon_name="edit-find-symbolic",
                title="No Matching Mods Found",
                description="Try clearing your search query or switching status filters.",
            )
            self.rows_container.append(empty)
            return

        for m in mods:
            row = ModRow(
                mod=m,
                on_selected=self._on_mod_selected,
                on_context_action=self._on_context_action,
            )
            self.rows_container.append(row)

    def _on_mod_selected(self, mod_id: int) -> None:
        if self.state.selected_mod_id == mod_id:
            self.state.select_mod(None)  # Toggle off
        else:
            self.state.select_mod(mod_id)

    def _on_context_action(self, action: str, mod: ModItemState) -> None:
        if action == "mod.nexus" and mod.nexus_url:
            try:
                webbrowser.open(mod.nexus_url)
            except Exception:
                pass

    def _build_details_drawer(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("sidebar")
        box.set_size_request(280, -1)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_end(20)
        box.set_visible(False)

        # Header with close button
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_hdr = Gtk.Label(label="MOD DETAILS")
        lbl_hdr.add_css_class("text-caption")
        lbl_hdr.add_css_class("text-muted")
        lbl_hdr.set_xalign(0.0)
        lbl_hdr.set_hexpand(True)
        hdr.append(lbl_hdr)

        btn_close = IconButton(icon_name="window-close-symbolic", on_clicked=lambda: self.state.select_mod(None))
        hdr.append(btn_close)
        box.append(hdr)

        self.drawer_name = Gtk.Label(label="")
        self.drawer_name.add_css_class("text-heading")
        self.drawer_name.set_xalign(0.0)
        self.drawer_name.set_wrap(True)
        box.append(self.drawer_name)

        self.drawer_badge_box = Gtk.Box()
        box.append(self.drawer_badge_box)

        self.drawer_author = Gtk.Label(label="")
        self.drawer_author.add_css_class("text-caption")
        self.drawer_author.add_css_class("text-muted")
        self.drawer_author.set_xalign(0.0)
        box.append(self.drawer_author)

        self.drawer_desc = Gtk.Label(label="")
        self.drawer_desc.add_css_class("text-body")
        self.drawer_desc.set_xalign(0.0)
        self.drawer_desc.set_wrap(True)
        box.append(self.drawer_desc)

        # Action buttons
        actions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        actions_box.set_margin_top(12)

        self.btn_open_nexus = AppButton(
            label="Open Nexus Page",
            variant="secondary",
            icon_name="web-browser-symbolic",
            on_clicked=self._open_selected_nexus,
        )
        actions_box.append(self.btn_open_nexus)

        box.append(actions_box)
        return box

    def _render_details(self) -> None:
        mod_id = self.state.selected_mod_id
        if mod_id is None or mod_id not in self.state.mods:
            self.drawer.set_visible(False)
            return

        mod = self.state.mods[mod_id]
        self.drawer.set_visible(True)

        self.drawer_name.set_text(mod.name)
        self.drawer_author.set_text(f"Author: {mod.author} · v{mod.version} · Mod #{mod.mod_id}")
        self.drawer_desc.set_text(mod.description or "No description provided.")

        ch = self.drawer_badge_box.get_first_child()
        if ch:
            self.drawer_badge_box.remove(ch)
        self.drawer_badge_box.append(StatusBadge(mod.status))

        self.btn_open_nexus.set_visible(bool(mod.nexus_url))

    def _open_selected_nexus(self) -> None:
        mod_id = self.state.selected_mod_id
        if mod_id and mod_id in self.state.mods:
            url = self.state.mods[mod_id].nexus_url
            if url:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
