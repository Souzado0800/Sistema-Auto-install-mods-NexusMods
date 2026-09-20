"""
Intelligent Mod Analyzer for My Summer Car archives.
Inspects internal structure, scores files, classifies roles (Main, Texture/4K, Addon, Fix),
and extracts explicit dependencies.
"""

from pathlib import Path
import os
import re

from core.readers import ArchiveMember, BaseArchiveReader, open_archive
from core.normalizer import ModNormalizer
from utils.logging import get_logger

logger = get_logger("core.analyzer")

DANGEROUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".scr", ".msi", ".com", ".pif", ".reg", ".sh"}
MOD_CODE_EXTENSIONS = {".dll"}
ASSET_EXTENSIONS = {".unity3d", ".assets", ".bundle", ".sharedassets", ".resS"}
TEXTURE_EXTENSIONS = {".png", ".dds", ".jpg", ".jpeg", ".tga", ".bmp", ".tex"}
CONFIG_EXTENSIONS = {".xml", ".ini", ".cfg", ".json", ".yaml", ".yml"}
DOC_EXTENSIONS = {".txt", ".md", ".pdf", ".rtf", ".html"}


class ModType:
    MAIN_FILE = "MAIN FILE"
    TEXTURE_ADDON = "TEXTURE / ADDON"
    ADDON = "ADDON"
    PATCH_FIX = "PATCH / FIX"
    UPDATE = "UPDATE"
    DEPENDENCY = "DEPENDÊNCIA"
    TRANSLATION = "TRADUÇÃO"
    CONFIG = "CONFIGURAÇÃO"
    OPTIONAL = "ARQUIVO OPCIONAL"
    DOCUMENTATION = "DOCUMENTAÇÃO"
    INDEPENDENT = "ARQUIVO INDEPENDENTE"


class ModPackage:
    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        self.filename = self.file_path.name
        self.file_size = self.file_path.stat().st_size if self.file_path.exists() else 0
        self.archive_sha256 = ""

        self.mod_name_detected = ""
        self.base_group_name = ""
        self.version_detected = ""
        self.mod_type = ModType.INDEPENDENT
        self.priority = 50
        self.confidence = 50.0

        self.members: list[ArchiveMember] = []
        self.has_dll = False
        self.has_assets = False
        self.has_textures = False
        self.has_readme = False
        self.has_dangerous_files = False
        self.dangerous_files_list: list[str] = []
        self.detected_dependencies: list[str] = []
        self.readme_members: list[str] = []

        self.resolved_mappings: dict[str, str] = {}
        self.related_main_file: str | None = None
        self.is_group_main = False
        self.decision_status = "PENDING"
        self.decision_message = ""

    def get_asset_folders(self) -> set[str]:
        folders = set()
        for m in self.members:
            parts = [p.strip() for p in m.filename.replace("\\", "/").split("/") if p.strip()]
            if len(parts) >= 2 and parts[0].lower() == "assets":
                folders.add(parts[1].lower())
        return folders

    def get_mod_dlls(self) -> set[str]:
        dlls = set()
        generic = {"mscloader.dll", "raycastcore.dll", "modapi.dll"}
        for m in self.members:
            base = os.path.basename(m.filename).lower()
            if base.endswith(".dll") and base not in generic:
                dlls.add(base)
        return dlls


class ModGroup:
    def __init__(self, group_name: str):
        self.group_name = group_name
        self.packages: list[ModPackage] = []
        self.main_package: ModPackage | None = None

    def add_package(self, pkg: ModPackage):
        self.packages.append(pkg)

    def resolve_relationships(self):
        self.packages.sort(key=lambda p: p.priority, reverse=True)
        if self.packages:
            candidates = [p for p in self.packages if p.mod_type in (ModType.MAIN_FILE, ModType.DEPENDENCY, ModType.INDEPENDENT)]
            if candidates:
                self.main_package = candidates[0]
            else:
                self.main_package = self.packages[0]

            self.main_package.is_group_main = True
            if self.main_package.mod_name_detected:
                self.group_name = self.main_package.mod_name_detected

            for p in self.packages:
                if p != self.main_package:
                    p.related_main_file = self.main_package.mod_name_detected


