#!/usr/bin/env python3
"""
Standalone Binary Builder for AutoInstallModMySummerCar
======================================================
Compiles AutoInstallModMySummerCar into a self-contained Linux executable.

Packaging Evaluation: PyInstaller vs Nuitka
--------------------------------------------
- PyInstaller (Selected):
    * Flawless dynamic loading of D-Bus / Keyring backends (`secretstorage`, `jeepney`, `keyring.backends`).
    * Full compatibility with `rich` console styling and `httpx` SSL bundles.
    * Fast packaging (< 30s) and predictable runtime behavior across Linux distributions.
- Nuitka:
    * Compiles to C++, but requires extensive tuning for D-Bus dynamic imports and complex third-party metadata.
    * Significantly higher build times with marginal execution gains for I/O-bound networking apps.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build() -> int:
    print("=" * 70)
    print(" AutoInstallModMySummerCar - Standalone Executable Builder")
    print("=" * 70)

    # Verify PyInstaller is installed
    try:
        import PyInstaller
        print(f"[*] Found PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("[!] PyInstaller is not installed in the active environment.")
        print("[*] Install it via: pip install pyinstaller")
        return 1

    dist_dir = PROJECT_ROOT / "dist"
    build_dir = PROJECT_ROOT / "build"

    entry_point = PROJECT_ROOT / "AutoInstallModMySummerCar.py"
    config_example = PROJECT_ROOT / "config.example.json"

    hidden_imports = [
        "keyring",
        "keyring.backends",
        "keyring.backends.SecretService",
        "secretstorage",
        "jeepney",
        "rich",
        "rich.console",
        "rich.table",
        "rich.panel",
        "rich.progress",
        "pydantic",
        "sqlite3",
        "httpx",
        "psutil",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=AutoInstallModMySummerCar",
        "--onefile",
        "--clean",
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={PROJECT_ROOT}",
    ]

    for hi in hidden_imports:
        cmd.extend(["--hidden-import", hi])

    if config_example.exists():
        cmd.extend(["--add-data", f"{config_example}:."])

    cmd.append(str(entry_point))

    print(f"[*] Running command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode == 0:
        binary_path = dist_dir / "AutoInstallModMySummerCar"
        print("\n" + "=" * 70)
        print("[✓] Standalone binary built successfully!")
        print(f"    Location: {binary_path}")
        print("=" * 70)
    else:
        print(f"\n[!] Build failed with exit code: {result.returncode}")

    return result.returncode


if __name__ == "__main__":
    sys.exit(build())
