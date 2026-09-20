"""Database persistence layer for Nexus Mods AutoInstaller."""

from .connection import DatabaseConnection
from .migrations import init_db
from .repositories import (
    CacheRepository,
    DownloadStoreRepository,
    InstallationRepository,
    ModRepository,
    OwnershipRepository,
    QueueRepository,
    UnmanagedRepository,
)

__all__ = [
    "CacheRepository",
    "DatabaseConnection",
    "DownloadStoreRepository",
    "InstallationRepository",
    "ModRepository",
    "OwnershipRepository",
    "QueueRepository",
    "UnmanagedRepository",
    "init_db",
]

