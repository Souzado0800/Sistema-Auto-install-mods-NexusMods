"""Database schema migrations and initialization."""

from utils.logging import get_logger

from .connection import DatabaseConnection

logger = get_logger("nexus.database.migrations")

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS mods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_domain TEXT NOT NULL,
        mod_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        author TEXT,
        version TEXT,
        summary TEXT,
        description TEXT,
        picture_url TEXT,
        updated_timestamp INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(game_domain, mod_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS mod_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL UNIQUE,
        mod_id INTEGER NOT NULL,
        game_domain TEXT NOT NULL,
        name TEXT NOT NULL,
        version TEXT,
        category_id INTEGER,
        category_name TEXT,
        size_bytes INTEGER,
        size_kb INTEGER,
        file_name TEXT,
        md5 TEXT,
        sha256 TEXT,
        is_primary BOOLEAN DEFAULT 0,
        uploaded_timestamp INTEGER,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_game_domain TEXT NOT NULL,
        source_mod_id INTEGER NOT NULL,
        target_game_domain TEXT NOT NULL,
        target_mod_id INTEGER,
        target_name TEXT,
        dependency_type TEXT NOT NULL, -- REQUIRED, OPTIONAL, RECOMMENDED, INCOMPATIBLE
        version_constraint TEXT,
        description TEXT,
        is_external BOOLEAN DEFAULT 0,
        external_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_game_domain, source_mod_id, target_game_domain, target_mod_id, dependency_type, external_url)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS download_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_domain TEXT NOT NULL,
        mod_id INTEGER NOT NULL,
        file_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER DEFAULT 0,
        downloaded_bytes INTEGER DEFAULT 0,
        status TEXT NOT NULL, -- DISCOVERED, WAITING, DOWNLOADING, DOWNLOADED, VALIDATING, VALID, FAILED, INSTALLING, INSTALLED, SKIPPED
        local_path TEXT,
        download_url TEXT,
        hash_expected TEXT,
        hash_algorithm TEXT DEFAULT 'md5',
        priority INTEGER DEFAULT 0,
        error_message TEXT,
        retry_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(game_domain, mod_id, file_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS installations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_domain TEXT NOT NULL,
        mod_id INTEGER NOT NULL,
        file_id INTEGER NOT NULL,
        mod_name TEXT NOT NULL,
        version TEXT,
        profile TEXT NOT NULL,
        install_dir TEXT NOT NULL,
        status TEXT NOT NULL, -- INSTALLED, CORRUPTED, UNINSTALLED
        installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(game_domain, mod_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS installed_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        installation_id INTEGER NOT NULL,
        relative_path TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(installation_id) REFERENCES installations(id) ON DELETE CASCADE,
        UNIQUE(installation_id, relative_path)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cache_entries (
        cache_key TEXT PRIMARY KEY,
        value_json TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_name TEXT NOT NULL,
        metric_value REAL NOT NULL,
        details_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS downloads_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_domain TEXT NOT NULL,
        mod_id INTEGER NOT NULL,
        file_id INTEGER NOT NULL,
        version TEXT,
        filename TEXT NOT NULL,
        local_path TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'VALID',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(game_domain, mod_id, file_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS unmanaged_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_domain TEXT NOT NULL,
        relative_path TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(game_domain, relative_path)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS file_ownership (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        relative_path TEXT NOT NULL UNIQUE,
        mod_name TEXT NOT NULL,
        mod_group TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        is_shared BOOLEAN DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_mods_game_id ON mods(game_domain, mod_id);
    CREATE INDEX IF NOT EXISTS idx_files_mod_id ON mod_files(game_domain, mod_id);
    CREATE INDEX IF NOT EXISTS idx_deps_source ON dependencies(source_game_domain, source_mod_id);
    CREATE INDEX IF NOT EXISTS idx_deps_target ON dependencies(target_game_domain, target_mod_id);
    CREATE INDEX IF NOT EXISTS idx_queue_status ON download_queue(status);
    CREATE INDEX IF NOT EXISTS idx_installed_game_mod ON installations(game_domain, mod_id);
    CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);
    CREATE INDEX IF NOT EXISTS idx_downloads_store_lookup ON downloads_store(game_domain, mod_id, file_id);
    CREATE INDEX IF NOT EXISTS idx_unmanaged_lookup ON unmanaged_files(game_domain, relative_path);
    CREATE INDEX IF NOT EXISTS idx_file_ownership_path ON file_ownership(relative_path);
    """,
]


def init_db(db_conn: DatabaseConnection) -> None:
    """Initialize database tables and indexes."""
    conn = db_conn.get_connection()
    with conn:
        for stmt in SCHEMA_STATEMENTS:
            conn.executescript(stmt)
    logger.info("Database schema initialized successfully.")
