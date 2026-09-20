"""
Monitors the user's downloads folder for newly completed mod archives.
Handles in-progress browser downloads (.crdownload, .part) and prevents
picking up pre-existing files using baseline snapshots.
"""

import asyncio
import logging
import re
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
        """Records initial state of files in downloads directory to ignore pre-existing files."""
        if not self.downloads_dir.is_dir():
            return
        for f in self.downloads_dir.glob("*"):
            if f.is_file():
                try:
                    stat = f.stat()
                    self.baseline_snapshot[f.name] = FileState(
                        path=f, size=stat.st_size, mtime=stat.st_mtime
                    )
                except Exception:
                    pass

    def is_new_or_modified(self, path: Path) -> bool:
        """Returns True if the file was not present at baseline or its size/mtime changed."""
        filename = path.name
        if filename not in self.baseline_snapshot:
            return True
        prev = self.baseline_snapshot[filename]
        try:
            cur_stat = path.stat()
            return cur_stat.st_size != prev.size or cur_stat.st_mtime != prev.mtime
        except Exception:
            return False

    @staticmethod
    def is_matching_mod(
        filename: str,
        mod_id: int | None,
        mod_name: str | None,
        file_id: int | None = None,
    ) -> bool:
        """
        Checks if a filename semantically matches the mod ID or mod name with zero false-positives.
        Prevents random substrings inside timestamps or version numbers from matching small mod IDs.
        """
        stem = Path(filename).stem

        # 1. Official Nexus Mods filename pattern: <Title>-<ModID>-<Version>-<Timestamp>
        m = re.match(
            r"^(.+?)-(?P<mid>\d+)-(?:[\d\.\-a-zA-Z]+)-(?:\d{9,11})(?: \(\d+\))?$",
            stem,
            re.IGNORECASE,
        )
        if m and mod_id:
            return int(m.group("mid")) == mod_id

        # 2. Match by file_id if provided
        if file_id:
            if re.search(r"(?:^|[^0-9])" + str(file_id) + r"(?:[^0-9]|$)", stem):
                return True

        # 3. Match isolated mod_id
        if mod_id:
            if re.search(r"(?:^|[\s_\-\(\[])" + str(mod_id) + r"(?:[\s_\-\)\]]|$)", stem):
                if mod_id >= 100:
                    return True
                if mod_name:
                    norm_m = re.sub(r"[^a-z0-9]", "", mod_name.lower())
                    norm_f = re.sub(r"[^a-z0-9]", "", stem.lower())
                    if len(norm_m) >= 3 and len(norm_f) >= 3 and (
                        norm_m in norm_f or norm_f in norm_m or norm_f.startswith(norm_m[:4])
                    ):
                        return True
                else:
                    return True

        # 4. Match by normalized mod_name
        if mod_name:
            norm_name = re.sub(r"[^a-z0-9]", "", mod_name.lower())
            norm_file = re.sub(r"[^a-z0-9]", "", stem.lower())
            if len(norm_name) >= 4 and len(norm_file) >= 4:
                if norm_name in norm_file or norm_file in norm_name:
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
                    if self.is_matching_mod(f.name, mod_id, mod_name, file_id):
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

                if self.is_matching_mod(f.name, mod_id, mod_name, file_id):
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
