import hashlib
import zipfile
import pytest

from browser.manual import parse_urls_from_text
from core.installer import AutoInstaller

from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import (
    DownloadStoreRepository,
)
from dependencies.graph import DependencyGraph
from dependencies.models import DependencyEdge, DependencyNode, DependencyType
from downloads.store import DownloadFileStore
from nexus.resolver import FileSelectionPolicy
from nexus.models import ModFile, FileCategory


def make_archive_bytes(files: dict[str, bytes]) -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for f, d in files.items():
            zf.writestr(f, d)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_e2e_sandbox_pipeline_progression(tmp_path):
    """
    End-to-End Pipeline test strictly in a sandbox (tmp_path).
    Tests progressively:
    Step A: 1 Mod
    Step B: 3 Mods with linear dependency
    Step C: 5 Mods with diamond dependency graph
    Guarantees: NEVER touches /home/souza/My Summer Car/Mods!
    """
    sandbox_mods = tmp_path / "fake_game" / "Mods"
    sandbox_mods.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "sandbox.sqlite"
    db_conn = DatabaseConnection(str(db_path))
    init_db(db_conn)

    store_repo = DownloadStoreRepository(db_conn)
    store = DownloadFileStore(tmp_path / "downloads", store_repo)
    installer = AutoInstaller(sandbox_mods, db_conn=db_conn)

    # -------------------------------------------------------------
    # STEP A: 1 Mod
    # -------------------------------------------------------------
    raw_urls = ["https://www.nexusmods.com/mysummercar/mods/101?tab=files"]
    canonical_keys = parse_urls_from_text("\n".join(raw_urls))
    assert len(canonical_keys) == 1

    key101 = canonical_keys[0]
    assert key101.game_domain == "mysummercar"
    assert key101.mod_id == 101

    # Simulated official API file metadata
    files_mod101 = [
        ModFile(
            file_id=1001,
            mod_id=101,
            game_domain="mysummercar",
            name="TestMod Main 1.0",
            version="1.0",
            category_id=FileCategory.MAIN,
            category_name="MAIN",
            is_primary=True,
            size_bytes=1024,
            file_name="TestMod_1.0.zip",
            uploaded_timestamp=1680000000,
        )
    ]

    sel_101 = FileSelectionPolicy.select_files(files_mod101)
    assert len(sel_101.selected_files) == 1
    file_to_download = sel_101.selected_files[0]
    assert file_to_download.file_id == 1001

    # Create archive bytes and download into L3 store
    archive_bytes_101 = make_archive_bytes({
        "Mods/TestMod.dll": b"DLL_101_PAYLOAD",
        "Mods/Assets/TestMod/texture.png": b"PNG_101_PAYLOAD",
        "Mods/README.txt": b"Mod 101 readme",
    })
    target_path = store.get_storage_path("mysummercar", 101, 1001, "TestMod_1.0.zip")
    target_path.write_bytes(archive_bytes_101)
    sha256_101 = hashlib.sha256(archive_bytes_101).hexdigest()
    store.register_download("mysummercar", 101, 1001, "1.0", "TestMod_1.0.zip", target_path, len(archive_bytes_101), sha256_101)

    # Install through AutoInstaller
    assert installer.install_archive(target_path, game_domain="mysummercar", mod_id=101)
    assert (sandbox_mods / "TestMod.dll").is_file()
    assert (sandbox_mods / "Assets" / "TestMod" / "texture.png").is_file()
    assert (sandbox_mods / "readme(TestMod).md").is_file()

    # -------------------------------------------------------------
    # STEP B: 3 Mods with linear dependency (Mod 201 depends on Mod 202)
    # -------------------------------------------------------------
    graph3 = DependencyGraph()
    n201 = DependencyNode(game_domain="mysummercar", mod_id=201, name="DependentMod", file_size=2048)
    n202 = DependencyNode(game_domain="mysummercar", mod_id=202, name="CoreLibrary", file_size=1024)
    n203 = DependencyNode(game_domain="mysummercar", mod_id=203, name="StandaloneMod", file_size=4096)
    for n in (n201, n202, n203):
        graph3.add_node(n)
    graph3.add_edge(DependencyEdge(source=n201.key, target=n202.key, dep_type=DependencyType.REQUIRED))

    order3 = graph3.get_installation_order()
    assert len(order3) == 3
    # n202 (CoreLibrary) MUST come before n201 (DependentMod)
    idx_202 = [n.mod_id for n in order3].index(202)
    idx_201 = [n.mod_id for n in order3].index(201)
    assert idx_202 < idx_201

    # Simulate and install all 3 in topological order
    for node in order3:
        arc_bytes = make_archive_bytes({
            f"{node.name}.dll": f"DLL_FOR_{node.name}".encode(),
            f"Assets/{node.name}/data.bin": b"DATA",
        })
        p = store.get_storage_path("mysummercar", node.mod_id, node.mod_id * 10, f"{node.name}.zip")
        p.write_bytes(arc_bytes)
        assert installer.install_archive(p, game_domain="mysummercar", mod_id=node.mod_id)

    assert (sandbox_mods / "CoreLibrary.dll").is_file()
    assert (sandbox_mods / "DependentMod.dll").is_file()
    assert (sandbox_mods / "StandaloneMod.dll").is_file()

    # -------------------------------------------------------------
    # STEP C: 5 Mods with Diamond Dependency Graph
    # Mod 301 -> Mod 302 & Mod 303 -> Mod 304 (Root Framework); Mod 305 (Independent)
    # -------------------------------------------------------------
    graph5 = DependencyGraph()
    nodes5 = [
        DependencyNode(game_domain="mysummercar", mod_id=301, name="TopMod"),
        DependencyNode(game_domain="mysummercar", mod_id=302, name="BranchA"),
        DependencyNode(game_domain="mysummercar", mod_id=303, name="BranchB"),
        DependencyNode(game_domain="mysummercar", mod_id=304, name="SharedRoot"),
        DependencyNode(game_domain="mysummercar", mod_id=305, name="Independent"),
    ]
    for n in nodes5:
        graph5.add_node(n)

    graph5.add_edge(DependencyEdge(source=nodes5[0].key, target=nodes5[1].key))
    graph5.add_edge(DependencyEdge(source=nodes5[0].key, target=nodes5[2].key))
    graph5.add_edge(DependencyEdge(source=nodes5[1].key, target=nodes5[3].key))
    graph5.add_edge(DependencyEdge(source=nodes5[2].key, target=nodes5[3].key))

    order5 = graph5.get_installation_order()
    assert len(order5) == 5

    order_ids = [n.mod_id for n in order5]
    # 304 must precede 302 and 303, which in turn must precede 301
    assert order_ids.index(304) < order_ids.index(302)
    assert order_ids.index(304) < order_ids.index(303)
    assert order_ids.index(302) < order_ids.index(301)
    assert order_ids.index(303) < order_ids.index(301)

    for n in order5:
        arc = make_archive_bytes({f"{n.name}.dll": f"DLL_{n.name}".encode()})
        p = store.get_storage_path("mysummercar", n.mod_id, n.mod_id * 10, f"{n.name}.zip")
        p.write_bytes(arc)
        assert installer.install_archive(p, game_domain="mysummercar", mod_id=n.mod_id)

    assert (sandbox_mods / "SharedRoot.dll").is_file()
    assert (sandbox_mods / "BranchA.dll").is_file()
    assert (sandbox_mods / "BranchB.dll").is_file()
    assert (sandbox_mods / "TopMod.dll").is_file()
    assert (sandbox_mods / "Independent.dll").is_file()
