import hashlib
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_requirements_hash_matches_requirements_file():
    req_file = PROJECT_ROOT / "requirements.txt"
    hash_file = PROJECT_ROOT / ".requirements.hash"

    assert req_file.exists(), "requirements.txt must exist"
    assert hash_file.exists(), ".requirements.hash must exist"

    computed = hashlib.sha256(req_file.read_bytes()).hexdigest()
    stored = hash_file.read_text().strip()

    assert computed == stored, f"Hash mismatch: computed {computed} != stored {stored}"


def test_launcher_scripts_executable():
    run_sh = PROJECT_ROOT / "run.sh"
    launcher = PROJECT_ROOT / "AutoInstallModMySummerCar"

    assert run_sh.exists()
    assert os.access(run_sh, os.X_OK), "run.sh must be executable"

    assert launcher.exists()
    assert launcher.is_symlink() or launcher.is_file()
    assert os.access(launcher, os.X_OK), "AutoInstallModMySummerCar launcher must be executable"


def test_desktop_entry_validity():
    desktop_file = PROJECT_ROOT / "AutoInstallModMySummerCar.desktop"
    assert desktop_file.exists()

    content = desktop_file.read_text()
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "Terminal=true" in content
    assert "AutoInstallModMySummerCar" in content
    assert "Categories=" in content
