"""Repository access layer for SQLite database tables."""

import json
import time
from typing import Any

from utils.logging import get_logger

from .connection import DatabaseConnection

logger = get_logger("nexus.database.repositories")


class ModRepository:
    """Repository for mod and mod files metadata."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def upsert_mod(self, mod_data: dict[str, Any]) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO mods (
                    game_domain, mod_id, name, author, version, summary,
                    description, picture_url, updated_timestamp, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(game_domain, mod_id) DO UPDATE SET
                    name = excluded.name,
                    author = excluded.author,
                    version = excluded.version,
                    summary = excluded.summary,
                    description = excluded.description,
                    picture_url = excluded.picture_url,
                    updated_timestamp = excluded.updated_timestamp,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    mod_data["game_domain"],
                    mod_data["mod_id"],
                    mod_data.get("name", ""),
                    mod_data.get("author", ""),
                    mod_data.get("version", ""),
                    mod_data.get("summary", ""),
                    mod_data.get("description", ""),
                    mod_data.get("picture_url", ""),
                    mod_data.get("updated_timestamp", 0),
                ),
            )

    def get_mod(self, game_domain: str, mod_id: int) -> dict[str, Any] | None:
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT * FROM mods WHERE game_domain = ? AND mod_id = ?",
            (game_domain, mod_id),
        ).fetchone()
        return dict(row) if row else None

    def upsert_files(self, game_domain: str, mod_id: int, files: list[dict[str, Any]]) -> None:
        conn = self.db.get_connection()
        with conn:
            for f in files:
                conn.execute(
                    """
                    INSERT INTO mod_files (
                        file_id, mod_id, game_domain, name, version,
                        category_id, category_name, size_bytes, size_kb,
                        file_name, md5, sha256, is_primary, uploaded_timestamp, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_id) DO UPDATE SET
                        name = excluded.name,
                        version = excluded.version,
                        category_id = excluded.category_id,
                        category_name = excluded.category_name,
                        size_bytes = excluded.size_bytes,
                        size_kb = excluded.size_kb,
                        file_name = excluded.file_name,
                        md5 = excluded.md5,
                        sha256 = excluded.sha256,
                        is_primary = excluded.is_primary,
                        uploaded_timestamp = excluded.uploaded_timestamp,
                        description = excluded.description;
                    """,
                    (
                        f["file_id"],
                        mod_id,
                        game_domain,
                        f.get("name", ""),
                        f.get("version", ""),
                        f.get("category_id", 1),
                        f.get("category_name", "MAIN"),
                        f.get("size_bytes", 0),
                        f.get("size_kb", 0),
                        f.get("file_name", ""),
                        f.get("md5"),
                        f.get("sha256"),
                        1 if f.get("is_primary") else 0,
                        f.get("uploaded_timestamp", 0),
                        f.get("description", ""),
                    ),
                )

    def get_files(self, game_domain: str, mod_id: int) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM mod_files WHERE game_domain = ? AND mod_id = ? ORDER BY is_primary DESC, file_id DESC",
            (game_domain, mod_id),
        )
        return [dict(r) for r in cursor.fetchall()]

    def add_dependency(self, dep: dict[str, Any]) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO dependencies (
                    source_game_domain, source_mod_id, target_game_domain,
                    target_mod_id, target_name, dependency_type,
                    version_constraint, description, is_external, external_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dep["source_game_domain"],
                    dep["source_mod_id"],
                    dep["target_game_domain"],
                    dep.get("target_mod_id"),
                    dep.get("target_name"),
                    dep.get("dependency_type", "REQUIRED"),
                    dep.get("version_constraint"),
                    dep.get("description"),
                    1 if dep.get("is_external") else 0,
                    dep.get("external_url"),
                ),
            )

    def get_dependencies(self, game_domain: str, mod_id: int) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM dependencies WHERE source_game_domain = ? AND source_mod_id = ?",
            (game_domain, mod_id),
        )
        return [dict(r) for r in cursor.fetchall()]


class QueueRepository:
    """Repository for download queue operations."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def upsert_item(self, item: dict[str, Any]) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO download_queue (
                    game_domain, mod_id, file_id, file_name, file_size,
                    downloaded_bytes, status, local_path, download_url,
                    hash_expected, hash_algorithm, priority, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(game_domain, mod_id, file_id) DO UPDATE SET
                    file_name = excluded.file_name,
                    file_size = excluded.file_size,
                    download_url = COALESCE(excluded.download_url, download_queue.download_url),
                    hash_expected = COALESCE(excluded.hash_expected, download_queue.hash_expected),
                    hash_algorithm = excluded.hash_algorithm,
                    priority = excluded.priority,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    item["game_domain"],
                    item["mod_id"],
                    item["file_id"],
                    item["file_name"],
                    item.get("file_size", 0),
                    item.get("downloaded_bytes", 0),
                    item.get("status", "WAITING"),
                    item.get("local_path"),
                    item.get("download_url"),
                    item.get("hash_expected"),
                    item.get("hash_algorithm", "md5"),
                    item.get("priority", 0),
                ),
            )

    def update_status(
        self,
        game_domain: str,
        mod_id: int,
        file_id: int,
        status: str,
        error_message: str | None = None,
        downloaded_bytes: int | None = None,
        local_path: str | None = None,
    ) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                UPDATE download_queue
                SET status = ?,
                    error_message = ?,
                    downloaded_bytes = COALESCE(?, downloaded_bytes),
                    local_path = COALESCE(?, local_path),
                    updated_at = CURRENT_TIMESTAMP
                WHERE game_domain = ? AND mod_id = ? AND file_id = ?
                """,
                (status, error_message, downloaded_bytes, local_path, game_domain, mod_id, file_id),
            )

    def get_items_by_status(self, statuses: list[str]) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        placeholders = ",".join("?" for _ in statuses)
        cursor = conn.execute(
            f"SELECT * FROM download_queue WHERE status IN ({placeholders}) ORDER BY priority DESC, id ASC",
            statuses,
        )
        return [dict(r) for r in cursor.fetchall()]

    def reset_in_flight(self) -> None:
        """Reset items that were in downloading or validating state back to waiting."""
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                UPDATE download_queue
                SET status = 'WAITING'
                WHERE status IN ('DOWNLOADING', 'VALIDATING')
                """
            )


