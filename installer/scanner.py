"""Startup filesystem scanner to distinguish Managed vs Unmanaged mod files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from database.repositories import InstallationRepository, UnmanagedRepository
from utils.hashing import compute_file_hash
from utils.logging import get_logger

logger = get_logger("nexus.installer.scanner")


@dataclass
class ScanSummary:
    mods_directory: str
    total_files: int = 0
    managed_files_count: int = 0
    unmanaged_files_count: int = 0
    dll_count: int = 0
    directories_count: int = 0
    unmanaged_files: list[dict[str, Any]] = field(default_factory=list)


class StartupScanner:
    """
    Scans the live mods directory on initial startup.
    Catalogs pre-existing files as UNMANAGED without inventing false Nexus associations.
    """

    def __init__(
        self,
        mods_dir: str | Path,
        inst_repo: InstallationRepository,
        unmanaged_repo: UnmanagedRepository,
        game_domain: str = "mysummercar",
    ):
        self.mods_dir = Path(mods_dir)
        self.inst_repo = inst_repo
        self.unmanaged_repo = unmanaged_repo
        self.game_domain = game_domain

    def scan(self) -> ScanSummary:
        """Scan directory, record unmanaged files, and return summary."""
        summary = ScanSummary(mods_directory=str(self.mods_dir))

        if not self.mods_dir.is_dir():
            logger.info(f"Mods directory does not yet exist: {self.mods_dir}")
            return summary

        # 1. Fetch all managed relative paths and existing unmanaged records
        installed_mods = self.inst_repo.list_all_installed(self.game_domain)
        managed_paths: set[str] = set()
        for mod in installed_mods:
            manifest = self.inst_repo.get_manifest(self.game_domain, mod["mod_id"])
            for item in manifest:
                managed_paths.add(item["relative_path"])

        existing_unmanaged = {
            r["relative_path"]: r
            for r in self.unmanaged_repo.list_unmanaged_files(self.game_domain)
        }

        # 2. Walk directory
        all_entries = list(self.mods_dir.rglob("*"))
        for entry in all_entries:
            if entry.is_dir():
                summary.directories_count += 1
                continue

            if not entry.is_file():
                continue

            summary.total_files += 1
            rel_path = str(entry.relative_to(self.mods_dir))

            if entry.suffix.lower() == ".dll":
                summary.dll_count += 1

            if rel_path in managed_paths:
                summary.managed_files_count += 1
            else:
                summary.unmanaged_files_count += 1
                st = entry.stat()
                file_size = st.st_size

                # Re-use cached hash if file size hasn't changed
                cached = existing_unmanaged.get(rel_path)
                if cached and cached.get("file_size") == file_size and cached.get("sha256"):
                    sha256 = cached["sha256"]
                else:
                    sha256 = compute_file_hash(entry, "sha256")
                    self.unmanaged_repo.record_unmanaged_file(
                        game_domain=self.game_domain,
                        relative_path=rel_path,
                        file_size=file_size,
                        sha256=sha256,
                    )

                summary.unmanaged_files.append({
                    "relative_path": rel_path,
                    "file_size": file_size,
                    "sha256": sha256,
                })

        logger.info(
            f"Startup scan complete: {summary.total_files} files ({summary.managed_files_count} managed, "
            f"{summary.unmanaged_files_count} unmanaged, {summary.dll_count} DLLs)."
        )
        return summary
