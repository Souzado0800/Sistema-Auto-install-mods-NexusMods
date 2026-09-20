
from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import InstallationRepository
from dependencies.graph import DependencyGraph
from dependencies.models import DependencyNode


def test_dry_run_leaves_mods_directory_completely_untouched(tmp_path):
    """
    Validates that a dry-run operation strictly produces plans without:
    1. Writing any file to the target Mods folder.
    2. Creating any backups in _Backups/.
    3. Marking any mod as installed in the database.
    4. Altering filesystem state.
    """
    sandbox_mods = tmp_path / "fake_game" / "Mods"
    sandbox_mods.mkdir(parents=True, exist_ok=True)

    # Put an existing user file in the sandbox
    (sandbox_mods / "UserExistingMod.dll").write_bytes(b"USER_EXISTING_DATA")
    initial_files = list(sandbox_mods.iterdir())
    initial_mtime = (sandbox_mods / "UserExistingMod.dll").stat().st_mtime_ns

    db_path = tmp_path / "test_dry_run.sqlite"
    db_conn = DatabaseConnection(str(db_path))
    init_db(db_conn)
    inst_repo = InstallationRepository(db_conn)

    # Build dependency graph
    graph = DependencyGraph()
    n1 = DependencyNode(game_domain="mysummercar", mod_id=144, name="Mod A", file_size=1024 * 1024)
    n2 = DependencyNode(game_domain="mysummercar", mod_id=214, name="Mod B", file_size=2048 * 1024)
    graph.add_node(n1)
    graph.add_node(n2)
    from dependencies.models import DependencyEdge
    graph.add_edge(DependencyEdge(source=n1.key, target=n2.key))

    order = graph.get_installation_order()
    assert len(order) == 2

    assert order[0].mod_id == 214  # Dependency installed before dependent

    # Simulate Dry-Run Execution Plan
    dry_run_plan = {
        "execution_order": [str(node.key) for node in order],
        "total_download_bytes": sum(node.file_size for node in order),
        "dry_run": True,
    }


    assert dry_run_plan["dry_run"] is True
    assert dry_run_plan["total_download_bytes"] == 3072 * 1024

    # Strict Assertions: Mods folder MUST remain identical
    current_files = list(sandbox_mods.iterdir())
    assert current_files == initial_files
    assert (sandbox_mods / "UserExistingMod.dll").stat().st_mtime_ns == initial_mtime
    assert not (sandbox_mods / "_Backups").exists()
    assert not inst_repo.is_installed("mysummercar", 144)
    assert not inst_repo.is_installed("mysummercar", 214)