class InstallationRepository:
    """Repository for mod installation tracking, file manifests, and repair."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def is_installed(self, game_domain: str, mod_id: int) -> bool:
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT 1 FROM installations WHERE game_domain = ? AND mod_id = ? AND status = 'INSTALLED'",
            (game_domain, mod_id),
        ).fetchone()
        return row is not None

    def get_installation(self, game_domain: str, mod_id: int) -> dict[str, Any] | None:
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT * FROM installations WHERE game_domain = ? AND mod_id = ?",
            (game_domain, mod_id),
        ).fetchone()
        return dict(row) if row else None

    def record_installation(
        self,
        game_domain: str,
        mod_id: int,
        file_id: int,
        mod_name: str,
        version: str,
        profile: str,
        install_dir: str,
        manifest: list[dict[str, Any]],
    ) -> int:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO installations (
                    game_domain, mod_id, file_id, mod_name, version, profile, install_dir, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'INSTALLED', CURRENT_TIMESTAMP)
                ON CONFLICT(game_domain, mod_id) DO UPDATE SET
                    file_id = excluded.file_id,
                    mod_name = excluded.mod_name,
                    version = excluded.version,
                    profile = excluded.profile,
                    install_dir = excluded.install_dir,
                    status = 'INSTALLED',
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (game_domain, mod_id, file_id, mod_name, version, profile, install_dir),
            )
            # Retrieve installation ID
            inst_row = conn.execute(
                "SELECT id FROM installations WHERE game_domain = ? AND mod_id = ?",
                (game_domain, mod_id),
            ).fetchone()
            inst_id = inst_row["id"]

            # Clear prior manifest if update
            conn.execute("DELETE FROM installed_files WHERE installation_id = ?", (inst_id,))

            for item in manifest:
                conn.execute(
                    """
                    INSERT INTO installed_files (installation_id, relative_path, file_size, sha256)
                    VALUES (?, ?, ?, ?)
                    """,
                    (inst_id, item["relative_path"], item["file_size"], item["sha256"]),
                )
            return inst_id

    def get_manifest(self, game_domain: str, mod_id: int) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        inst = self.get_installation(game_domain, mod_id)
        if not inst:
            return []
        cursor = conn.execute(
            "SELECT * FROM installed_files WHERE installation_id = ?",
            (inst["id"],),
        )
        return [dict(r) for r in cursor.fetchall()]

    def list_all_installed(self, game_domain: str | None = None) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        if game_domain:
            cursor = conn.execute(
                "SELECT * FROM installations WHERE game_domain = ? AND status = 'INSTALLED' ORDER BY mod_name ASC",
                (game_domain,),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM installations WHERE status = 'INSTALLED' ORDER BY mod_name ASC"
            )
        return [dict(r) for r in cursor.fetchall()]


class CacheRepository:
    """Repository for persistent key-value metadata caching with TTL."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def get(self, cache_key: str) -> dict[str, Any] | None:
        conn = self.db.get_connection()
        now = int(time.time())
        row = conn.execute(
            "SELECT value_json FROM cache_entries WHERE cache_key = ? AND expires_at > ?",
            (cache_key, now),
        ).fetchone()
        if row:
            try:
                return json.loads(row["value_json"])
            except Exception:
                return None
        return None

    def set(self, cache_key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        conn = self.db.get_connection()
        expires_at = int(time.time()) + ttl_seconds
        value_json = json.dumps(value)
        with conn:
            conn.execute(
                """
                INSERT INTO cache_entries (cache_key, value_json, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    value_json = excluded.value_json,
                    expires_at = excluded.expires_at,
                    created_at = CURRENT_TIMESTAMP;
                """,
                (cache_key, value_json, expires_at),
            )

    def cleanup_expired(self) -> int:
        conn = self.db.get_connection()
        now = int(time.time())
        with conn:
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE expires_at <= ?",
                (now,),
            )
            return cursor.rowcount


