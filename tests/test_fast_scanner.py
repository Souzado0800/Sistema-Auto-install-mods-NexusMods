"""Tests for incremental fast scan using cached file size/mtime."""

from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import InstallationRepository, UnmanagedRepository
from installer.scanner import StartupScanner


def test_fast_scanner_caches_unchanged_files(tmp_path):
    db_file = tmp_path / "test.sqlite"
    db = DatabaseConnection(db_file)
    init_db(db)

    inst_repo = InstallationRepository(db)
    unmanaged_repo = UnmanagedRepository(db)

    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    file1 = mods_dir / "ExistingMod.dll"
    file1.write_bytes(b"EXISTING_MOD_BYTES_123")

    scanner = StartupScanner(mods_dir, inst_repo, unmanaged_repo, game_domain="mysummercar")

    # Run 1: First scan (computes hash)
    summary1 = scanner.scan()
    assert summary1.total_files == 1
    assert summary1.unmanaged_files_count == 1
    sha1 = summary1.unmanaged_files[0]["sha256"]

    # Run 2: Unchanged file (uses cached hash)
    summary2 = scanner.scan()
    assert summary2.total_files == 1
    assert summary2.unmanaged_files[0]["sha256"] == sha1

    # Run 3: Modified file (recomputes hash)
    file1.write_bytes(b"DIFFERENT_MOD_BYTES_45678")
    summary3 = scanner.scan()
    sha3 = summary3.unmanaged_files[0]["sha256"]
    assert sha3 != sha1
