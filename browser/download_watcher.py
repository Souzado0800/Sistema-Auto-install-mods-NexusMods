"""
Monitors the user's downloads folder for newly completed mod archives.
Handles in-progress browser downloads (.crdownload, .part) and prevents
picking up pre-existing files using baseline snapshots.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = (".zip", ".rar", ".7z", ".tar.gz")


@dataclass
class FileState:
    path: Path
    size: int
    mtime: float


class DownloadWatcher:
    """Watches the downloads folder for new, completed downloads matching target criteria."""

    def __init__(self, downloads_dir: Path | None = None):
        self.downloads_dir = downloads_dir or (Path.home() / "Downloads")
        self.baseline_snapshot: dict[str, FileState] = {}
        self.capture_baseline()

    def capture_baseline(self) -> None:
        """Takes a snapshot of all existing files in the downloads directory."""
        self.baseline_snapshot.clear()
        if not self.downloads_dir.is_dir():
            return

        try:
            for p in self.downloads_dir.glob("*"):
                if p.is_file():
                    try:
                        st = p.stat()
                        self.baseline_snapshot[p.name] = FileState(
                            path=p, size=st.st_size, mtime=st.st_mtime
                        )
                    except (OSError, FileNotFoundError):
                        pass
        except Exception as e:
            logger.debug(f"Error capturing baseline downloads snapshot: {e}")

    def is_new_or_modified(self, path: Path) -> bool:
        """Determines if a file is newly created or modified after baseline snapshot."""
        if path.name not in self.baseline_snapshot:
            return True
        try:
            current_st = path.stat()
            baseline = self.baseline_snapshot[path.name]
            return current_st.st_mtime > baseline.mtime or current_st.st_size != baseline.size
        except (OSError, FileNotFoundError):
            return False

    @staticmethod
    def is_matching_mod(filename: str, mod_id: int | None, mod_name: str | None) -> bool:
        """Checks if a filename semantically matches the mod ID or mod name."""
        name_lower = filename.lower()
        if mod_id and str(mod_id) in name_lower:
            return True

        if mod_name:
            norm_name = mod_name.lower().replace(" ", "").replace("_", "").replace("-", "")
            norm_file = name_lower.replace(" ", "").replace("_", "").replace("-", "")
            if norm_name and norm_name in norm_file:
                return True

        return False

    async def wait_for_download(
        self,
        mod_id: int | None = None,
        file_id: int | None = None,
        mod_name: str | None = None,
        timeout: float = 120.0,
        poll_interval: float = 1.0,
    ) -> Path | None:
        """
        Polls downloads directory until a matching completed archive appears.
        Detects in-progress downloads (.crdownload, .part) and waits for completion.
        """
        if not self.downloads_dir.is_dir():
            logger.warning(f"Downloads directory does not exist: {self.downloads_dir}")
            return None

        elapsed = 0.0
        in_progress_detected = False

        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            # Check for in-progress browser downloads (.crdownload / .part)
            current_files = list(self.downloads_dir.glob("*"))
            for f in current_files:
                if f.suffix in (".crdownload", ".part"):
                    if self.is_matching_mod(f.name, mod_id, mod_name):
                        if not in_progress_detected:
                            logger.info(f"Detected in-progress download: {f.name}")
                            in_progress_detected = True

            # Check for completed archives
            candidates: list[Path] = []
            for f in current_files:
                if not f.is_file():
                    continue
                if f.suffix.lower() not in ARCHIVE_EXTENSIONS:
                    continue
                if not self.is_new_or_modified(f):
                    continue

                if self.is_matching_mod(f.name, mod_id, mod_name):
                    candidates.append(f)

            if candidates:
                # Pick most recent candidate
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                candidate = candidates[0]

                # Ensure file is completely written (size stable for 0.5s)
                initial_size = candidate.stat().st_size
                await asyncio.sleep(0.5)
                try:
                    current_size = candidate.stat().st_size
                    if current_size == initial_size and current_size > 0:
                        logger.info(f"Download complete and stable: {candidate.name} ({current_size} bytes)")
                        return candidate
                except (OSError, FileNotFoundError):
                    continue

        logger.warning(f"Download watcher timed out after {timeout}s for Mod ID {mod_id}")
        return None
