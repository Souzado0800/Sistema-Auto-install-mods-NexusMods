"""Unit tests for Desktop AppState, ModItemState, and filtering logic."""

from ui.desktop.mock.demo_data import SAMPLE_MODS, populate_demo_state
from ui.desktop.state import AppState, ModStatus


def test_app_state_initialization():
    state = AppState()
    assert len(state.mods) == 0
    assert len(state.downloads) == 0


def test_app_state_filtering():
    state = AppState()
    state.set_mods(SAMPLE_MODS)
    assert len(state.mods) == len(SAMPLE_MODS)

    # Search filter
    state.search_query = "Tangerine"
    filtered = state.get_filtered_mods()
    assert len(filtered) == 1
    assert filtered[0].name == "Tangerine FZ-120 Pickup"

    # Status filter
    state.search_query = ""
    state.selected_filter = "Updates"
    updates = state.get_filtered_mods()
    assert len(updates) > 0
    assert all(m.status == ModStatus.UPDATE_AVAILABLE for m in updates)


def test_app_state_demo_population():
    state = AppState()
    populate_demo_state(state)

    assert state.system.msc_detected is True
    assert state.system.msc_loader_present is True
    assert state.system.nexus_authenticated is True
    assert len(state.mods) > 0
    assert len(state.downloads) > 0
    assert len(state.activities) > 0
