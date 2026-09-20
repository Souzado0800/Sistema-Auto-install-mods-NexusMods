"""Pre-installation backup and rollback manager."""

import shutil
import time
from pathlib import Path

from utils.logging import get_logger
from utils.paths import normalize_path

logger = get_logger("nexus.installer.backup")


class BackupManager:
    """Manages file backups prior to file overwrites during mod installation."""

    def __init__(self, backup_root: str | Path = "data/backups"):
        self.backup_root = normalize_path(backup_root)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self._current_session_dir: Path | None = None
        self._backed_up_files: list[tuple[Path, Path]] = []  # (original, backup_dest)

    def start_session(self, session_name: str | None = None) -> Path:
        """Create a new timestamped backup session directory."""
        ts = time.strftime("%Y%m%d_%H%M%S")
        name = f"backup_{session_name}_{ts}" if session_name else f"backup_{ts}"
        self._current_session_dir = self.backup_root / name
        self._current_session_dir.mkdir(parents=True, exist_ok=True)
        self._backed_up_files.clear()
        return self._current_session_dir

    def backup_if_exists(self, file_path: Path, base_install_dir: Path) -> Path | None:
        """If file already exists on disk, copy it to the current backup session directory."""
        if not file_path.is_file():
            return None

        if not self._current_session_dir:
            self.start_session()

        assert self._current_session_dir is not None

        try:
            rel = file_path.relative_to(base_install_dir)
            backup_dest = self._current_session_dir / rel
            backup_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_dest)
            self._backed_up_files.append((file_path, backup_dest))
            logger.debug(f"Backed up existing file: {rel}")
            return backup_dest
        except Exception as e:
            logger.warning(f"Failed to backup existing file {file_path}: {e}")
            return None

    def rollback(self) -> None:
        """Restore all files backed up in the current session in reverse order."""
        if not self._backed_up_files:
            return

        logger.warning(f"Rolling back {len(self._backed_up_files)} backed up files...")
        for original, backup in reversed(self._backed_up_files):
            try:
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, original)
                logger.info(f"Restored: {original.name}")
            except Exception as e:
                logger.error(f"Failed to rollback file {original}: {e}")
