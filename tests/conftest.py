"""Pytest fixtures and configuration for Nexus Mods AutoInstaller test suite."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from database.connection import DatabaseConnection
from database.migrations import init_db
from database.repositories import (
    CacheRepository,
    DownloadStoreRepository,
    InstallationRepository,
    ModRepository,
    QueueRepository,
    UnmanagedRepository,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide an isolated temporary directory for testing."""
    tmp = tempfile.mkdtemp(prefix="nexus_test_")
    p = Path(tmp)
    yield p
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_db(temp_dir: Path) -> Generator[DatabaseConnection, None, None]:
    """Provide a fresh SQLite database in WAL mode."""
    db_path = temp_dir / "test.sqlite"
    conn = DatabaseConnection(db_path)
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def repositories(test_db: DatabaseConnection) -> dict:
    """Provide initialized repositories for testing."""
    return {
        "mod": ModRepository(test_db),
        "queue": QueueRepository(test_db),
        "installation": InstallationRepository(test_db),
        "cache": CacheRepository(test_db),
        "store": DownloadStoreRepository(test_db),
        "unmanaged": UnmanagedRepository(test_db),
    }
