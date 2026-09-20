"""
Filesystem Snapshot & Post-Install Diff Engine
=============================================
Provides cryptographic auditing of the target mods directory before and after
installation operations to guarantee zero unintended deletions or file corruptions.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("installer.snapshot")


@dataclass
class FileRecord:
    relative_path: str
    size_bytes: int
    mtime: float
    sha256: str


@dataclass
class FilesystemSnapshot:
    timestamp: float
    target_dir: str
    files: dict[str, FileRecord] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "target_dir": self.target_dir,
                "files": {k: asdict(v) for k, v in self.files.items()},
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "FilesystemSnapshot":
        data = json.loads(json_str)
        files = {k: FileRecord(**v) for k, v in data.get("files", {}).items()}
        return cls(
            timestamp=data.get("timestamp", 0.0),
            target_dir=data.get("target_dir", ""),
            files=files,
        )


@dataclass
class SnapshotDiff:
    added: list[FileRecord] = field(default_factory=list)
    modified: list[tuple[FileRecord, FileRecord]] = field(default_factory=list)  # (before, after)
    removed: list[FileRecord] = field(default_factory=list)
    unchanged: list[FileRecord] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.removed)

    def summary_dict(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "modified": len(self.modified),
            "removed": len(self.removed),
            "unchanged": len(self.unchanged),
        }


class SnapshotManager:
    """Manages pre-install snapshots and post-install diffs."""

    def __init__(self, target_dir: Path, snapshot_storage_dir: Path):
        self.target_dir = Path(target_dir)
        self.storage_dir = Path(snapshot_storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def take_snapshot(self, save_to_disk: bool = True) -> FilesystemSnapshot:
        """Takes an exact recursive cryptographic snapshot of the target directory."""
        self.target_dir.mkdir(parents=True, exist_ok=True)
        files: dict[str, FileRecord] = {}

        for item in self.target_dir.rglob("*"):
            if item.is_file():
                try:
                    rel_path = str(item.relative_to(self.target_dir))
                    stat = item.stat()
                    sha256 = self._hash_file(item)
                    files[rel_path] = FileRecord(
                        relative_path=rel_path,
                        size_bytes=stat.st_size,
                        mtime=stat.st_mtime,
                        sha256=sha256,
                    )
                except Exception as exc:
                    logger.warning(f"Failed to record {item} in snapshot: {exc}")

        snapshot = FilesystemSnapshot(
            timestamp=time.time(),
            target_dir=str(self.target_dir.resolve()),
            files=files,
        )

        if save_to_disk:
            ts_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(snapshot.timestamp))
            out_file = self.storage_dir / f"snapshot_{ts_str}.json"
            out_file.write_text(snapshot.to_json(), encoding="utf-8")
            logger.info(f"Saved snapshot with {len(files)} files to {out_file}")

        return snapshot

    @staticmethod
    def compute_diff(
        before: FilesystemSnapshot, after: FilesystemSnapshot
    ) -> SnapshotDiff:
        """Computes difference between two snapshots."""
        diff = SnapshotDiff()

        all_paths = set(before.files.keys()) | set(after.files.keys())

        for p in sorted(all_paths):
            in_before = p in before.files
            in_after = p in after.files

            if in_after and not in_before:
                diff.added.append(after.files[p])
            elif in_before and not in_after:
                diff.removed.append(before.files[p])
            else:
                b_rec = before.files[p]
                a_rec = after.files[p]
                if b_rec.sha256 != a_rec.sha256 or b_rec.size_bytes != a_rec.size_bytes:
                    diff.modified.append((b_rec, a_rec))
                else:
                    diff.unchanged.append(a_rec)

        return diff
