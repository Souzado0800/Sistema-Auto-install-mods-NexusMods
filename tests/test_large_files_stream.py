import hashlib
import psutil
from pathlib import Path


def generate_streaming_chunks(total_bytes: int, chunk_size: int = 64 * 1024):
    """Generator yielding chunks of simulated large file data without holding total in RAM."""
    pattern = b"0123456789ABCDEF" * (chunk_size // 16)
    yielded = 0
    while yielded < total_bytes:
        to_yield = min(chunk_size, total_bytes - yielded)
        yield pattern[:to_yield]
        yielded += to_yield


def stream_download_and_hash(chunks_gen, dest_path: Path):
    """Simulates streaming worker writing chunks to disk and calculating SHA-256 on the fly."""
    hasher = hashlib.sha256()
    bytes_written = 0
    with open(dest_path, "wb") as f:
        for chunk in chunks_gen:
            f.write(chunk)
            hasher.update(chunk)
            bytes_written += len(chunk)
    return bytes_written, hasher.hexdigest()


def test_streaming_large_file_constant_ram(tmp_path):
    """
    Simulates downloading and hashing a 100 MB and 500 MB file.
    Asserts that RAM usage does not grow with the file size.
    """
    proc = psutil.Process()
    ram_before = proc.memory_info().rss / (1024 * 1024)

    # 1. Test 100 MB stream
    size_100mb = 100 * 1024 * 1024
    dest_100mb = tmp_path / "stream_100mb.bin"
    bytes_100, hash_100 = stream_download_and_hash(
        generate_streaming_chunks(size_100mb), dest_100mb
    )
    assert bytes_100 == size_100mb
    assert dest_100mb.stat().st_size == size_100mb

    ram_after_100 = proc.memory_info().rss / (1024 * 1024)
    delta_100 = ram_after_100 - ram_before
    # RAM increase must be negligible (< 25 MB), not 100 MB!
    assert delta_100 < 25.0, f"RAM grew by {delta_100:.2f} MB, expected constant memory"

    # 2. Test 500 MB stream
    size_500mb = 500 * 1024 * 1024
    dest_500mb = tmp_path / "stream_500mb.bin"
    bytes_500, hash_500 = stream_download_and_hash(
        generate_streaming_chunks(size_500mb), dest_500mb
    )
    assert bytes_500 == size_500mb
    assert dest_500mb.stat().st_size == size_500mb

    ram_after_500 = proc.memory_info().rss / (1024 * 1024)
    delta_500 = ram_after_500 - ram_before
    # RAM increase must still be negligible (< 35 MB), not 500 MB!
    assert delta_500 < 35.0, f"RAM grew by {delta_500:.2f} MB during 500MB stream, expected constant memory"

    # Clean up large files
    dest_100mb.unlink()
    dest_500mb.unlink()
