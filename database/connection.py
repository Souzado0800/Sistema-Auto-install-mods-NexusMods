"""Thread-safe SQLite connection manager with WAL mode."""

import sqlite3
import threading
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("nexus.database")


class DatabaseConnection:
    """Connection manager for SQLite databases with WAL mode and sensible concurrency pragmas."""

    def __init__(self, db_path: str | Path = "data/database.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode and performance pragmas
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 30000;")
            self._local.connection = conn
        return self._local.connection

    def close(self) -> None:
        """Close the thread-local connection if open."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            try:
                self._local.connection.close()
            except Exception as e:
                logger.debug(f"Error closing DB connection: {e}")
            self._local.connection = None