class DownloadStoreRepository:
    """Repository managing L3 persistent file download records with composite identity."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def record_download(
        self,
        game_domain: str,
        mod_id: int,
        file_id: int,
        version: str | None,
        filename: str,
        local_path: str,
        file_size: int,
        sha256: str,
        status: str = "VALID",
    ) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO downloads_store (
                    game_domain, mod_id, file_id, version, filename,
                    local_path, file_size, sha256, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(game_domain, mod_id, file_id) DO UPDATE SET
                    version = excluded.version,
                    filename = excluded.filename,
                    local_path = excluded.local_path,
                    file_size = excluded.file_size,
                    sha256 = excluded.sha256,
                    status = excluded.status,
                    created_at = CURRENT_TIMESTAMP;
                """,
                (
                    game_domain,
                    mod_id,
                    file_id,
                    version,
                    filename,
                    local_path,
                    file_size,
                    sha256,
                    status,
                ),
            )

    def get_download(
        self, game_domain: str, mod_id: int, file_id: int
    ) -> dict[str, Any] | None:
        conn = self.db.get_connection()
        row = conn.execute(
            """
            SELECT * FROM downloads_store
            WHERE game_domain = ? AND mod_id = ? AND file_id = ? AND status = 'VALID'
            """,
            (game_domain, mod_id, file_id),
        ).fetchone()
        return dict(row) if row else None

    def list_all_downloads(self, game_domain: str | None = None) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        if game_domain:
            cursor = conn.execute(
                "SELECT * FROM downloads_store WHERE game_domain = ? ORDER BY id DESC",
                (game_domain,),
            )
        else:
            cursor = conn.execute("SELECT * FROM downloads_store ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]

    def delete_record(self, game_domain: str, mod_id: int, file_id: int) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                "DELETE FROM downloads_store WHERE game_domain = ? AND mod_id = ? AND file_id = ?",
                (game_domain, mod_id, file_id),
            )


class UnmanagedRepository:
    """Repository tracking pre-existing, unmanaged files found during startup scans."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def record_unmanaged_file(
        self, game_domain: str, relative_path: str, file_size: int, sha256: str
    ) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO unmanaged_files (game_domain, relative_path, file_size, sha256, scanned_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(game_domain, relative_path) DO UPDATE SET
                    file_size = excluded.file_size,
                    sha256 = excluded.sha256,
                    scanned_at = CURRENT_TIMESTAMP;
                """,
                (game_domain, relative_path, file_size, sha256),
            )

    def list_unmanaged_files(self, game_domain: str) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM unmanaged_files WHERE game_domain = ? ORDER BY relative_path ASC",
            (game_domain,),
        )
        return [dict(r) for r in cursor.fetchall()]

    def is_unmanaged(self, game_domain: str, relative_path: str) -> bool:
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT 1 FROM unmanaged_files WHERE game_domain = ? AND relative_path = ?",
            (game_domain, relative_path),
        ).fetchone()
        return row is not None


class OwnershipRepository:
    """Repository managing fine-grained file ownership and shared dependencies."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def get_owner(self, relative_path: str) -> dict[str, Any] | None:
        norm = relative_path.replace("\\", "/")
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT * FROM file_ownership WHERE relative_path = ?",
            (norm,),
        ).fetchone()
        return dict(row) if row else None

    def record_ownership(
        self,
        relative_path: str,
        mod_name: str,
        mod_group: str,
        sha256: str,
        is_shared: bool = False,
    ) -> None:
        norm = relative_path.replace("\\", "/")
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO file_ownership (relative_path, mod_name, mod_group, sha256, is_shared, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(relative_path) DO UPDATE SET
                    mod_name = excluded.mod_name,
                    mod_group = excluded.mod_group,
                    sha256 = excluded.sha256,
                    is_shared = excluded.is_shared,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (norm, mod_name, mod_group, sha256, 1 if is_shared else 0),
            )

    def list_owned_files(self) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM file_ownership ORDER BY relative_path ASC")
        return [dict(r) for r in cursor.fetchall()]


