"""Tests for SQLite persistence, manifest tracking, and mod repair auditing."""

from pathlib import Path

from database.repositories import (
    InstallationRepository,
    ModRepository,
    QueueRepository,
)
from installer.manager import InstallationManager
from utils.hashing import compute_file_hash


def test_sqlite_wal_mode(test_db):
    conn = test_db.get_connection()
    row = conn.execute("PRAGMA journal_mode;").fetchone()
    assert row[0].lower() == "wal"


def test_mod_and_queue_repositories(repositories):
    mod_repo: ModRepository = repositories["mod"]
    queue_repo: QueueRepository = repositories["queue"]

    # Upsert mod
    mod_repo.upsert_mod({
        "game_domain": "skyrimspecialedition",
        "mod_id": 32444,
        "name": "Address Library for SKSE Plugins",
        "author": "meh321",
        "version": "8.0",
    })
    mod = mod_repo.get_mod("skyrimspecialedition", 32444)
    assert mod is not None
    assert mod["name"] == "Address Library for SKSE Plugins"

    # Queue item
    queue_repo.upsert_item({
        "game_domain": "skyrimspecialedition",
        "mod_id": 32444,
        "file_id": 100200,
        "file_name": "address_library.zip",
        "file_size": 50000,
        "status": "WAITING",
    })
    waiting = queue_repo.get_items_by_status(["WAITING"])
    assert len(waiting) == 1

    queue_repo.update_status("skyrimspecialedition", 32444, 100200, "DOWNLOADING")
    downloading = queue_repo.get_items_by_status(["DOWNLOADING"])
    assert len(downloading) == 1

    # Reset in-flight back to WAITING
    queue_repo.reset_in_flight()
    assert len(queue_repo.get_items_by_status(["DOWNLOADING"])) == 0
    assert len(queue_repo.get_items_by_status(["WAITING"])) == 1


def test_installation_manifest_and_repair(repositories, temp_dir: Path):
    inst_repo: InstallationRepository = repositories["installation"]
    inst_mgr = InstallationManager(inst_repo)

    game_dir = temp_dir / "game"
    game_dir.mkdir()

    # Create dummy installed files
    f1 = game_dir / "plugins" / "skse.dll"
    f1.parent.mkdir(parents=True)
    f1.write_bytes(b"VALID_CONTENT_1")

    f2 = game_dir / "plugins" / "data.bin"
    f2.write_bytes(b"VALID_CONTENT_2")

    f1_hash = compute_file_hash(f1, "sha256")
    f2_hash = compute_file_hash(f2, "sha256")

    manifest = [
        {"relative_path": "plugins/skse.dll", "file_size": len(b"VALID_CONTENT_1"), "sha256": f1_hash},
        {"relative_path": "plugins/data.bin", "file_size": len(b"VALID_CONTENT_2"), "sha256": f2_hash},
    ]

    inst_repo.record_installation(
        game_domain="skyrim",
        mod_id=555,
        file_id=1,
        mod_name="SKSE Plugin",
        version="1.0",
        profile="generic",
        install_dir=str(game_dir),
        manifest=manifest,
    )

    # 1. Test healthy state
    report = inst_mgr.repair_mod("skyrim", 555, game_dir)
    assert report["status"] == "healthy"
    assert report["valid_count"] == 2
    assert len(report["missing"]) == 0
    assert len(report["modified"]) == 0

    # 2. Simulate deleted file (missing)
    f2.unlink()
    report = inst_mgr.repair_mod("skyrim", 555, game_dir)
    assert report["status"] == "corrupted"
    assert "plugins/data.bin" in report["missing"]

    # 3. Simulate modified file (modified)
    f1.write_bytes(b"CORRUPTED_OR_TAMPERED_DATA")
    report = inst_mgr.repair_mod("skyrim", 555, game_dir)
    assert report["status"] == "corrupted"
    assert "plugins/skse.dll" in report["modified"]
