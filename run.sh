#!/usr/bin/env bash
# ==============================================================================
# My Summer Car - AutoInstallModMySummerCar Linux Launcher
# Automatically manages .venv, dependencies (with sha256 hash check),
# and launches the 100% autonomous installer.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
HASH_FILE="$SCRIPT_DIR/.requirements.hash"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

# 1. Verify Python 3
if ! command -v python3 &>/dev/null; then
    echo "[!] Error: python3 is required but not installed or not in PATH." >&2
    exit 1
fi

# 2. Verify or create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Virtual environment not found. Initializing .venv..."
    python3 -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# 3. Check requirements.txt hash for fast startup
CURRENT_HASH=$(sha256sum "$REQ_FILE" 2>/dev/null | awk '{print $1}' || echo "none")
STORED_HASH=""
if [ -f "$HASH_FILE" ]; then
    STORED_HASH=$(cat "$HASH_FILE" 2>/dev/null || echo "")
fi

if [ "$CURRENT_HASH" != "$STORED_HASH" ]; then
    echo "[*] Dependencies updated or hash mismatch. Installing requirements..."
    "$VENV_PIP" install --quiet -r "$REQ_FILE"
    echo "$CURRENT_HASH" > "$HASH_FILE"
fi

# 4. Pass execution to Python
exec "$VENV_PYTHON" "$SCRIPT_DIR/AutoInstallModMySummerCar.py" "$@"
