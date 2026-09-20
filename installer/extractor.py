"""Safe archive extractor with path-traversal prevention and manifest logging."""

import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from utils.hashing import compute_file_hash
from utils.logging import get_logger

from .backup import BackupManager
from .safety import SafeArchiveGuard, SecurityError

logger = get_logger("nexus.installer.extractor")


@dataclass
class ExtractionResult:
    success: bool
    extracted_count: int = 0
    manifest: list[dict[str, Any]] = field(default_factory=list)
    executables_detected: list[str] = field(default_factory=list)
    error_message: str | None = None


class SafeArchiveExtractor:
    """Safely extracts archives into a target folder with Zip Slip and binary execution guards."""

    def __init__(self, backup_manager: BackupManager | None = None):
        self.backup_mgr = backup_manager

    def extract(self, archive_path: Path, destination_dir: Path) -> ExtractionResult:
        destination_dir.mkdir(parents=True, exist_ok=True)
        ext = archive_path.suffix.lower()

        if ext in (".zip", ".jar"):
            return self._extract_zip(archive_path, destination_dir)
        elif ext in (".tar", ".gz", ".tgz", ".bz2", ".xz"):
            return self._extract_tar(archive_path, destination_dir)
        else:
            return ExtractionResult(
                success=False,
                error_message=f"Unsupported archive format '{ext}' for file {archive_path.name}",
            )

    def _extract_zip(self, archive_path: Path, dest_dir: Path) -> ExtractionResult:
        manifest: list[dict[str, Any]] = []
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                namelist = zf.namelist()

                # 1. Scan for blocked executables/scripts
                executables = SafeArchiveGuard.scan_for_executables(namelist)

                # 2. Validate all destination paths before writing any file
                for name in namelist:
                    SafeArchiveGuard.validate_destination_path(dest_dir, name)

                # 3. Extract verified files safely
                for member in zf.infolist():
                    if member.is_dir():
                        continue

                    target_file = SafeArchiveGuard.validate_destination_path(dest_dir, member.filename)
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    # Backup if overwriting
                    if self.backup_mgr:
                        self.backup_mgr.backup_if_exists(target_file, dest_dir)

                    # Extract file stream
                    with zf.open(member) as src, open(target_file, "wb") as dst:
                        while chunk := src.read(64 * 1024):
                            dst.write(chunk)

                    # Record manifest
                    rel_path = str(target_file.relative_to(dest_dir))
                    size = target_file.stat().st_size
                    sha256 = compute_file_hash(target_file, "sha256")
                    manifest.append({
                        "relative_path": rel_path,
                        "file_size": size,
                        "sha256": sha256,
                    })

            return ExtractionResult(
                success=True,
                extracted_count=len(manifest),
                manifest=manifest,
                executables_detected=executables,
            )

        except SecurityError as sec_err:
            logger.error(f"Security validation rejected {archive_path.name}: {sec_err}")
            return ExtractionResult(success=False, error_message=str(sec_err))
        except Exception as e:
            logger.error(f"Failed to extract {archive_path.name}: {e}")
            return ExtractionResult(success=False, error_message=str(e))

    def _extract_tar(self, archive_path: Path, dest_dir: Path) -> ExtractionResult:
        manifest: list[dict[str, Any]] = []
        try:
            with tarfile.open(archive_path, "r:*") as tf:
                members = tf.getmembers()
                names = [m.name for m in members]

                executables = SafeArchiveGuard.scan_for_executables(names)

                for m in members:
                    SafeArchiveGuard.validate_destination_path(dest_dir, m.name)

                for m in members:
                    if m.isdir():
                        continue

                    target_file = SafeArchiveGuard.validate_destination_path(dest_dir, m.name)
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    if self.backup_mgr:
                        self.backup_mgr.backup_if_exists(target_file, dest_dir)

                    src = tf.extractfile(m)
                    if src:
                        with src, open(target_file, "wb") as dst:
                            while chunk := src.read(64 * 1024):
                                dst.write(chunk)

                    rel_path = str(target_file.relative_to(dest_dir))
                    size = target_file.stat().st_size
                    sha256 = compute_file_hash(target_file, "sha256")
                    manifest.append({
                        "relative_path": rel_path,
                        "file_size": size,
                        "sha256": sha256,
                    })

            return ExtractionResult(
                success=True,
                extracted_count=len(manifest),
                manifest=manifest,
                executables_detected=executables,
            )

        except SecurityError as sec_err:
            return ExtractionResult(success=False, error_message=str(sec_err))
        except Exception as e:
            return ExtractionResult(success=False, error_message=str(e))
