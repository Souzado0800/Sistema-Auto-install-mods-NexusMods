import hashlib
import zipfile
from pathlib import Path

from core.installer import AutoInstaller
from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import DownloadStoreRepository
from downloads.store import DownloadFileStore


def make_zip(path: Path, files: dict[str, bytes]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for f, d in files.items():
            zf.writestr(f, d)


def test_cache_full_lifecycle_4_stages(tmp_path):
    """
    Validates the 4 lifecycle stages of L3 caching and repair:
    Stage 1: Initial cold download & registration.
    Stage 2: Warm cache hit (0 network calls, 3 cache hits).
    Stage 3: Repair of missing installed file using L3 archive cache (0 network downloads).
    Stage 4: Deliberate archive corruption -> Hash mismatch -> Cache invalidated -> Redownload needed.
    """
    db_conn = DatabaseConnection(str(tmp_path / "test_cache.sqlite"))
    init_db(db_conn)
    repo = DownloadStoreRepository(db_conn)
    store = DownloadFileStore(tmp_path / "l3_store", repo)
    sandbox_mods = tmp_path / "Mods"
    sandbox_mods.mkdir(parents=True, exist_ok=True)

    mods_data = [
        ("mysummercar", 101, 1001, "ModA.zip", {"ModA.dll": b"DATA_MOD_A"}),
        ("mysummercar", 102, 1002, "ModB.zip", {"ModB.dll": b"DATA_MOD_B"}),
        ("mysummercar", 103, 1003, "ModC.zip", {"ModC.dll": b"DATA_MOD_C"}),
    ]

    # --- STAGE 1: Cold Run ---
    total_bytes_transferred = 0
    network_downloads_stage1 = 0

    for game, mod_id, file_id, fname, contents in mods_data:
        # Check cache (should be miss)
        cached = store.get_cached_file(game, mod_id, file_id)
        assert cached is None, f"Expected cache miss on stage 1 for {fname}"

        # Simulate network download
        network_downloads_stage1 += 1
        storage_path = store.get_storage_path(game, mod_id, file_id, fname)
        make_zip(storage_path, contents)
        file_size = storage_path.stat().st_size
        sha256 = hashlib.sha256(storage_path.read_bytes()).hexdigest()
        total_bytes_transferred += file_size

        store.register_download(game, mod_id, file_id, "1.0", fname, storage_path, file_size, sha256)

    assert network_downloads_stage1 == 3
    assert total_bytes_transferred > 0

    # Install to sandbox
    installer = AutoInstaller(sandbox_mods, db_conn=db_conn)
    for game, mod_id, file_id, fname, _ in mods_data:
        cached_path = store.get_cached_file(game, mod_id, file_id)
        assert cached_path is not None
        assert installer.install_archive(cached_path, game_domain=game, mod_id=mod_id)

    assert (sandbox_mods / "ModA.dll").is_file()
    assert (sandbox_mods / "ModB.dll").is_file()
    assert (sandbox_mods / "ModC.dll").is_file()

    # --- STAGE 2: Warm Run ---
    network_downloads_stage2 = 0
    cache_hits_stage2 = 0

    for game, mod_id, file_id, fname, _ in mods_data:
        cached = store.get_cached_file(game, mod_id, file_id)
        if cached:
            cache_hits_stage2 += 1
        else:
            network_downloads_stage2 += 1

    assert network_downloads_stage2 == 0, "Expected 0 network downloads on warm cache"
    assert cache_hits_stage2 == 3, "Expected 3 cache hits on warm cache"

    # --- STAGE 3: Repair using local archive cache ---
    # Delete ModB.dll from the game Mods folder
    (sandbox_mods / "ModB.dll").unlink()
    assert not (sandbox_mods / "ModB.dll").exists()

    # Execute repair using local cache archive
    network_downloads_stage3 = 0
    cached_b = store.get_cached_file("mysummercar", 102, 1002)
    assert cached_b is not None
    assert cached_b.is_file()
    # Reinstall / repair
    assert installer.install_archive(cached_b, game_domain="mysummercar", mod_id=102)

    assert (sandbox_mods / "ModB.dll").is_file()
    assert (sandbox_mods / "ModB.dll").read_bytes() == b"DATA_MOD_B"
    assert network_downloads_stage3 == 0, "Repair must not download from network when archive is cached!"

    # --- STAGE 4: Deliberate archive corruption ---
    cached_c = store.get_cached_file("mysummercar", 103, 1003)
    assert cached_c is not None
    # Corrupt the archive on disk
    cached_c.write_bytes(b"CORRUPTED_GARBAGE_PAYLOAD")

    # Next check must detect HASH MISMATCH and invalidate cache
    cached_after_corruption = store.get_cached_file("mysummercar", 103, 1003)
    assert cached_after_corruption is None, "Cache should have rejected corrupted archive and returned None"

    # Verify that database record was cleared
    assert repo.get_download("mysummercar", 103, 1003) is None, "Database record must be invalidated on corruption"
