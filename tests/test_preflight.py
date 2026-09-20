import pytest
from pathlib import Path
from core.preflight import PreflightChecker


@pytest.mark.asyncio
async def test_preflight_passes_on_valid_directories(tmp_path: Path):
    mods_dir = tmp_path / "Mods"
    data_dir = tmp_path / "data"
    staging_dir = tmp_path / "staging"

    checker = PreflightChecker(
        mods_dir=mods_dir,
        data_dir=data_dir,
        staging_dir=staging_dir,
        api_key="test_key",
        estimated_download_bytes=1024 * 1024,  # 1 MB
    )

    result = await checker.run_all(skip_network=True)
    assert result.passed, f"Preflight failed: {[c.name for c in result.checks if not c.passed]}"
    assert result.free_disk_bytes > 0
    assert result.required_disk_bytes > 0
    assert any(c.name == "Mods directory writable" and c.passed for c in result.checks)
    assert any(c.name == "Available disk space" and c.passed for c in result.checks)
    assert any(c.name == "Transaction clean state" and c.passed for c in result.checks)


@pytest.mark.asyncio
async def test_preflight_detects_unwritable_directory(tmp_path: Path):
    unwritable_dir = tmp_path / "unwritable"
    unwritable_dir.mkdir(parents=True)
    unwritable_dir.chmod(0o400)  # read-only

    checker = PreflightChecker(
        mods_dir=unwritable_dir,
        data_dir=tmp_path / "data",
        staging_dir=tmp_path / "staging",
        api_key=None,
    )

    result = await checker.run_all(skip_network=True)
    unwritable_dir.chmod(0o700)  # restore for cleanup
    assert not result.passed
    assert any("Mods directory writable" in c.name and not c.passed for c in result.checks)
