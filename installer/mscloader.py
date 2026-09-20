"""Smart MSCLoader archive structure inspector and installation planner."""

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("nexus.installer.mscloader")

IGNORED_DOC_EXTENSIONS = {".txt", ".md", ".pdf", ".url", ".png", ".jpg", ".jpeg"}


@dataclass
class MSCLoaderInstallPlan:
    """Explicit mapping from archive members to destinations within /home/souza/My Summer Car/Mods."""

    mod_name: str
    file_mappings: list[tuple[str, str]] = field(default_factory=list)  # (archive_path, dest_rel_to_mods)
    unsupported_files: list[tuple[str, str]] = field(default_factory=list)  # (filename, reason)
    is_automatic: bool = True
    dll_count: int = 0

    @property
    def requires_manual(self) -> bool:
        return not self.is_automatic or len(self.unsupported_files) > 0


class MSCLoaderInspector:
    """
    Inspects archive structure without blind extractall.
    Detects wrappers (Mods/, ModName/), assets, and non-standard game-root files.
    """

    @staticmethod
    def inspect_archive(archive_path: Path, mod_name: str = "") -> MSCLoaderInstallPlan:
        plan = MSCLoaderInstallPlan(mod_name=mod_name or archive_path.stem)

        if not archive_path.is_file():
            plan.is_automatic = False
            plan.unsupported_files.append((str(archive_path), "Archive file not found"))
            return plan

        # Inspect member names inside zip
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                members = [m for m in zf.namelist() if not m.endswith("/")]
        except Exception as e:
            plan.is_automatic = False
            plan.unsupported_files.append((archive_path.name, f"Failed to inspect archive: {e}"))
            return plan

        # Check for non-standard files (e.g. game root overrides, executables)
        for member in members:
            p = Path(member)
            if p.suffix.lower() in (".exe", ".bat", ".cmd", ".sh"):
                plan.unsupported_files.append((member, "Executable binary requires manual installation"))
                plan.is_automatic = False
            elif "mysummercar_data" in member.lower():
                plan.unsupported_files.append((member, "Mod targets game root mysummercar_Data instead of Mods/ folder"))
                plan.is_automatic = False

        if not plan.is_automatic:
            return plan

        # Determine wrapper prefix
        prefix_to_strip = MSCLoaderInspector._find_wrapper_prefix(members)

        for member in members:
            p = Path(member)
            ext = p.suffix.lower()

            # Skip documentation at archive root unless part of an assets subfolder
            if ext in IGNORED_DOC_EXTENSIONS and ("/" not in member or member.count("/") == 1):
                logger.debug(f"Ignoring documentation file from install: {member}")
                continue

            # Strip wrapper prefix
            rel_dest = member
            if prefix_to_strip and rel_dest.startswith(prefix_to_strip):
                rel_dest = rel_dest[len(prefix_to_strip):].lstrip("/")

            # Clean and normalize destination relative to Mods/
            dest_path = Path(rel_dest)

            # Prevent empty destination
            if not str(dest_path) or str(dest_path) == ".":
                continue

            # Count DLLs
            if dest_path.suffix.lower() == ".dll":
                plan.dll_count += 1

            plan.file_mappings.append((member, str(dest_path)))

        if plan.dll_count == 0 and not any(m[1].startswith("Assets") for m in plan.file_mappings):
            plan.unsupported_files.append((archive_path.name, "No MSCLoader .dll or Assets directory found in archive"))
            plan.is_automatic = False

        return plan

    @staticmethod
    def _find_wrapper_prefix(members: list[str]) -> str | None:
        """
        Identify redundant wrapper folders like 'Mods/' or 'ModName/' containing the DLL.
        """
        # Case 1: Wrapped in 'Mods/' folder (e.g. Mods/MyMod.dll)
        if all(m.startswith("Mods/") or m.startswith("mods/") for m in members if not m.endswith("/")):
            # Common prefix is Mods/
            sample = next(m for m in members if m.lower().startswith("mods/"))
            prefix = sample.split("/", 1)[0] + "/"
            return prefix

        # Case 2: Wrapped in a single top-level folder (e.g. ModName/ModName.dll)
        top_dirs = {m.split("/")[0] for m in members if "/" in m}
        has_root_files = any("/" not in m for m in members)

        if len(top_dirs) == 1 and not has_root_files:
            wrapper = list(top_dirs)[0]
            # Check if there is a DLL directly inside this wrapper
            dll_inside_wrapper = any(
                m.startswith(f"{wrapper}/") and m.count("/") == 1 and m.lower().endswith(".dll")
                for m in members
            )
            if dll_inside_wrapper:
                return f"{wrapper}/"

        return None
