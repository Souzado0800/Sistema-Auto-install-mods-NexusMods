"""Tests for startup filesystem scanner distinguishing Managed vs Unmanaged files."""

from pathlib import Path

from database.repositories import InstallationRepository, UnmanagedRepository
from installer.scanner import StartupScanner


def test_startup_scanner_unmanaged_detection(repositories, temp_dir: Path):
    inst_repo: InstallationRepository = repositories["installation"]
    unmanaged_repo: UnmanagedRepository = repositories["unmanaged"]

    mods_dir = temp_dir / "Mods"
    mods_dir.mkdir()

    # Create pre-existing files (e.g. MSCLoader_Settings)
    f1 = mods_dir / "ExistingMod.dll"
    f1.write_bytes(b"EXISTING_DLL_DATA")

    assets_dir = mods_dir / "Assets" / "MSCLoader_Settings"
    assets_dir.mkdir(parents=True)
    f2 = assets_dir / "settingsui.unity3d"
    f2.write_bytes(b"UNITY_ASSET_DATA")

    scanner = StartupScanner(
        mods_dir=mods_dir,
        inst_repo=inst_repo,
        unmanaged_repo=unmanaged_repo,
        game_domain="mysummercar",
    )

    summary = scanner.scan()

    assert summary.total_files == 2
    assert summary.managed_files_count == 0
    assert summary.unmanaged_files_count == 2
    assert summary.dll_count == 1

    # Verify recorded in database
    unmanaged_db = unmanaged_repo.list_unmanaged_files("mysummercar")
    assert len(unmanaged_db) == 2
    recorded_paths = [r["relative_path"] for r in unmanaged_db]
    assert "ExistingMod.dll" in recorded_paths
    assert "Assets/MSCLoader_Settings/settingsui.unity3d" in recorded_paths
