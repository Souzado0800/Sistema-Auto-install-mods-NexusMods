import hashlib
import zipfile
import pytest
import httpx

from core.analyzer import ModPackage
from core.installer import AutoInstaller
from downloads.worker import DownloadWorker
from installer.staging import StagingWorkspace


@pytest.mark.asyncio
async def test_crash_at_50_percent_download_resumes(tmp_path):
    """
    Simulates a download crashing after writing 50% of the bytes.
    Subsequent invocation must send HTTP Range: bytes=X- and resume without redownloading.
    """
    dest_dir = tmp_path / "downloads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = "large_mod.zip"

    total_data = b"PART_1_FIRST_HALF_50_PERCENT" + b"PART_2_SECOND_HALF_50_PERCENT"
    half_size = len(b"PART_1_FIRST_HALF_50_PERCENT")
    expected_hash = hashlib.md5(total_data).hexdigest()

    # Create the partial .part file simulating crash at 50%
    part_file = dest_dir / f"{filename}.part"
    part_file.write_bytes(b"PART_1_FIRST_HALF_50_PERCENT")

    ranges_received = []

    def app_handler(request: httpx.Request) -> httpx.Response:
        range_header = request.headers.get("Range")
        ranges_received.append(range_header)
        if range_header == f"bytes={half_size}-":
            # HTTP 206 Partial Content
            return httpx.Response(
                206,
                content=b"PART_2_SECOND_HALF_50_PERCENT",
                headers={
                    "Content-Range": f"bytes {half_size}-{len(total_data)-1}/{len(total_data)}",
                    "Content-Length": str(len(b"PART_2_SECOND_HALF_50_PERCENT")),
                },
            )
        return httpx.Response(200, content=total_data)

    transport = httpx.MockTransport(app_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        worker = DownloadWorker(client, dest_dir)
        final_file = await worker.download(
            url="https://mock.nexusmods.com/file.zip",
            filename=filename,
            expected_hash=expected_hash,
            hash_algo="md5",
            expected_size=len(total_data),
        )

    assert final_file.is_file()
    assert final_file.read_bytes() == total_data
    assert not part_file.exists()
    assert ranges_received == [f"bytes={half_size}-"]


def test_crash_during_staging_cleanup(tmp_path):
    """
    Simulates a crash while files are being unpacked in a staging workspace.
    Asserts that staging directory can be safely cleaned up without leaving traces.
    """
    staging_base = tmp_path / "staging"
    ws = StagingWorkspace(staging_base)
    staging_dir = ws.create_session("test_mod")

    # Simulate unpacking partial files
    (staging_dir / "partial.dll").write_bytes(b"PARTIAL")
    (staging_dir / "temp_folder").mkdir()
    (staging_dir / "temp_folder" / "assets.unity3d").write_bytes(b"ASSETS")

    assert staging_dir.exists()

    # Simulate crash and cleanup
    ws.cleanup()
    assert not staging_dir.exists(), "Staging workspace was not cleaned up after crash!"


def test_crash_during_installation_rollback(tmp_path):
    """
    Simulates an error/crash during installation of an archive.
    Asserts:
      - Any newly written files are removed.
      - Pre-existing files that were replaced are restored from _Backups/.
    """
    sandbox_mods = tmp_path / "fake_game" / "Mods"
    sandbox_mods.mkdir(parents=True, exist_ok=True)

    # Pre-existing file
    existing_file = sandbox_mods / "TestMod.dll"
    existing_file.write_bytes(b"ORIGINAL_VERSION_DATA")

    # Create archive with a valid file and one member designed to fail
    zip_path = tmp_path / "crash_test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Mods/TestMod.dll", b"NEW_VERSION_DATA")
        zf.writestr("Mods/SecondMod.dll", b"SECOND_MOD_DATA")

    installer = AutoInstaller(sandbox_mods)

    # Monkey-patch to force an exception right after writing TestMod.dll
    orig_open = open
    fail_triggered = False

    def faulty_open(path, mode="r", *args, **kwargs):
        nonlocal fail_triggered
        if "SecondMod.dll" in str(path) and "w" in mode:
            fail_triggered = True
            raise OSError("Simulated disk full or permission crash!")
        return orig_open(path, mode, *args, **kwargs)

    pkg = ModPackage(zip_path)
    installer.path_resolver.resolve_package_paths(pkg)

    import unittest.mock as mock
    with mock.patch("builtins.open", side_effect=faulty_open):
        success = installer.install_package(pkg)

    assert not success, "Installation should have failed!"
    assert fail_triggered, "Failure was not triggered!"

    # Rollback verification:
    # 1. Original file should be restored with original contents
    assert existing_file.is_file()
    assert existing_file.read_bytes() == b"ORIGINAL_VERSION_DATA", "Original file was not restored!"

    # 2. Incomplete second file should not exist
    assert not (sandbox_mods / "SecondMod.dll").exists()
