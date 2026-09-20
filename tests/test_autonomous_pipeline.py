"""End-to-end tests for the 100% autonomous execution pipeline."""

import hashlib
import io
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock

from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import (
    InstallationRepository,
    ModRepository,
    DownloadStoreRepository,
)
from dependencies.resolver import DependencyResolver
from downloads.store import DownloadFileStore
from core.installer import AutoInstaller
from browser.normalizer import NormalizedModUrl
from nexus.models import ModFile, FileCategory, ModMetadata


def make_zip(files_dict: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, data in files_dict.items():
            zf.writestr(fname, data)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_autonomous_idempotency_and_fast_path(tmp_path):
    sandbox_mods = tmp_path / "Mods"
    sandbox_mods.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    db_conn = DatabaseConnection(data_dir / "db.sqlite")
    init_db(db_conn)

    mod_repo = ModRepository(db_conn)
    inst_repo = InstallationRepository(db_conn)
    store_repo = DownloadStoreRepository(db_conn)
    file_store = DownloadFileStore(data_dir / "downloads", store_repo)

    # 1. Create mock mod archive in L3 store
    mod_zip_bytes = make_zip({
        "TestMod.dll": b"DLL_BINARY_CONTENT",
        "Assets/TestMod/texture.png": b"PNG_DATA",
    })
    target_archive = file_store.get_storage_path("mysummercar", 500, 5001, "TestMod-1.0.zip")
    target_archive.write_bytes(mod_zip_bytes)
    real_sha256 = hashlib.sha256(mod_zip_bytes).hexdigest()
    file_store.register_download(
        game_domain="mysummercar",
        mod_id=500,
        file_id=5001,
        version="1.0",
        filename="TestMod-1.0.zip",
        final_path=target_archive,
        file_size=len(mod_zip_bytes),
        sha256=real_sha256,
    )

    # Mock API client with AsyncMock
    mock_client = MagicMock()
    mock_client.get_mod = AsyncMock(return_value=ModMetadata(
        mod_id=500,
        name="TestMod",
        game_domain="mysummercar",
        version="1.0",
        author="Author",
        summary="Summary",
    ))
    mock_client.get_mod_files = AsyncMock(return_value=[
        ModFile(
            file_id=5001,
            mod_id=500,
            game_domain="mysummercar",
            name="TestMod-1.0.zip",
            version="1.0",
            category_id=FileCategory.MAIN,
            is_primary=True,
            size_bytes=len(mod_zip_bytes),
            file_name="TestMod-1.0.zip",
            uploaded_timestamp=1680000000,
        )
    ])
    mock_client.get_mod_dependencies = AsyncMock(return_value=[])

    collected = [
        NormalizedModUrl("https://www.nexusmods.com/mysummercar/mods/500", "mysummercar", 500)
    ]

    resolver = DependencyResolver(
        api_client=mock_client,
        mod_repo=mod_repo,
        installation_repo=inst_repo,
    )

    # RUN 1: Fresh install
    plan1 = await resolver.resolve_plan(collected)
    assert len(plan1.installation_order) == 1
    assert plan1.installation_order[0].is_installed is False

    # Install using AutoInstaller
    installer = AutoInstaller(sandbox_mods, db_conn=db_conn)
    assert installer.install_archive(target_archive, game_domain="mysummercar", mod_id=500)

    assert (sandbox_mods / "TestMod.dll").is_file()
    assert (sandbox_mods / "Assets" / "TestMod" / "texture.png").is_file()

    # RUN 2: Re-run with the exact same tabs
    # Plan resolution should detect that mod 500 is already installed!
    plan2 = await resolver.resolve_plan(collected)
    assert len(plan2.installation_order) == 1
    assert plan2.installation_order[0].is_installed is True
    assert len(plan2.to_download) == 0  # Zero network downloads needed!

    # RUN 3: Auto-Repair simulation
    # Delete TestMod.dll to simulate corruption or accidental deletion
    (sandbox_mods / "TestMod.dll").unlink()
    assert not (sandbox_mods / "TestMod.dll").exists()

    from installer import InstallationManager, ProfileManager, BackupManager, StagingWorkspace
    inst_mgr = InstallationManager(
        inst_repo,
        ProfileManager(),
        BackupManager(data_dir / "backups"),
        StagingWorkspace(data_dir / "staging"),
    )

    report_broken = inst_mgr.repair_mod("mysummercar", 500, sandbox_mods)
    assert report_broken["status"] == "corrupted"
    assert "TestMod.dll" in report_broken["missing"]

    # Reinstall / repair from L3 disk cache archive
    cached_arc = file_store.get_cached_file("mysummercar", 500, 5001)
    assert cached_arc is not None
    assert installer.install_archive(cached_arc, game_domain="mysummercar", mod_id=500)

    # Verification post-repair
    assert (sandbox_mods / "TestMod.dll").is_file()
    report_repaired = inst_mgr.repair_mod("mysummercar", 500, sandbox_mods)
    assert report_repaired["status"] == "healthy"
    assert len(report_repaired["missing"]) == 0
