"""Security policies, path traversal (Zip Slip) guards, and binary execution blockers."""

from pathlib import Path

from utils.logging import get_logger
from utils.paths import normalize_path

logger = get_logger("nexus.installer.safety")

# Dangerous executable and script file extensions that must NEVER be executed automatically
BLOCKED_EXECUTABLE_EXTENSIONS: set[str] = {
    ".exe",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".vbs",
    ".com",
    ".msi",
    ".scr",
}


class SecurityError(Exception):
    """Raised when an archive violates filesystem security boundaries (e.g. Zip Slip)."""


class SafeArchiveGuard:
    """Guards against path traversal and malicious archive extraction."""

    @staticmethod
    def validate_destination_path(base_dir: str | Path, relative_member_path: str) -> Path:
        """
        Validate that a file extracted from an archive stays strictly within base_dir.
        Protects against Zip Slip / Tar Slip directory traversal attacks.
        """
        resolved_base = normalize_path(base_dir)

        # Sanitize member path: strip leading slashes and drive letters
        cleaned_path = relative_member_path.replace("\\", "/").lstrip("/")
        if ":" in cleaned_path:
            cleaned_path = cleaned_path.split(":", 1)[1].lstrip("/")

        target_path = (resolved_base / cleaned_path).resolve()

        if not target_path.is_relative_to(resolved_base):
            raise SecurityError(
                f"Path traversal detected! Archive member '{relative_member_path}' escapes target directory '{resolved_base}'."
            )

        return target_path

    @staticmethod
    def scan_for_executables(filenames: list[str]) -> list[str]:
        """
        Scan archive member filenames for dangerous executables or scripts.
        Returns the list of detected executable files.
        """
        detected: list[str] = []
        for name in filenames:
            ext = Path(name).suffix.lower()
            if ext in BLOCKED_EXECUTABLE_EXTENSIONS:
                detected.append(name)
                logger.warning(
                    f"Executable detected inside archive: '{name}'. "
                    "Automatic execution is strictly prohibited by security policy."
                )
        return detected