class ModAnalyzer:
    def __init__(self):
        pass

    def analyze_package(self, pkg: ModPackage) -> bool:
        try:
            with open_archive(pkg.file_path) as reader:
                pkg.members = reader.get_members()
                self._inspect_members(pkg, reader)
        except Exception as e:
            logger.error(f"Falha ao inspecionar {pkg.filename}: {e}")
            pkg.confidence = 0.0
            return False

        pkg.mod_name_detected = ModNormalizer.extract_mod_title(pkg.filename)
        pkg.base_group_name = ModNormalizer.get_base_group_key(pkg.filename)
        pkg.version_detected = ModNormalizer.extract_version(pkg.filename)

        self._calculate_scores_and_classification(pkg)
        return True

    def _inspect_members(self, pkg: ModPackage, reader: BaseArchiveReader):
        non_dir_members = [m for m in pkg.members if not m.is_dir]
        file_exts = {os.path.splitext(m.filename)[1].lower() for m in non_dir_members}

        pkg.has_dll = any(ext in MOD_CODE_EXTENSIONS for ext in file_exts)
        pkg.has_assets = any(ext in ASSET_EXTENSIONS for ext in file_exts)
        pkg.has_textures = any(ext in TEXTURE_EXTENSIONS for ext in file_exts)

        for m in non_dir_members:
            ext = os.path.splitext(m.filename)[1].lower()
            if ext in DANGEROUS_EXTENSIONS:
                pkg.has_dangerous_files = True
                pkg.dangerous_files_list.append(m.filename)

        for m in non_dir_members:
            base_name = os.path.basename(m.filename).lower()
            if base_name in ("readme.txt", "readme.md", "leiame.txt", "instructions.txt", "info.txt"):
                pkg.has_readme = True
                pkg.readme_members.append(m.filename)

        self._detect_dependencies(pkg, reader)

    def _detect_dependencies(self, pkg: ModPackage, reader: BaseArchiveReader):
        text_to_scan = ""
        for m in pkg.members:
            fn_low = os.path.basename(m.filename).lower()
            if fn_low == "raycastcore.dll":
                pkg.detected_dependencies.append("RaycastCore (incluso no pacote)")

        for readme_file in pkg.readme_members[:2]:
            try:
                raw = reader.read_bytes(readme_file)
                text = raw[:16384].decode("utf-8", errors="replace")
                text_to_scan += "\n" + text
            except Exception:
                pass

        if text_to_scan:
            dep_patterns = [
                (r'(?:requires|requer|dependency|dependencia|needs)\s*[:\-]?\s*(mscloader\s*(?:pro)?)', "MSCLoader"),
                (r'(?:requires|requer|dependency|dependencia|needs)\s*[:\-]?\s*(modapi)', "ModAPI"),
                (r'(?:requires|requer|dependency|dependencia|needs)\s*[:\-]?\s*(raycastcore)', "RaycastCore"),
                (r'(?:requires|requer|dependency|dependencia|needs)\s*[:\-]?\s*(playmaker)', "HutongGames PlayMaker"),
            ]
            for pat, dep_name in dep_patterns:
                if re.search(pat, text_to_scan, flags=re.IGNORECASE):
                    if dep_name not in pkg.detected_dependencies:
                        pkg.detected_dependencies.append(dep_name)

    def _calculate_scores_and_classification(self, pkg: ModPackage):
        fn_lower = pkg.filename.lower()
        scores = {
            ModType.MAIN_FILE: 0,
            ModType.TEXTURE_ADDON: 0,
            ModType.ADDON: 0,
            ModType.PATCH_FIX: 0,
            ModType.UPDATE: 0,
            ModType.DEPENDENCY: 0,
            ModType.TRANSLATION: 0,
            ModType.CONFIG: 0,
            ModType.OPTIONAL: 0,
            ModType.DOCUMENTATION: 0
        }

        if any(w in fn_lower for w in ["main file", "main mod", "main"]):
            scores[ModType.MAIN_FILE] += 55
        elif any(w in fn_lower for w in ["core", "base", "original", "full", "complete"]):
            scores[ModType.MAIN_FILE] += 35

        if any(w in fn_lower for w in ["4k", "2k", "8k", "hd", "ultra hd", "texture", "textures", "retexture", "resolution"]):
            scores[ModType.TEXTURE_ADDON] += 50
            scores[ModType.MAIN_FILE] -= 30

        if any(w in fn_lower for w in ["addon", "add-on", "expansion"]):
            scores[ModType.ADDON] += 40
            scores[ModType.MAIN_FILE] -= 15

        if any(w in fn_lower for w in ["patch", "fix", "hotfix", "bugfix", "compatibility"]):
            scores[ModType.PATCH_FIX] += 45
            scores[ModType.MAIN_FILE] -= 20

        if any(w in fn_lower for w in ["update", "upgrade"]):
            scores[ModType.UPDATE] += 35

        if any(w in fn_lower for w in ["localization", "translation", "traducao", "pt-br", "translate"]):
            scores[ModType.TRANSLATION] += 45

        if any(w in fn_lower for w in ["optional", "extra", "alt", "alternative"]):
            scores[ModType.OPTIONAL] += 35
            scores[ModType.MAIN_FILE] -= 20

        # Conteúdo interno tem peso decisivo
        if pkg.has_dll:
            scores[ModType.MAIN_FILE] += 45
            scores[ModType.ADDON] += 20
            scores[ModType.DEPENDENCY] += 15
            scores[ModType.TEXTURE_ADDON] -= 45
        else:
            if pkg.has_assets or pkg.has_textures:
                scores[ModType.TEXTURE_ADDON] += 60
                scores[ModType.MAIN_FILE] -= 60

        non_dirs = [m for m in pkg.members if not m.is_dir]
        all_docs = non_dirs and all(os.path.splitext(m.filename)[1].lower() in DOC_EXTENSIONS for m in non_dirs)
        if all_docs:
            scores[ModType.DOCUMENTATION] += 70
            scores[ModType.MAIN_FILE] = 0

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        priority_map = {
            ModType.DEPENDENCY: 110,
            ModType.MAIN_FILE: 100,
            ModType.UPDATE: 85,
            ModType.PATCH_FIX: 80,
            ModType.ADDON: 75,
            ModType.TEXTURE_ADDON: 70,
            ModType.TRANSLATION: 65,
            ModType.CONFIG: 60,
            ModType.OPTIONAL: 45,
            ModType.DOCUMENTATION: 30,
            ModType.INDEPENDENT: 50
        }

        if best_score <= 15:
            pkg.mod_type = ModType.INDEPENDENT
            pkg.priority = priority_map[ModType.INDEPENDENT]
            pkg.confidence = 70.0
        else:
            pkg.mod_type = best_type
            pkg.priority = priority_map.get(best_type, 50)
            pkg.confidence = min(99.0, max(75.0, 65.0 + (best_score * 0.40)))
