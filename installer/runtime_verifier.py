"""
MSCLoader Runtime Log Verifier & Parser
=======================================
Distinguishes INSTALLATION VERIFIED (valid on disk) from RUNTIME VERIFIED (in-game evidence).
Performs strictly read-only inspection of Unity 5 / Doorstop / MSCLoader output logs.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("installer.runtime_verifier")


class RuntimeStatus(StrEnum):
    LOADED = "LOADED"
    LOAD_FAILED = "LOAD_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ModRuntimeEvidence:
    mod_id: int | None
    mod_name: str
    status: RuntimeStatus
    details: str
    log_source: str | None = None
    log_mtime: float | None = None


class MSCLoaderLogParser:
    """Read-only parser for MSCLoader and Unity output logs."""

    def __init__(self, game_dir: Path | None = None, mods_dir: Path | None = None):
        self.game_dir = Path(game_dir) if game_dir else None
        self.mods_dir = Path(mods_dir) if mods_dir else None

    def find_candidate_logs(self) -> list[Path]:
        """Discovers output_log.txt in standard MSC and Proton paths."""
        candidates = []

        if self.game_dir:
            candidates.append(self.game_dir / "output_log.txt")
            candidates.append(self.game_dir / "mysummercar_Data" / "output_log.txt")

        if self.mods_dir:
            candidates.append(self.mods_dir / "output_log.txt")
            for p in self.mods_dir.glob("*.log"):
                if p not in candidates:
                    candidates.append(p)

        # Flatpak Steam Proton default path
        flatpak_proton_log = (
            Path.home()
            / ".var"
            / "app"
            / "com.valvesoftware.Steam"
            / ".local"
            / "share"
            / "Steam"
            / "steamapps"
            / "compatdata"
            / "516750"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "AppData"
            / "LocalLow"
            / "Amistech"
            / "My Summer Car"
            / "output_log.txt"
        )
        candidates.append(flatpak_proton_log)

        # Native Steam Proton path
        native_proton_log = (
            Path.home()
            / ".local"
            / "share"
            / "Steam"
            / "steamapps"
            / "compatdata"
            / "516750"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "AppData"
            / "LocalLow"
            / "Amistech"
            / "My Summer Car"
            / "output_log.txt"
        )
        candidates.append(native_proton_log)

        # Return only files that exist and have size > 0
        existing = [c for c in candidates if c.is_file() and c.stat().st_size > 0]
        # Sort by mtime descending (newest log first)
        existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return existing

    def verify_mod_runtime(
        self,
        mod_name: str,
        dll_name: str | None = None,
        min_install_time: float | None = None,
    ) -> ModRuntimeEvidence:
        """
        Inspects output logs to verify if a mod was loaded by MSCLoader at runtime.
        Returns RUNTIME status: LOADED, LOAD_FAILED, or UNKNOWN.
        """
        logs = self.find_candidate_logs()
        if not logs:
            return ModRuntimeEvidence(
                mod_id=None,
                mod_name=mod_name,
                status=RuntimeStatus.UNKNOWN,
                details="No MSCLoader output_log.txt found on system. Launch My Summer Car to generate runtime logs.",
            )

        log_path = logs[0]
        log_mtime = log_path.stat().st_mtime

        if min_install_time and log_mtime < min_install_time:
            return ModRuntimeEvidence(
                mod_id=None,
                mod_name=mod_name,
                status=RuntimeStatus.UNKNOWN,
                details=f"Latest log ({log_path.name}) is older than installation time. Game has not been run since install.",
                log_source=str(log_path),
                log_mtime=log_mtime,
            )

        try:
            content = log_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ModRuntimeEvidence(
                mod_id=None,
                mod_name=mod_name,
                status=RuntimeStatus.UNKNOWN,
                details=f"Failed to read log file {log_path}: {exc}",
                log_source=str(log_path),
            )

        # Build search patterns
        clean_name = re.escape(mod_name)
        dll_stem = re.escape(Path(dll_name).stem) if dll_name else clean_name

        # Check for error patterns first
        error_regex = re.compile(
            rf"(?:error|exception|failed|could not load).*?(?:{clean_name}|{dll_stem})",
            re.IGNORECASE,
        )
        if error_regex.search(content):
            # Extract matching snippet
            match = error_regex.search(content)
            snippet = match.group(0)[:120] if match else "Error found in log"
            return ModRuntimeEvidence(
                mod_id=None,
                mod_name=mod_name,
                status=RuntimeStatus.LOAD_FAILED,
                details=f"Error recorded in log: {snippet}",
                log_source=str(log_path),
                log_mtime=log_mtime,
            )

        # Check for loaded patterns (both "Loaded Mod X" and "Mod X loaded")
        loaded_regex = re.compile(
            rf"(?:(?:loaded|loading|initialized|mod\s+<b>).*?(?:{clean_name}|{dll_stem}))|(?:(?:{clean_name}|{dll_stem}).*?(?:loaded|loading|initialized|active))",
            re.IGNORECASE,
        )
        if loaded_regex.search(content):
            return ModRuntimeEvidence(
                mod_id=None,
                mod_name=mod_name,
                status=RuntimeStatus.LOADED,
                details=f"Confirmed loaded by MSCLoader in {log_path.name}",
                log_source=str(log_path),
                log_mtime=log_mtime,
            )

        return ModRuntimeEvidence(
            mod_id=None,
            mod_name=mod_name,
            status=RuntimeStatus.UNKNOWN,
            details=f"Mod not mentioned in latest log ({log_path.name}). Game may need to reach main menu.",
            log_source=str(log_path),
            log_mtime=log_mtime,
        )
