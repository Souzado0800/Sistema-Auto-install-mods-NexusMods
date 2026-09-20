"""Transactional staging area for mod extraction before live filesystem deployment."""

import shutil
import time
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("nexus.installer.staging")


class StagingWorkspace:
    """Provides an isolated staging environment for archives before moving to game directory."""

    def __init__(self, base_staging_dir: str | Path = "data/staging"):
        self.base_dir = Path(base_staging_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Path | None = None

    def create_session(self, mod_name: str = "") -> Path:
        """Create a clean isolated staging folder for a mod installation transaction."""
        ts = time.strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(c for c in mod_name if c.isalnum() or c in ("-", "_"))[:30]
        session_name = f"stage_{clean_name}_{ts}" if clean_name else f"stage_{ts}"
        self._current_session = self.base_dir / session_name
        self._current_session.mkdir(parents=True, exist_ok=True)
        return self._current_session

    @property
    def current_session_path(self) -> Path | None:
        return self._current_session

    def cleanup(self) -> None:
        """Remove the active staging session directory."""
        if self._current_session and self._current_session.is_dir():
            try:
                shutil.rmtree(self._current_session, ignore_errors=True)
                logger.debug(f"Cleaned staging session: {self._current_session.name}")
            except Exception as e:
                logger.warning(f"Error removing staging dir: {e}")
            self._current_session = None
