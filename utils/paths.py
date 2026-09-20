"""Platform-independent filesystem path utilities."""

from pathlib import Path


def normalize_path(path_input: str | Path) -> Path:
    """Normalize a path to an absolute, resolved Path object."""
    if isinstance(path_input, str):
        path_input = Path(path_input.strip())
    return path_input.expanduser().resolve()


def ensure_dir(dir_path: str | Path) -> Path:
    """Ensure a directory exists, creating all parents if necessary."""
    p = normalize_path(dir_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_relative_path(target_path: str | Path, base_dir: str | Path) -> bool:
    """
    Check if a target path is strictly contained within a base directory.
    Protects against directory traversal attacks (Zip Slip / Tar Slip).
    """
    try:
        resolved_target = normalize_path(target_path)
        resolved_base = normalize_path(base_dir)
        return resolved_target.is_relative_to(resolved_base)
    except (ValueError, RuntimeError):
        return False
