"""Tests for secure credential storage and redaction."""

from unittest.mock import patch

from credentials.manager import CredentialManager


def test_credential_manager_env_var(monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "test_env_api_key_123456789")
    key = CredentialManager.get_api_key()
    assert key == "test_env_api_key_123456789"


def test_credential_manager_save_and_read(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)
    fake_config_dir = tmp_path / ".config" / "AutoInstallModMySummerCar"
    fake_cred_file = fake_config_dir / "credentials.json"

    with patch("credentials.manager.USER_CONFIG_DIR", fake_config_dir), \
         patch("credentials.manager.CREDENTIALS_FILE", fake_cred_file), \
         patch("keyring.get_password", return_value=None), \
         patch("keyring.set_password", return_value=None):

        assert CredentialManager.get_api_key() is None

        # Save key
        saved = CredentialManager.save_api_key("super_secret_nexus_key_99999")
        assert saved is True
        assert fake_cred_file.is_file()

        # Check file mode on Unix (0600)
        mode = oct(fake_cred_file.stat().st_mode & 0o777)
        assert mode == "0o600"

        # Read back
        monkeypatch.delenv("NEXUS_API_KEY", raising=False)
        read_key = CredentialManager.get_api_key()
        assert read_key == "super_secret_nexus_key_99999"


def test_credential_manager_redaction():
    secret = "secret_key_abc123456789"
    text = f"Connecting with apikey='{secret}' to https://api.nexusmods.com"
    redacted = CredentialManager.redact(text, api_key=secret)
    assert secret not in redacted
    assert "[REDACTED" in redacted
