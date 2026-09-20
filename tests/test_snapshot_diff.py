from pathlib import Path
from installer.snapshot import SnapshotManager


def test_snapshot_and_diff_workflow(tmp_path: Path):
    target_dir = tmp_path / "Mods"
    storage_dir = tmp_path / "snapshots"
    target_dir.mkdir(parents=True)

    # Initial file
    file_a = target_dir / "UnchangedMod.dll"
    file_a.write_text("initial unchanged content")

    file_b = target_dir / "ModifiedMod.dll"
    file_b.write_text("v1.0")

    manager = SnapshotManager(target_dir, storage_dir)

    # 1. Take before snapshot
    before_snap = manager.take_snapshot(save_to_disk=True)
    assert len(before_snap.files) == 2
    assert "UnchangedMod.dll" in before_snap.files
    assert "ModifiedMod.dll" in before_snap.files

    # 2. Simulate installation actions:
    # - Add new mod
    new_mod = target_dir / "NewMod.dll"
    new_mod.write_text("freshly installed mod")

    # - Modify existing mod
    file_b.write_text("v2.0 updated")

    # 3. Take after snapshot
    after_snap = manager.take_snapshot(save_to_disk=True)
    assert len(after_snap.files) == 3

    # 4. Compute diff
    diff = manager.compute_diff(before_snap, after_snap)

    assert diff.has_changes
    assert len(diff.added) == 1
    assert diff.added[0].relative_path == "NewMod.dll"

    assert len(diff.modified) == 1
    assert diff.modified[0][0].relative_path == "ModifiedMod.dll"

    assert len(diff.removed) == 0  # Zero deletions guarantee!

    assert len(diff.unchanged) == 1
    assert diff.unchanged[0].relative_path == "UnchangedMod.dll"
