"""
PathResolver ported from AutoInstallModMySummerCar and enhanced with SafeArchiveGuard.
Resolves archive member paths to target destinations within MSCLoader Mods folder,
performing wrapper stripping, texture/4K asset routing, and README markdown formatting.
"""

from pathlib import Path
import os
import re

from core.analyzer import ModPackage
from installer.safety import SafeArchiveGuard, SecurityError
from utils.logging import get_logger

logger = get_logger("core.resolver")


class PathResolver:
    def __init__(self, mods_dir: Path | str, db_ownership_fn=None):
        self.mods_dir = Path(mods_dir).resolve()
        self.db_ownership_fn = db_ownership_fn
        self.readme_counters: dict[str, int] = {}

    def resolve_package_paths(self, pkg: ModPackage) -> bool:
        """
        Maps each member in pkg.members to a relative destination path inside mods_dir.
        Enforces Zip Slip protection on every mapped path.
        """
        pkg.resolved_mappings.clear()
        file_members = [m for m in pkg.members if not m.is_dir]
        if not file_members:
            return True

        norm_paths = [m.filename.replace("\\", "/") for m in file_members]
        strip_prefix = ""
        try:
            cp = os.path.commonpath(norm_paths).replace("\\", "/")
        except Exception:
            cp = ""

        if cp:
            parts = [p for p in cp.split("/") if p]
            parts_low = [p.lower() for p in parts]
            if "mods" in parts_low:
                mods_idx = parts_low.index("mods")
                strip_prefix = "/".join(parts[:mods_idx + 1]) + "/"
            else:
                single_root = parts[0] + "/"
                sub_paths = [p[len(single_root):].lstrip("/") for p in norm_paths]
                has_sub_dll = any("/" not in p and p.lower().endswith(".dll") for p in sub_paths)
                has_sub_assets = any(p.lower().startswith("assets/") for p in sub_paths)
                if has_sub_dll or has_sub_assets:
                    strip_prefix = single_root
                else:
                    strip_prefix = ""

        for m in file_members:
            raw_path = m.filename
            if strip_prefix and raw_path.startswith(strip_prefix):
                rel_path = raw_path[len(strip_prefix):].lstrip("/")
            else:
                rel_path = raw_path

            base_name_low = os.path.basename(rel_path).lower()
            if base_name_low in ("readme.txt", "readme.md", "leiame.txt", "instructions.txt"):
                rel_path = self._format_readme_name(pkg.mod_name_detected)

            # Zip Slip security check
            try:
                SafeArchiveGuard.validate_destination_path(self.mods_dir, rel_path)
            except SecurityError as sec_err:
                logger.error(f"Path Traversal bloqueado em {pkg.filename}: {raw_path} ({sec_err})")
                continue

            pkg.resolved_mappings[m.filename] = rel_path

        # Roteamento inteligente de complementos/texturas sem DLL
        if not pkg.has_dll and (pkg.has_assets or pkg.has_textures):
            for orig_m, mapped in list(pkg.resolved_mappings.items()):
                mapped_norm = mapped.replace("\\", "/")
                parts = [p for p in mapped_norm.split("/") if p]
                if not parts:
                    continue
                first = parts[0].lower()
                if first not in ("assets", "config", "references") and not mapped_norm.lower().startswith("readme"):
                    disk_asset_dir = self.mods_dir / "Assets" / parts[0]
                    if disk_asset_dir.is_dir():
                        pkg.resolved_mappings[orig_m] = "Assets/" + mapped_norm
                    elif len(parts) == 1:
                        target_asset_dir = self._find_matching_asset_dir(pkg)
                        if target_asset_dir:
                            pkg.resolved_mappings[orig_m] = f"Assets/{target_asset_dir}/{mapped_norm}"
                        else:
                            clean_t = re.sub(r'[\\/:*?"<>| ]', '', pkg.mod_name_detected) or "Assets"
                            pkg.resolved_mappings[orig_m] = f"Assets/{clean_t}/{mapped_norm}"
                    else:
                        pkg.resolved_mappings[orig_m] = "Assets/" + mapped_norm

        return True

    def _find_matching_asset_dir(self, pkg: ModPackage) -> str | None:
        assets_base = self.mods_dir / "Assets"
        if not assets_base.is_dir():
            return None
        existing_dirs = [d.name for d in assets_base.iterdir() if d.is_dir()]
        if not existing_dirs:
            return None

        candidates = [pkg.base_group_name, pkg.mod_name_detected]
        if pkg.related_main_file:
            candidates.insert(0, pkg.related_main_file)

        for cand in candidates:
            if not cand:
                continue
            cand_norm = re.sub(r'[\(\)\[\]\-_ ]', '', cand.lower())
            for ed in existing_dirs:
                ed_norm = re.sub(r'[\(\)\[\]\-_ ]', '', ed.lower())
                if cand_norm == ed_norm or (len(cand_norm) > 4 and cand_norm in ed_norm) or (len(ed_norm) > 4 and ed_norm in cand_norm):
                    return ed
        return None

    def _format_readme_name(self, mod_name: str) -> str:
        clean_name = re.sub(r'[\\/:*?"<>|]', '_', mod_name).strip() or "Mod"
        base_name = f"readme({clean_name}).md"
        dest = self.mods_dir / base_name

        # Se o README base não existe no disco, usa-o
        if not dest.is_file():
            return base_name

        # Se já existe no disco e pertence a este mesmo mod, reutiliza-o sem duplicar!
        if self.db_ownership_fn:
            owner = self.db_ownership_fn(base_name)
            if owner and owner.get("mod_name", "").lower() == mod_name.lower():
                return base_name

        # Caso pertença a outro mod com mesmo nome, busca próximo sufixo livre
        count = 2
        while True:
            candidate = f"readme({clean_name}_{count}).md"
            dest = self.mods_dir / candidate
            if not dest.is_file():
                return candidate
            if self.db_ownership_fn:
                owner = self.db_ownership_fn(candidate)
                if owner and owner.get("mod_name", "").lower() == mod_name.lower():
                    return candidate
            count += 1

