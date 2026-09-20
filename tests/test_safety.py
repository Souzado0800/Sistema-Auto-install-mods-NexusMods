"""Tests for security policies: Zip Slip path traversal guard and executable blocker."""

import io
import zipfile
from pathlib import Path

from installer.backup import BackupManager
from installer.extractor import SafeArchiveExtractor


def test_zip_slip_path_traversal_blocked(temp_dir: Path):
    """Verify that an archive containing relative path traversal (Zip Slip) is rejected."""
    target_install_dir = temp_dir / "mods_dir"
    target_install_dir.mkdir()

    # Craft an evil ZIP with relative path traversal
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../../evil_payload.txt", "Malicious content escaping sandbox!")
        zf.writestr("normal.txt", "Normal content")
    evil_zip = temp_dir / "evil.zip"
    evil_zip.write_bytes(buffer.getvalue())

    extractor = SafeArchiveExtractor()
    result = extractor.extract(evil_zip, target_install_dir)

    # Must fail extraction
    assert not result.success
    assert "Path traversal detected" in str(result.error_message)

    # Verify no file was written outside target directory
    assert not (temp_dir / "evil_payload.txt").exists()


def test_executable_detection(temp_dir: Path):
    """Verify that dangerous executables (.exe, .bat, .sh) are detected and flagged."""
    target_dir = temp_dir / "game_dir"
    target_dir.mkdir()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("scripts/setup.bat", "echo harmful")
        zf.writestr("bin/patcher.exe", "MZ...")
        zf.writestr("textures/sky.dds", "DDS texture data")
    test_zip = temp_dir / "mod_with_binaries.zip"
    test_zip.write_bytes(buffer.getvalue())

    extractor = SafeArchiveExtractor()
    result = extractor.extract(test_zip, target_dir)

    assert result.success
    assert len(result.executables_detected) == 2
    assert "scripts/setup.bat" in result.executables_detected
    assert "bin/patcher.exe" in result.executables_detected


def test_backup_and_rollback(temp_dir: Path):
    """Verify that existing files are backed up before overwrite, and rollback restores them."""
    game_dir = temp_dir / "game"
    game_dir.mkdir()
    target_file = game_dir / "config.ini"
    target_file.write_text("ORIGINAL_VERSION_1")

    backup_dir = temp_dir / "backups"
    backup_mgr = BackupManager(backup_dir)

    # Create archive with updated file
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("config.ini", "MODIFIED_VERSION_2")
    mod_zip = temp_dir / "mod.zip"
    mod_zip.write_bytes(buffer.getvalue())

    extractor = SafeArchiveExtractor(backup_manager=backup_mgr)
    result = extractor.extract(mod_zip, game_dir)

    assert result.success
    assert target_file.read_text() == "MODIFIED_VERSION_2"

    # Rollback
    backup_mgr.rollback()
    assert target_file.read_text() == "ORIGINAL_VERSION_1"
