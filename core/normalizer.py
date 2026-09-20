"""
Mod filename normalizer and relation detector from AutoInstallModMySummerCar.
Removes Nexus suffixes, extracts semantic versions, base titles, and groups related mods.
"""

import difflib
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.analyzer import ModPackage


class ModNormalizer:
    @staticmethod
    def clean_nexus_suffix(name: str) -> str:
        """Removes Nexus Mods upload IDs and timestamps, e.g. -1801-1-3-1682251911 and file_123_ prefix."""
        cleaned = re.sub(r'^file_\d+_', '', name, flags=re.IGNORECASE)
        cleaned = re.sub(r'[-_]\d+-[0-9a-zA-Z]+(?:-[0-9a-zA-Z]+)*-\d{9,12}$', '', cleaned)
        cleaned = re.sub(r'\s*\d+\s+[\d\.]+\s+\d{4}-\d{2}-\d{2}T.*$', '', cleaned)
        cleaned = re.sub(r'[-_]\d{9,12}$', '', cleaned)
        return cleaned.strip()


    @staticmethod
    def extract_version(filename: str) -> str:
        match = re.search(r'\bv?(\d+(?:\.\d+)+(?:[a-zA-Z])?)\b', filename)
        if match:
            return match.group(1)
        nexus_match = re.search(r'[-_]\d+-([0-9a-zA-Z]+(?:-[0-9a-zA-Z]+)*)-\d{9,12}', filename)
        if nexus_match:
            return nexus_match.group(1).replace("-", ".")
        return ""

    @staticmethod
    def extract_mod_title(filename: str) -> str:
        base, _ = os.path.splitext(filename)
        cleaned = ModNormalizer.clean_nexus_suffix(base)
        cleaned = re.sub(r'[\s\-_]+v?\d+(\.\d+)+[a-zA-Z]?$', '', cleaned, flags=re.IGNORECASE)
        t = re.sub(r'\b(main file|main mod|main)\b', '', cleaned, flags=re.IGNORECASE)
        t = re.sub(r'\b(4k|2k|8k|hd|ultra hd|texture|textures)\b', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\s+', ' ', t).strip(' -_')
        return t or cleaned


    @staticmethod
    def get_base_group_key(filename: str) -> str:
        base, _ = os.path.splitext(filename)
        cleaned = ModNormalizer.clean_nexus_suffix(base)
        keywords_to_strip = [
            r'\bmain file\b', r'\bmain mod\b', r'\bmain\b', r'\bcore mod\b', r'\bbase mod\b',
            r'\boriginal\b', r'\bfull\b', r'\bcomplete\b',
            r'\b4k\b', r'\b2k\b', r'\b8k\b', r'\bhd\b', r'\bultra hd\b',
            r'\btexture\b', r'\btextures\b', r'\bretexture\b', r'\bhigh res\b', r'\blow res\b',
            r'\baddon\b', r'\badd-on\b', r'\bpatch\b', r'\bfix\b', r'\bhotfix\b',
            r'\bupdate\b', r'\boptional file\b', r'\boptional\b',
            r'\bv?\d+(\.\d+)+[a-z]?\b'
        ]
        result = cleaned
        for kw in keywords_to_strip:
            result = re.sub(kw, ' ', result, flags=re.IGNORECASE)
        result = re.sub(r'[\(\)\[\]\-_]', ' ', result)
        result = re.sub(r'\s+', ' ', result).strip().lower()
        return result

    @staticmethod
    def are_mods_related(pkg_a: "ModPackage", pkg_b: "ModPackage") -> tuple[bool, float]:
        if pkg_a.base_group_name and pkg_a.base_group_name == pkg_b.base_group_name:
            return True, 0.98

        dlls_a = pkg_a.get_mod_dlls()
        dlls_b = pkg_b.get_mod_dlls()
        if dlls_a and dlls_b and dlls_a.intersection(dlls_b):
            return True, 0.96

        assets_a = pkg_a.get_asset_folders()
        assets_b = pkg_b.get_asset_folders()
        if assets_a and assets_b and assets_a.intersection(assets_b):
            return True, 0.95

        for dll in dlls_a:
            dll_norm = re.sub(r'[\(\)\[\]\-_ ]', '', dll.replace('.dll', '').lower())
            for asset_f in assets_b:
                asset_norm = re.sub(r'[\(\)\[\]\-_ ]', '', asset_f.lower())
                if dll_norm == asset_norm or (len(dll_norm) > 4 and dll_norm in asset_norm):
                    return True, 0.94

        for dll in dlls_b:
            dll_norm = re.sub(r'[\(\)\[\]\-_ ]', '', dll.replace('.dll', '').lower())
            for asset_f in assets_a:
                asset_norm = re.sub(r'[\(\)\[\]\-_ ]', '', asset_f.lower())
                if dll_norm == asset_norm or (len(dll_norm) > 4 and dll_norm in asset_norm):
                    return True, 0.94

        words_a = pkg_a.base_group_name.split()
        words_b = pkg_b.base_group_name.split()
        if words_a and words_b:
            last_a = words_a[-1]
            last_b = words_b[-1]
            if (last_a.isdigit() or last_b.isdigit()) and last_a != last_b:
                return False, 0.0

        ratio = difflib.SequenceMatcher(None, pkg_a.base_group_name, pkg_b.base_group_name).ratio()
        if ratio >= 0.92:
            return True, ratio

        return False, ratio
