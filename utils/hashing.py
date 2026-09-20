"""Streaming hash calculation and verification utilities."""

import asyncio
import hashlib
from pathlib import Path

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB chunks


def compute_file_hash(
    file_path: str | Path,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """
    Compute a cryptographic hash of a file using streaming chunks to minimize memory usage.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hashing: {file_path}")

    hasher = hashlib.new(algorithm.lower())
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def compute_file_hashes(
    file_path: str | Path,
    algorithms: tuple[str, ...] = ("md5", "sha256"),
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, str]:
    """
    Compute multiple hashes in a single sequential pass over the file.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hashing: {file_path}")

    hashers = {alg: hashlib.new(alg.lower()) for alg in algorithms}
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            for h in hashers.values():
                h.update(chunk)

    return {alg: h.hexdigest().lower() for alg, h in hashers.items()}


async def compute_file_hash_async(
    file_path: str | Path,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """
    Asynchronously compute a file hash offloaded to a thread pool executor.
    """
    return await asyncio.to_thread(compute_file_hash, file_path, algorithm, chunk_size)


def verify_file_hash(
    file_path: str | Path,
    expected_hash: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify if the hash of a file matches the expected hash (case-insensitive).
    """
    if not expected_hash:
        return True
    actual_hash = compute_file_hash(file_path, algorithm=algorithm)
    return actual_hash.lower() == expected_hash.strip().lower()
