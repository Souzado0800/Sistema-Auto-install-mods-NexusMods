"""
Comprehensive automated tests for zero-config onboarding, credential lifecycle,
and secret leakage audit for AutoInstallModMySummerCar.
"""

import io
import json
import logging
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from rich.console import Console

from core.preflight import PreflightChecker
from core.wizard import FirstRunWizard
from credentials.manager import CredentialManager
from nexus.models import UserValidate


@pytest.fixture
def isolated_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate credentials file, OS keyring, and environment variable to temporary directory."""
    config_dir = tmp_path / "user_config"
    cred_file = config_dir / "credentials.json"
    monkeypatch.setattr(CredentialManager, "USER_CONFIG_DIR", config_dir)
    monkeypatch.setattr(CredentialManager, "CREDENTIALS_FILE", cred_file)
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)

    fake_keyring: dict[tuple[str, str], str] = {}

    def mock_get_password(service: str, username: str) -> str | None:
        return fake_keyring.get((service, username))

    def mock_set_password(service: str, username: str, password: str) -> None:
        fake_keyring[(service, username)] = password

    def mock_delete_password(service: str, username: str) -> None:
        fake_keyring.pop((service, username), None)

    monkeypatch.setattr("keyring.get_password", mock_get_password)
    monkeypatch.setattr("keyring.set_password", mock_set_password)
    monkeypatch.setattr("keyring.delete_password", mock_delete_password)
    monkeypatch.setattr("core.wizard.is_gui_available", lambda: False)

    return config_dir, cred_file


@pytest.mark.asyncio
async def test_first_run_without_key_prompts_and_validates(isolated_credentials):
    """
    1. Primeira execução sem chave:
    Simula input do usuário e validação com mock da API oficial do Nexus.
    """
    console_out = io.StringIO()
    console = Console(file=console_out, color_system=None)
    wizard = FirstRunWizard(console)

    secret_key = "first_run_valid_key_12345"
    mock_user = UserValidate(
        user_id=101,
        key=secret_key,
        name="NexusTestPlayer",
        is_premium=True,
        email="player@example.com",
        profile_url="https://nexusmods.com/users/101",
    )

    with (
        patch("webbrowser.open", return_value=True) as mock_browser,
        patch("sys.stdin.isatty", return_value=True),
        patch("getpass.getpass", return_value=secret_key) as mock_getpass,
        patch("nexus.api.NexusApiClient.validate_key", new_callable=AsyncMock, return_value=mock_user),
    ):
        result_key = await wizard.run_wizard_if_needed()

    assert result_key == secret_key
    assert wizard.user_info is not None
    assert wizard.user_info.name == "NexusTestPlayer"
    assert wizard.user_info.is_premium is True
    assert mock_browser.called
    assert mock_getpass.called

    # Confirm key was securely saved to CredentialManager
    saved = CredentialManager.get_api_key()
    assert saved == secret_key


@pytest.mark.asyncio
async def test_valid_key_saved_and_retrieved_silently(isolated_credentials):
    """
    2. Chave válida salva e recuperada corretamente:
    Na segunda execução, valida silenciosamente sem abrir navegador e sem pedir input.
    """
    secret_key = "pre_saved_valid_key_99999"
    CredentialManager.save_api_key(secret_key)

    console_out = io.StringIO()
    console = Console(file=console_out, color_system=None)
    wizard = FirstRunWizard(console)

    mock_user = UserValidate(
        user_id=202,
        key=secret_key,
        name="SilentUser",
        is_premium=False,
        email="silent@example.com",
        profile_url="https://nexusmods.com/users/202",
    )

    with (
        patch("webbrowser.open", side_effect=AssertionError("Browser opened unexpectedly")),
        patch("getpass.getpass", side_effect=AssertionError("getpass called unexpectedly")),
        patch("nexus.api.NexusApiClient.validate_key", new_callable=AsyncMock, return_value=mock_user),
    ):
        result_key = await wizard.run_wizard_if_needed()

    assert result_key == secret_key
    assert wizard.user_info is not None
    assert wizard.user_info.name == "SilentUser"
    # Ensure setup panel was NOT displayed
    assert "CONFIGURAÇÃO DO NEXUS MODS" not in console_out.getvalue()


@pytest.mark.asyncio
async def test_invalid_key_rejected_with_retry(isolated_credentials):
    """
    3. Chave inválida rejeitada com retry:
    Informa amigavelmente 'API KEY INVÁLIDA' e permite tentar novamente.
    """
    console_out = io.StringIO()
    console = Console(file=console_out, color_system=None)
    wizard = FirstRunWizard(console)

    bad_key = "invalid_rejected_key_00000"
    good_key = "good_retry_key_11111"

    mock_user = UserValidate(
        user_id=303,
        key=good_key,
        name="RetryUser",
        is_premium=False,
        email="retry@example.com",
        profile_url="",
    )

    mock_responses = [
        httpx.HTTPStatusError("401 Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)),
        mock_user,
    ]

    async def mock_validate_side_effect():
        resp = mock_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    with (
        patch("webbrowser.open", return_value=True),
        patch("sys.stdin.isatty", return_value=True),
        patch("getpass.getpass", side_effect=[bad_key, good_key]),
        patch("nexus.api.NexusApiClient.validate_key", side_effect=mock_validate_side_effect),
    ):
        result_key = await wizard.run_wizard_if_needed()

    assert result_key == good_key
    assert wizard.user_info.name == "RetryUser"
    output = console_out.getvalue()
    assert "API KEY INVÁLIDA" in output
    assert "rejeitou a chave informada" in output
    assert "Autenticação Nexus Mods concluída" in output
    assert CredentialManager.get_api_key() == good_key


@pytest.mark.asyncio
async def test_revoked_key_detected_at_startup_triggers_wizard(isolated_credentials):
    """
    4. Chave revogada/expirada detectada no início:
    Detecta chave inválida previamente salva, deleta a chave corrompida,
    mostra aviso e abre o wizard para input da nova chave.
    """
    old_key = "revoked_old_key_555"
    CredentialManager.save_api_key(old_key)

    new_key = "new_active_key_777"
    mock_user = UserValidate(
        user_id=404,
        key=new_key,
        name="RecoveredUser",
        is_premium=True,
        email="rec@example.com",
        profile_url="",
    )

    call_count = 0

    async def mock_validate_logic():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call tests the stored old key -> fails (revoked)
            raise httpx.HTTPStatusError("403 Forbidden", request=MagicMock(), response=MagicMock(status_code=403))
        # Second call tests the newly entered key -> succeeds
        return mock_user

    console_out = io.StringIO()
    console = Console(file=console_out, color_system=None)
    wizard = FirstRunWizard(console)

    with (
        patch("webbrowser.open", return_value=True),
        patch("sys.stdin.isatty", return_value=True),
        patch("getpass.getpass", return_value=new_key),
        patch("nexus.api.NexusApiClient.validate_key", side_effect=mock_validate_logic),
    ):
        result_key = await wizard.run_wizard_if_needed()

    assert result_key == new_key
    assert wizard.user_info.name == "RecoveredUser"
    assert CredentialManager.get_api_key() == new_key
    output = console_out.getvalue()
    assert "inválida ou revogada" in output
    assert "CONFIGURAÇÃO DO NEXUS MODS" in output


def test_keyring_unavailable_fallback_to_0600_file(isolated_credentials):
    """
    5. Fallback quando keyring do sistema não estiver disponível:
    Grava com segurança no arquivo protegido 0600 em ~/.config/AutoInstallModMySummerCar/credentials.json.
    """
    _, cred_file = isolated_credentials
    fallback_key = "secret_fallback_key_333"

    with patch("keyring.set_password", side_effect=RuntimeError("Keyring daemon unreachable")):
        with patch("keyring.get_password", side_effect=RuntimeError("Keyring daemon unreachable")):
            saved = CredentialManager.save_api_key(fallback_key)
            assert saved is True
            assert cred_file.exists()

            # Verify permissions
            mode = cred_file.stat().st_mode & 0o777
            assert mode == 0o600, f"Expected 0600 file mode, got {oct(mode)}"

            # Verify directory permissions
            dir_mode = cred_file.parent.stat().st_mode & 0o777
            assert dir_mode == 0o700, f"Expected 0700 dir mode, got {oct(dir_mode)}"

            # Verify retrieval
            retrieved = CredentialManager.get_api_key()
            assert retrieved == fallback_key


@pytest.mark.asyncio
async def test_browser_open_failure_graceful_fallback(isolated_credentials):
    """
    6. Comportamento se o navegador não abrir:
    Fallback graceful exibe URL oficial no console e aguarda input sem quebrar a execução.
    """
    console_out = io.StringIO()
    console = Console(file=console_out, color_system=None)
    wizard = FirstRunWizard(console)

    secret_key = "browser_fail_key_444"
    mock_user = UserValidate(
        user_id=505,
        key=secret_key,
        name="NoBrowserUser",
        is_premium=False,
        email="nobrowser@example.com",
        profile_url="",
    )

    with (
        patch("webbrowser.open", side_effect=Exception("Failed to launch xdg-open: no display")),
        patch("sys.stdin.isatty", return_value=True),
        patch("getpass.getpass", return_value=secret_key),
        patch("nexus.api.NexusApiClient.validate_key", new_callable=AsyncMock, return_value=mock_user),
    ):
        result_key = await wizard.run_wizard_if_needed()

    assert result_key == secret_key
    output = console_out.getvalue()
    assert "https://www.nexusmods.com/users/myaccount?tab=api" in output
    assert "Não foi possível abrir o navegador automaticamente" in output


@pytest.mark.asyncio
async def test_wizard_reopen_option_and_cancel_option(isolated_credentials):
    """
    Testa opções [R] (reabrir navegador) e [Q] (cancelar configuração).
    """
    # 1. Test [R] Reopen followed by valid key
    console_out = io.StringIO()
    console = Console(file=console_out, color_system=None)
    wizard = FirstRunWizard(console)
    valid_key = "key_after_reopen_123"
    mock_user = UserValidate(user_id=601, key=valid_key, name="ReopenUser", is_premium=False, email="", profile_url="")

    with (
        patch("webbrowser.open", return_value=True) as mock_open,
        patch("sys.stdin.isatty", return_value=True),
        patch("getpass.getpass", side_effect=["r", valid_key]),
        patch("nexus.api.NexusApiClient.validate_key", new_callable=AsyncMock, return_value=mock_user),
    ):
        result = await wizard.run_wizard_if_needed()

    assert result == valid_key
    assert mock_open.call_count == 2  # Once initially, once on 'r'
    assert "Reabrindo a página do Nexus Mods" in console_out.getvalue()

    # 2. Test [Q] Cancel
    CredentialManager.delete_api_key()
    console_out_q = io.StringIO()
    wizard_q = FirstRunWizard(Console(file=console_out_q, color_system=None))

    with (
        patch("webbrowser.open", return_value=True),
        patch("sys.stdin.isatty", return_value=True),
        patch("getpass.getpass", return_value="q"),
    ):
        result_q = await wizard_q.run_wizard_if_needed()

    assert result_q is None
    assert "cancelada pelo usuário" in console_out_q.getvalue()


@pytest.mark.asyncio
async def test_leak_audit_no_key_in_stdout_stderr_logs_sqlite_config(isolated_credentials, tmp_path: Path):
    """
    7. Nenhuma chave vazando em stdout, stderr, logs, banco sqlite ou config.json de teste.
    Auditoria rigorosa de vazamento de segredo.
    """
    confidential_key = "ULTRA_SENSITIVE_NEXUS_API_KEY_xyz987654321"

    # Setup isolated directories
    data_dir = tmp_path / "data"
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True)
    db_file = data_dir / "database.sqlite"
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"nexus_api_key": ""}, indent=2))

    # Configure logger capturing to file
    log_file = log_dir / "app.log"
    file_handler = logging.FileHandler(log_file)
    logger = logging.getLogger()
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)

    console_out = io.StringIO()
    console = Console(file=console_out, color_system=None)
    wizard = FirstRunWizard(console)

    mock_user = UserValidate(
        user_id=606,
        key=confidential_key,
        name="SecurityAuditor",
        is_premium=True,
        email="sec@audit.test",
        profile_url="",
    )

    with (
        patch("webbrowser.open", return_value=True),
        patch("sys.stdin.isatty", return_value=True),
        patch("getpass.getpass", return_value=confidential_key),
        patch("nexus.api.NexusApiClient.validate_key", new_callable=AsyncMock, return_value=mock_user),
    ):
        key = await wizard.run_wizard_if_needed(config_path=config_file)

    assert key == confidential_key

    # Initialize sqlite test database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE installed_mods (id INTEGER PRIMARY KEY, name TEXT, version TEXT)")
    cursor.execute("INSERT INTO installed_mods (id, name, version) VALUES (?, ?, ?)", (868, "Lights On Switches", "2.0"))
    conn.commit()
    conn.close()

    # Preflight check with api key
    preflight = PreflightChecker(
        mods_dir=tmp_path / "Mods",
        data_dir=data_dir,
        staging_dir=tmp_path / "staging",
        api_key=confidential_key,
    )
    result = await preflight.run_all(skip_network=True)
    assert result.passed

    # Flush logging
    file_handler.flush()
    file_handler.close()
    logger.removeHandler(file_handler)

    # 1. Audit stdout / console output
    captured_stdout = console_out.getvalue()
    assert confidential_key not in captured_stdout, "CONFIDENTIAL KEY LEAKED TO CONSOLE STDOUT!"

    # 2. Audit config.json
    config_content = config_file.read_text(encoding="utf-8")
    assert confidential_key not in config_content, "CONFIDENTIAL KEY LEAKED TO CONFIG.JSON!"

    # 3. Audit log files
    for log_path in log_dir.glob("*.log"):
        log_text = log_path.read_text(encoding="utf-8", errors="ignore")
        assert confidential_key not in log_text, f"CONFIDENTIAL KEY LEAKED TO LOG FILE {log_path.name}!"

    # 4. Audit sqlite database
    db_raw_bytes = db_file.read_bytes()
    assert confidential_key.encode("utf-8") not in db_raw_bytes, "CONFIDENTIAL KEY LEAKED TO SQLITE DB!"

    # 5. Verify redaction function
    redacted = CredentialManager.redact(f"Failed with key {confidential_key} in query", confidential_key)
    assert confidential_key not in redacted
    assert "[REDACTED_API_KEY]" in redacted
