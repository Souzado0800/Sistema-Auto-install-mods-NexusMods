"""Tests for concurrent resumable download manager and archive validation."""

import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pytest

from downloads.adaptive import AdaptiveConcurrencyController
from downloads.worker import DownloadWorker


@pytest.mark.asyncio
async def test_download_worker_and_hash_validation(temp_dir: Path):
    # 1. Prepare synthetic ZIP content
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("test.txt", "Hello Nexus Mods!")
    content = buffer.getvalue()
    expected_md5 = hashlib.md5(content).hexdigest()

    # 2. Mock transport returning the synthetic archive
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        worker = DownloadWorker(client=client, dest_dir=temp_dir)
        downloaded = await worker.download(
            url="https://cdn.nexusmods.com/test.zip",
            filename="test.zip",
            expected_hash=expected_md5,
            hash_algo="md5",
        )

        assert downloaded.is_file()
        assert downloaded.name == "test.zip"
        assert downloaded.stat().st_size == len(content)


@pytest.mark.asyncio
async def test_resumable_partial_download(temp_dir: Path):
    content = b"A" * 1000 + b"B" * 1000
    part_file = temp_dir / "partial.zip.part"
    # Write initial 1000 bytes
    part_file.write_bytes(b"A" * 1000)

    range_header_seen = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal range_header_seen
        range_header_seen = request.headers.get("range")
        if range_header_seen == "bytes=1000-":
            return httpx.Response(206, content=b"B" * 1000, headers={"Content-Length": "1000"})
        return httpx.Response(200, content=content)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        worker = DownloadWorker(client=client, dest_dir=temp_dir)
        downloaded = await worker.download(
            url="https://cdn.nexusmods.com/partial.zip",
            filename="partial.zip",
        )

        assert range_header_seen == "bytes=1000-"
        assert downloaded.stat().st_size == 2000
        assert downloaded.read_bytes() == content


@pytest.mark.asyncio
async def test_download_corrupted_hash_rejection(temp_dir: Path):
    content = b"Corrupted data content"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        worker = DownloadWorker(client=client, dest_dir=temp_dir)
        with pytest.raises(ValueError) as exc:
            await worker.download(
                url="https://cdn.nexusmods.com/corrupt.zip",
                filename="corrupt.zip",
                expected_hash="deadbeef12345678",
                hash_algo="md5",
            )
        assert "Integrity check failed" in str(exc.value)
        # Verify part file was deleted
        assert not (temp_dir / "corrupt.zip.part").exists()
        assert not (temp_dir / "corrupt.zip").exists()


@pytest.mark.asyncio
async def test_adaptive_concurrency_controller():
    controller = AdaptiveConcurrencyController(initial_concurrency=4, min_concurrency=1, max_concurrency=8)
    assert controller.current_limit == 4

    # Report failure (rate limit 429)
    backoff = await controller.report_failure(status_code=429, is_rate_limit=True)
    assert controller.current_limit == 3
    assert backoff >= 15.0

    # Report multiple successes to ramp back up
    for _ in range(5):
        await controller.report_success()
    assert controller.current_limit == 4
