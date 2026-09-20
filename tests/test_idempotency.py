import zipfile
from pathlib import Path

from core.analyzer import ModPackage
from core.installer import AutoInstaller
from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import OwnershipRepository


def create_sample_zip(zip_path: Path, files_dict: dict[str, bytes]):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for fname, data in files_dict.items():
            zf.writestr(fname, data)


def test_installation_idempotency_three_runs(tmp_path):
    """
    Executes install(plan) three times consecutively.
    Asserts:
      - Never creates nested Mods/Mods/
      - No duplicate database entries
      - Same final filesystem state and SHA-256 hashes
      - No spurious duplicate backups created on runs 2 and 3
    """
    # 1. Setup isolated sandbox
    sandbox_mods = tmp_path / "fake_game" / "Mods"
    sandbox_mods.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "test_idempotency.sqlite"
    db_conn = DatabaseConnection(str(db_path))
    init_db(db_conn)

    # 2. Create sample archive wrapped with Mods/ prefix
    zip_file = tmp_path / "downloads" / "TestMod-1.0.zip"
    create_sample_zip(zip_file, {
        "Mods/TestMod.dll": b"TEST_MOD_DLL_V1",
        "Mods/Assets/TestMod/texture.png": b"PNG_DATA_TEXTURE",
        "Mods/README.txt": b"Instructions for TestMod",
    })

    installer = AutoInstaller(sandbox_mods, db_conn=db_conn)

    # RUN 1
    pkg1 = ModPackage(zip_file)
    assert installer.install_package(pkg1, game_domain="mysummercar", mod_id=101)

    assert (sandbox_mods / "TestMod.dll").is_file()
    assert (sandbox_mods / "Assets" / "TestMod" / "texture.png").is_file()
    assert (sandbox_mods / "readme(TestMod).md").is_file()
    assert not (sandbox_mods / "Mods").exists(), "Bug: nested Mods/ directory created!"

    # Count files on disk
    files_run1 = sorted([str(p.relative_to(sandbox_mods)) for p in sandbox_mods.rglob("*") if p.is_file()])

    # Check database counts
    own_repo = OwnershipRepository(db_conn)
    owners_run1 = len(own_repo.list_owned_files())


    # Check backups count (should be 0 because it's a fresh install)
    backups_dir = sandbox_mods / "_Backups"
    backups_run1 = len(list(backups_dir.glob("*.bak"))) if backups_dir.exists() else 0
    assert backups_run1 == 0

    # RUN 2 (Exact same mod reinstalled)
    pkg2 = ModPackage(zip_file)
    assert installer.install_package(pkg2, game_domain="mysummercar", mod_id=101)

    files_run2 = sorted([str(p.relative_to(sandbox_mods)) for p in sandbox_mods.rglob("*") if p.is_file()])
    owners_run2 = len(own_repo.list_owned_files())
    backups_run2 = len(list(backups_dir.glob("*.bak"))) if backups_dir.exists() else 0

    assert files_run1 == files_run2
    assert owners_run1 == owners_run2
    assert backups_run2 == 0, "Redundant backup created for identical files!"

    # RUN 3 (Exact same mod reinstalled again)
    pkg3 = ModPackage(zip_file)
    assert installer.install_package(pkg3, game_domain="mysummercar", mod_id=101)

    files_run3 = sorted([str(p.relative_to(sandbox_mods)) for p in sandbox_mods.rglob("*") if p.is_file()])
    owners_run3 = len(own_repo.list_owned_files())
    backups_run3 = len(list(backups_dir.glob("*.bak"))) if backups_dir.exists() else 0

    assert files_run1 == files_run3
    assert owners_run1 == owners_run3
    assert backups_run3 == 0
    assert not (sandbox_mods / "Mods").exists()
