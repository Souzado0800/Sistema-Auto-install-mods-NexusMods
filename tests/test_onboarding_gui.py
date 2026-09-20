"""
Automated unit tests for the native GTK 3 onboarding window (ui/onboarding_gui.py).
Tests all widget logic: empty input, normal input, paste, show/hide password,
unicode, very long input, double click prevention, valid and invalid validation, and timeouts.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from credentials.manager import CredentialManager
from nexus.models import UserValidate
from ui.onboarding_gui import NexusOnboardingWindow, is_gui_available

pytestmark = pytest.mark.skipif(not is_gui_available(), reason="GTK 3 GUI display not available")


@pytest.fixture
def isolated_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate credentials file, OS keyring, and environment variable to temporary directory."""
    config_dir = tmp_path / "user_config"
    cred_file = config_dir / "credentials.json"
    monkeypatch.setattr(CredentialManager, "USER_CONFIG_DIR", config_dir)
    monkeypatch.setattr(CredentialManager, "CREDENTIALS_FILE", cred_file)
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)

    fake_keyring: dict[tuple[str, str], str] = {}
    monkeypatch.setattr("keyring.get_password", lambda s, u: fake_keyring.get((s, u)))
    monkeypatch.setattr("keyring.set_password", lambda s, u, p: fake_keyring.update({(s, u): p}))
    monkeypatch.setattr("keyring.delete_password", lambda s, u: fake_keyring.pop((s, u), None))
    return config_dir, cred_file


def test_gui_empty_input_shows_warning(isolated_credentials):
    """Empty input triggers friendly warning without closing or saving."""
    window = NexusOnboardingWindow(test_mode=True)
    window.entry.set_text("")
    window._on_validate_clicked(None)

    assert window.validated_key is None
    assert "Chave vazia" in window.status_label.get_label()
    window.window.destroy()


def test_gui_normal_input_test_mode(isolated_credentials):
    """Normal input in test mode confirms keyboard and input receipt without saving."""
    window = NexusOnboardingWindow(test_mode=True)
    test_key = "dummy_personal_api_key_12345"
    window.entry.set_text(test_key)
    window._on_validate_clicked(None)

    assert window.validated_key == f"TEST_MODE_KEY_{len(test_key)}"
    assert "Teste Concluído com Sucesso" in window.status_label.get_label()
    assert CredentialManager.get_api_key() is None
    window.window.destroy()


def test_gui_show_hide_password_toggle(isolated_credentials):
    """Checkbox toggles password bullet masking correctly."""
    window = NexusOnboardingWindow(test_mode=True)
    # Default is masked (visibility False)
    assert window.entry.get_visibility() is False

    # Toggle Show
    window.check_show.set_active(True)
    assert window.entry.get_visibility() is True

    # Toggle Hide
    window.check_show.set_active(False)
    assert window.entry.get_visibility() is False
    window.window.destroy()


def test_gui_unicode_and_very_long_input(isolated_credentials):
    """Handles unicode, special characters, and very long pasted strings gracefully."""
    window = NexusOnboardingWindow(test_mode=True)
    long_key = "chave_🔑_longa_" + ("A" * 2048) + "_fim"
    window.entry.set_text(long_key)
    assert window.entry.get_text() == long_key

    window._on_validate_clicked(None)
    assert window.validated_key == f"TEST_MODE_KEY_{len(long_key)}"
    window.window.destroy()


def test_gui_double_click_prevention(isolated_credentials):
    """Button and entry are disabled during validation to prevent double submissions."""
    window = NexusOnboardingWindow(test_mode=False)
    window.entry.set_text("test_submission_key")

    with patch("threading.Thread.start"):
        window._on_validate_clicked(None)
        assert window.btn_validate.get_sensitive() is False
        assert window.entry.get_sensitive() is False
        assert "Validando com Nexus Mods" in window.status_label.get_label()

    window.window.destroy()


def flush_gtk_events():
    """Flushes pending GLib / GTK idle callbacks in test runner."""
    from gi.repository import Gtk
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def test_gui_validation_success_saves_and_stores_user(isolated_credentials):
    """Successful validation saves to CredentialManager and records validated key."""
    window = NexusOnboardingWindow(test_mode=False)
    secret_key = "validated_nexus_key_998877"
    mock_user = UserValidate(
        user_id=77,
        key=secret_key,
        name="GuiTester",
        is_premium=True,
        email="gui@test.com",
        profile_url="",
    )

    with patch("nexus.api.NexusApiClient.validate_key", new_callable=AsyncMock, return_value=mock_user):
        window._validate_worker(secret_key)
        flush_gtk_events()

    assert window.validated_key == secret_key
    assert window.user_info.name == "GuiTester"
    assert CredentialManager.get_api_key() == secret_key
    assert "Personal API Key válida" in window.status_label.get_label()
    window.window.destroy()


def test_gui_validation_failure_reenables_and_selects(isolated_credentials):
    """Rejected key shows friendly error, re-enables controls, and highlights input."""
    window = NexusOnboardingWindow(test_mode=False)
    window.btn_validate.set_sensitive(False)
    window.entry.set_sensitive(False)

    window._on_validation_failure("401 Unauthorized")
    flush_gtk_events()

    assert window.btn_validate.get_sensitive() is True
    assert window.entry.get_sensitive() is True
    assert "rejeitou esta Personal API Key" in window.status_label.get_label()
    assert window.validated_key is None
    window.window.destroy()


def test_gui_network_timeout_handling(isolated_credentials):
    """Network timeouts or exceptions do not crash and re-enable input."""
    window = NexusOnboardingWindow(test_mode=False)

    with patch("nexus.api.NexusApiClient.validate_key", side_effect=TimeoutError("Request timed out")):
        window._validate_worker("test_key_timeout")
        flush_gtk_events()

    assert window.btn_validate.get_sensitive() is True
    assert window.entry.get_sensitive() is True
    assert "rejeitou esta Personal API Key" in window.status_label.get_label()
    window.window.destroy()
