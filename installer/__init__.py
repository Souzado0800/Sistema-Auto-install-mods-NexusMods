"""Mod installation, profile management, and safety verification package."""

from .backup import BackupManager
from .extractor import ExtractionResult, SafeArchiveExtractor
from .manager import InstallationManager
from .mscloader import MSCLoaderInspector, MSCLoaderInstallPlan
from .profiles import GameProfile, ProfileManager
from .safety import SafeArchiveGuard, SecurityError
from .scanner import ScanSummary, StartupScanner
from .staging import StagingWorkspace

__all__ = [
    "BackupManager",
    "SafeArchiveGuard",
    "SecurityError",
    "ExtractionResult",
    "SafeArchiveExtractor",
    "GameProfile",
    "ProfileManager",
    "InstallationManager",
    "MSCLoaderInspector",
    "MSCLoaderInstallPlan",
    "StagingWorkspace",
    "StartupScanner",
    "ScanSummary",
]
