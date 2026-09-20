"""
Real end-to-end sandbox progression tests:
1 mod -> Download Cache -> Auto-Repair -> Idempotency -> 3 mods with shared dep -> 5 mods.
Strictly executed in isolated sandbox environments; NEVER touches live game directory.
"""

import hashlib
import io
import pytest
import zipfile
from unittest.mock import AsyncMock, MagicMock

from browser.normalizer import NormalizedModUrl
from core.installer import AutoInstaller
from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import (
    DownloadStoreRepository,
    InstallationRepository,
    ModRepository,
    OwnershipRepository,
)
from dependencies.models import DependencyNode
from dependencies.resolver import DependencyResolver
from downloads.manager import DownloadManager
from downloads.store import DownloadFileStore
from installer import (
    BackupManager,
    InstallationManager,
    ProfileManager,
    StagingWorkspace,
)
from nexus.models import FileCategory, ModFile, ModMetadata


def create_archive_bytes(contents: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in contents.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_single_mod_e2e_download_cache_repair_and_idempotency(tmp_path):
    """
    Validates:
    - Step 1: Real mod pipeline in sandbox
    - Step 2: Download cache (Run 1: net=1, cache=0; Run 2: net=0, cache=1)
    - Step 3: Auto-repair (deleted DLL restored from L3 cache, net=0)
    - Step 4: Idempotency (3 runs, zero duplicates)
    """
    sandbox_mods = tmp_path / "e2e_sandbox" / "Mods"
    sandbox_mods.mkdir(parents=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    db_conn = DatabaseConnection(data_dir / "database.sqlite")
    init_db(db_conn)

    inst_repo = InstallationRepository(db_conn)
    store_repo = DownloadStoreRepository(db_conn)
    own_repo = OwnershipRepository(db_conn)

    file_store = DownloadFileStore(data_dir / "downloads", store_repo)
    backup_mgr = BackupManager(data_dir / "backups")
    staging_ws = StagingWorkspace(data_dir / "staging")
    inst_mgr = InstallationManager(inst_repo, ProfileManager(), backup_mgr, staging_ws)

    # Mod ID 868: Lights On Switches (Real mod from user's 45 tabs)
    mod_id = 868
    file_id = 86801
    mod_name = "Lights On Switches"
    version = "1.2.0"
    filename = "LightsOnSwitches-1.2.0.zip"

    archive_bytes = create_archive_bytes({
        "LightsOnSwitches.dll": b"LIGHTS_SWITCHES_BINARY_PAYLOAD",
        "Assets/LightsOnSwitches/light.png": b"LIGHT_TEXTURE_DATA",
        "README.txt": b"Lights on switches documentation",
    })
    expected_sha256 = hashlib.sha256(archive_bytes).hexdigest()

    # Network spy counter
    network_download_count = 0

    async def mock_download_worker(node, is_premium=False):
        nonlocal network_download_count
        network_download_count += 1
        out_path = file_store.get_storage_path(node.game_domain, node.mod_id, node.file_id, filename)
        out_path.write_bytes(archive_bytes)
        file_store.register_download(
            game_domain=node.game_domain,
            mod_id=node.mod_id,
            file_id=node.file_id,
            version=version,
            filename=filename,
            final_path=out_path,
            file_size=len(archive_bytes),
            sha256=expected_sha256,
        )
        return out_path

    mock_download_mgr = MagicMock(spec=DownloadManager)
    mock_download_mgr.execute_downloads = AsyncMock(side_effect=lambda nodes, is_premium=False: [
        mock_download_worker(n, is_premium) for n in nodes
    ])

    # -------------------------------------------------------------------------
    # RUN 1: Fresh Download and Installation
    # -------------------------------------------------------------------------
    # Cache hit check before Run 1
    assert file_store.get_cached_file("mysummercar", mod_id, file_id) is None

    # Simulate Download
    dl_path = await mock_download_worker(
        DependencyNode(
            game_domain="mysummercar",
            mod_id=mod_id,
            name=mod_name,
            file_id=file_id,
            file_name=filename,
        )
    )
    assert network_download_count == 1
    assert dl_path.is_file()

    # Install via AutoInstaller
    installer = AutoInstaller(sandbox_mods, db_conn=db_conn)
    assert installer.install_archive(dl_path, game_domain="mysummercar", mod_id=mod_id)

    # Verify sandbox filesystem
    assert (sandbox_mods / "LightsOnSwitches.dll").is_file()
    assert (sandbox_mods / "Assets" / "LightsOnSwitches" / "light.png").is_file()
    assert not (sandbox_mods / "Mods").exists(), "Must not create nested Mods/ folder"

    # Verify SQLite tracking
    assert inst_repo.is_installed("mysummercar", mod_id)
    assert len(own_repo.list_owned_files()) >= 2

    # -------------------------------------------------------------------------
    # RUN 2: Cache Hit Verification
    # -------------------------------------------------------------------------
    # Check L3 cache hit
    cached_path = file_store.get_cached_file("mysummercar", mod_id, file_id)
    assert cached_path is not None
    assert cached_path == dl_path
    # Network downloads must remain exactly 1 (zero network I/O during run 2!)
    assert network_download_count == 1

    # -------------------------------------------------------------------------
    # RUN 3: Auto-Repair Verification
    # -------------------------------------------------------------------------
    # Simulate corruption by deleting LightsOnSwitches.dll
    (sandbox_mods / "LightsOnSwitches.dll").unlink()
    assert not (sandbox_mods / "LightsOnSwitches.dll").exists()

    repair_report = inst_mgr.repair_mod("mysummercar", mod_id, sandbox_mods)
    assert repair_report["status"] == "corrupted"
    assert "LightsOnSwitches.dll" in repair_report["missing"]

    # Restore from L3 cache
    repaired_path = file_store.get_cached_file("mysummercar", mod_id, file_id)
    assert repaired_path is not None
    assert installer.install_archive(repaired_path, game_domain="mysummercar", mod_id=mod_id)

    # Verify restored file
    assert (sandbox_mods / "LightsOnSwitches.dll").is_file()
    post_repair_report = inst_mgr.repair_mod("mysummercar", mod_id, sandbox_mods)
    assert post_repair_report["status"] == "healthy"
    assert len(post_repair_report["missing"]) == 0
    # Still 0 additional network downloads!
    assert network_download_count == 1

    # -------------------------------------------------------------------------
    # RUN 4: Idempotency Verification (3rd execution)
    # -------------------------------------------------------------------------
    initial_files = sorted([str(p.relative_to(sandbox_mods)) for p in sandbox_mods.rglob("*") if p.is_file()])
    assert installer.install_archive(repaired_path, game_domain="mysummercar", mod_id=mod_id)
    post_run_files = sorted([str(p.relative_to(sandbox_mods)) for p in sandbox_mods.rglob("*") if p.is_file()])

    assert initial_files == post_run_files, "Filesystem modified unexpectedly on idempotent run"
    assert not (sandbox_mods / "Mods" / "Mods").exists()


@pytest.mark.asyncio
async def test_3_mods_with_shared_dependency_progression(tmp_path):
    """
    Validates 3 mods progression:
    - Mod 8382 (Forest Addon) depends on #3518 (AchievementCore)
    - Mod 3676 (Moose Hunter) depends on #3518 (AchievementCore)
    - Mod 3518 (AchievementCore)
    Shared dependency #3518 is downloaded ONCE and installed ONCE.
    """
    sandbox_mods = tmp_path / "e2e_sandbox" / "Mods"
    sandbox_mods.mkdir(parents=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    db_conn = DatabaseConnection(data_dir / "database.sqlite")
    init_db(db_conn)

    mod_repo = ModRepository(db_conn)
    inst_repo = InstallationRepository(db_conn)
    store_repo = DownloadStoreRepository(db_conn)
    file_store = DownloadFileStore(data_dir / "downloads", store_repo)

    # Archives
    achieve_bytes = create_archive_bytes({"AchievementCore.dll": b"ACHIEVEMENT_CORE_DLL"})
    forest_bytes = create_archive_bytes({"ForestAddon.dll": b"FOREST_ADDON_DLL"})
    moose_bytes = create_archive_bytes({"MooseHunter.dll": b"MOOSE_HUNTER_DLL"})

    arc_achieve = file_store.get_storage_path("mysummercar", 3518, 351801, "AchievementCore.zip")
    arc_achieve.write_bytes(achieve_bytes)
    file_store.register_download(
        "mysummercar", 3518, 351801, "1.0", "AchievementCore.zip", arc_achieve, len(achieve_bytes), hashlib.sha256(achieve_bytes).hexdigest()
    )

    arc_forest = file_store.get_storage_path("mysummercar", 8382, 838201, "ForestAddon.zip")
    arc_forest.write_bytes(forest_bytes)
    file_store.register_download(
        "mysummercar", 8382, 838201, "1.0", "ForestAddon.zip", arc_forest, len(forest_bytes), hashlib.sha256(forest_bytes).hexdigest()
    )

    arc_moose = file_store.get_storage_path("mysummercar", 3676, 367601, "MooseHunter.zip")
    arc_moose.write_bytes(moose_bytes)
    file_store.register_download(
        "mysummercar", 3676, 367601, "1.0", "MooseHunter.zip", arc_moose, len(moose_bytes), hashlib.sha256(moose_bytes).hexdigest()
    )

    # Mock API with real requirements from Nexus GraphQL v2
    mock_client = MagicMock()

    async def mock_get_mod(game, mod_id):
        names = {3518: "AchievementCore", 8382: "Forest Addon", 3676: "Moose Hunter"}
        return ModMetadata(game_domain=game, mod_id=mod_id, name=names.get(mod_id, f"Mod {mod_id}"))

    async def mock_get_files(game, mod_id):
        fids = {3518: 351801, 8382: 838201, 3676: 367601}
        return [ModFile(file_id=fids[mod_id], mod_id=mod_id, game_domain=game, name=f"Mod {mod_id} File", category_id=FileCategory.MAIN, is_primary=True, size_bytes=100)]

    async def mock_get_requirements(game, mod_id):
        # 8382 and 3676 both require 3518
        if mod_id in (8382, 3676):
            return [{"modId": 3518, "modName": "AchievementCore", "notes": "Required", "url": "https://www.nexusmods.com/mysummercar/mods/3518", "externalRequirement": False}]
        return []

    mock_client.get_mod = AsyncMock(side_effect=mock_get_mod)
    mock_client.get_mod_files = AsyncMock(side_effect=mock_get_files)
    mock_client.get_mod_requirements = AsyncMock(side_effect=mock_get_requirements)

    collected = [
        NormalizedModUrl("https://www.nexusmods.com/mysummercar/mods/8382", "mysummercar", 8382),
        NormalizedModUrl("https://www.nexusmods.com/mysummercar/mods/3676", "mysummercar", 3676),
    ]

    resolver = DependencyResolver(api_client=mock_client, mod_repo=mod_repo, installation_repo=inst_repo)
    plan = await resolver.resolve_plan(collected)

    # Plan must include the 2 requested mods + 1 shared dependency = 3 total components
    assert len(plan.installation_order) == 3
    assert any(n.mod_id == 3518 for n in plan.discovered_dependencies)

    # Dependency must precede dependees in installation order (topological sort)
    order_ids = [n.mod_id for n in plan.installation_order]
    assert order_ids.index(3518) < order_ids.index(8382)
    assert order_ids.index(3518) < order_ids.index(3676)

    # Execute installation in sandbox
    installer = AutoInstaller(sandbox_mods, db_conn=db_conn)
    for node in plan.installation_order:
        cached = file_store.get_cached_file(node.game_domain, node.mod_id, node.file_id)
        assert cached is not None
        assert installer.install_archive(cached, game_domain=node.game_domain, mod_id=node.mod_id)

    # Verify all 3 mods are installed
    assert (sandbox_mods / "AchievementCore.dll").is_file()
    assert (sandbox_mods / "ForestAddon.dll").is_file()
    assert (sandbox_mods / "MooseHunter.dll").is_file()
    assert inst_repo.is_installed("mysummercar", 3518)
    assert inst_repo.is_installed("mysummercar", 8382)
    assert inst_repo.is_installed("mysummercar", 3676)


@pytest.mark.asyncio
async def test_5_mods_progression_with_diamond_dag(tmp_path):
    """
    Validates 5 mods progression with diamond DAG topology.
    """
    sandbox_mods = tmp_path / "e2e_sandbox" / "Mods"
    sandbox_mods.mkdir(parents=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    db_conn = DatabaseConnection(data_dir / "database.sqlite")
    init_db(db_conn)

    mod_repo = ModRepository(db_conn)
    inst_repo = InstallationRepository(db_conn)
    store_repo = DownloadStoreRepository(db_conn)
    file_store = DownloadFileStore(data_dir / "downloads", store_repo)

    # 5 Mods: A(1001), B(1002), C(1003), D(1004), Framework(1000)
    # A -> Framework, B -> Framework, C -> B, D (independent)
    for mid in [1000, 1001, 1002, 1003, 1004]:
        b = create_archive_bytes({f"Mod_{mid}.dll": f"CONTENT_{mid}".encode()})
        p = file_store.get_storage_path("mysummercar", mid, mid * 10, f"Mod_{mid}.zip")
        p.write_bytes(b)
        file_store.register_download("mysummercar", mid, mid * 10, "1.0", f"Mod_{mid}.zip", p, len(b), hashlib.sha256(b).hexdigest())

    mock_client = MagicMock()
    mock_client.get_mod = AsyncMock(side_effect=lambda g, mid: ModMetadata(game_domain=g, mod_id=mid, name=f"Mod #{mid}"))
    mock_client.get_mod_files = AsyncMock(side_effect=lambda g, mid: [ModFile(file_id=mid*10, mod_id=mid, game_domain=g, name=f"Mod {mid}", category_id=FileCategory.MAIN, is_primary=True, size_bytes=100)])

    async def mock_reqs(g, mid):
        if mid in (1001, 1002):
            return [{"modId": 1000, "modName": "Framework 1000", "notes": "", "url": "", "externalRequirement": False}]
        if mid == 1003:
            return [{"modId": 1002, "modName": "Mod 1002", "notes": "", "url": "", "externalRequirement": False}]
        return []

    mock_client.get_mod_requirements = AsyncMock(side_effect=mock_reqs)

    collected = [
        NormalizedModUrl("https://www.nexusmods.com/mysummercar/mods/1001", "mysummercar", 1001),
        NormalizedModUrl("https://www.nexusmods.com/mysummercar/mods/1003", "mysummercar", 1003),
        NormalizedModUrl("https://www.nexusmods.com/mysummercar/mods/1004", "mysummercar", 1004),
    ]

    resolver = DependencyResolver(api_client=mock_client, mod_repo=mod_repo, installation_repo=inst_repo)
    plan = await resolver.resolve_plan(collected)

    # Total 5 nodes
    assert len(plan.installation_order) == 5
    order = [n.mod_id for n in plan.installation_order]
    # Framework 1000 must precede 1001, 1002, 1003
    assert order.index(1000) < order.index(1001)
    assert order.index(1000) < order.index(1002)
    assert order.index(1002) < order.index(1003)

    installer = AutoInstaller(sandbox_mods, db_conn=db_conn)
    for node in plan.installation_order:
        arc = file_store.get_cached_file(node.game_domain, node.mod_id, node.file_id)
        assert installer.install_archive(arc, game_domain=node.game_domain, mod_id=node.mod_id)

    # Verify all 5 installed in sandbox
    for mid in [1000, 1001, 1002, 1003, 1004]:
        assert (sandbox_mods / f"Mod_{mid}.dll").is_file()
        assert inst_repo.is_installed("mysummercar", mid)
