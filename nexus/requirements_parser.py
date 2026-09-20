"""
Strict parser for extracting and classifying dependencies from Nexus Mods descriptions and widgets.
Categorizes requirements into REQUIRED, OPTIONAL, RECOMMENDED, EXTERNAL, MANUAL, UNKNOWN.
"""

from enum import StrEnum
import re
from typing import NamedTuple

from browser.normalizer import normalize_nexus_url
from utils.logging import get_logger

logger = get_logger("nexus.requirements")


class RequirementType(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    RECOMMENDED = "RECOMMENDED"
    EXTERNAL = "EXTERNAL"
    MANUAL = "MANUAL"
    UNKNOWN = "UNKNOWN"


class ParsedRequirement(NamedTuple):
    source_game: str
    source_mod_id: int
    target_game: str
    target_mod_id: int | None
    target_name: str
    dependency_type: RequirementType
    version_constraint: str | None = None
    is_external: bool = False
    external_url: str | None = None


EXTERNAL_DEP_PATTERNS = [
    (re.compile(r"\b(MSCLoader Pro)\b", re.IGNORECASE), "MSCLoader Pro", "https://www.nexusmods.com/mysummercar/mods/532", RequirementType.REQUIRED),
    (re.compile(r"\b(MSCLoader)\b", re.IGNORECASE), "MSCLoader", "https://www.nexusmods.com/mysummercar/mods/147", RequirementType.REQUIRED),
    (re.compile(r"\b(SKSE|Skyrim Script Extender)\b", re.IGNORECASE), "Skyrim Script Extender (SKSE)", "https://skse.silverlock.org/", RequirementType.EXTERNAL),
    (re.compile(r"\b(F4SE|Fallout 4 Script Extender)\b", re.IGNORECASE), "Fallout 4 Script Extender (F4SE)", "https://f4se.silverlock.org/", RequirementType.EXTERNAL),
    (re.compile(r"\b(NVSE|New Vegas Script Extender)\b", re.IGNORECASE), "New Vegas Script Extender (NVSE)", "http://nvse.silverlock.org/", RequirementType.EXTERNAL),
    (re.compile(r"\b(OBSE|Oblivion Script Extender)\b", re.IGNORECASE), "Oblivion Script Extender (OBSE)", "http://obse.silverlock.org/", RequirementType.EXTERNAL),
    (re.compile(r"\b(REDmod|Cyberpunk 2077 REDmod)\b", re.IGNORECASE), "REDmod (Official CDPR DLC)", "https://www.cyberpunk.net/redmod", RequirementType.EXTERNAL),
    (re.compile(r"\b(CET|Cyber Engine Tweaks)\b", re.IGNORECASE), "Cyber Engine Tweaks", "https://www.nexusmods.com/cyberpunk2077/mods/107", RequirementType.REQUIRED),
    (re.compile(r"\b(Address Library for SKSE Plugins)\b", re.IGNORECASE), "Address Library for SKSE Plugins", "https://www.nexusmods.com/skyrimspecialedition/mods/32444", RequirementType.REQUIRED),
]


def classify_context(context_window: str) -> RequirementType:
    """Classifies requirement type based on text context surrounding the link or mention."""
    low = context_window.lower()

    if any(w in low for w in ["optional", "optativo", "opcional", "alternative", "alternativa"]):
        return RequirementType.OPTIONAL

    if any(w in low for w in ["recommended", "recomendado", "suggested", "sugerido", "credits"]):
        return RequirementType.RECOMMENDED

    if any(w in low for w in ["manual install", "instalação manual", "mysummercar_data", "overwrite game"]):
        return RequirementType.MANUAL

    if any(w in low for w in ["requires", "requer", "prerequisite", "pre-requisito", "dependency", "dependencia", "mandatory", "obrigatório"]):
        return RequirementType.REQUIRED

    return RequirementType.UNKNOWN


def parse_requirements_from_description(
    source_game: str,
    source_mod_id: int,
    description_html: str | None,
) -> list[ParsedRequirement]:
    """
    Extract dependencies from a mod's description text/HTML.
    Classifies with strict context into REQUIRED, OPTIONAL, RECOMMENDED, EXTERNAL, MANUAL, or UNKNOWN.
    """
    if not description_html:
        return []

    requirements: list[ParsedRequirement] = []
    seen_keys = set()

    # 1. Find all Nexus Mods hyperlinks inside description with context window
    href_regex = re.compile(
        r'<a\s+(?:[^>]*?\s+)?href=["\'](https?://(?:www\.)?nexusmods\.com/([a-zA-Z0-9_\-]+)/mods/(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for m in href_regex.finditer(description_html):
        full_url, game, target_id_str, anchor_text = m.groups()
        target_id = int(target_id_str)
        # Skip self-references
        if game.lower() == source_game.lower() and target_id == source_mod_id:
            continue

        clean_name = re.sub(r"<[^>]+>", "", anchor_text).strip() or f"Mod #{target_id}"
        req_key = (game.lower(), target_id)
        if req_key in seen_keys:
            continue
        seen_keys.add(req_key)

        # Context window (-100 chars before, +100 chars after)
        start = max(0, m.start() - 100)
        end = min(len(description_html), m.end() + 100)
        ctx = description_html[start:end]
        dep_type = classify_context(ctx)

        requirements.append(
            ParsedRequirement(
                source_game=source_game,
                source_mod_id=source_mod_id,
                target_game=game.lower(),
                target_mod_id=target_id,
                target_name=clean_name,
                dependency_type=dep_type,
                is_external=False,
            )
        )

    # 2. Check for well-known external script extenders or frameworks
    for pattern, name, url, default_type in EXTERNAL_DEP_PATTERNS:
        match = pattern.search(description_html)
        if match:
            start = max(0, match.start() - 80)
            end = min(len(description_html), match.end() + 80)
            ctx = description_html[start:end]
            dep_type = classify_context(ctx)
            if dep_type == RequirementType.UNKNOWN:
                dep_type = default_type

            norm = normalize_nexus_url(url)
            if norm:
                req_key = (norm.game_domain, norm.mod_id)
                if req_key not in seen_keys and not (norm.game_domain == source_game.lower() and norm.mod_id == source_mod_id):
                    seen_keys.add(req_key)
                    requirements.append(
                        ParsedRequirement(
                            source_game=source_game,
                            source_mod_id=source_mod_id,
                            target_game=norm.game_domain,
                            target_mod_id=norm.mod_id,
                            target_name=name,
                            dependency_type=dep_type,
                            is_external=False,
                        )
                    )
            else:
                ext_key = ("external", name)
                if ext_key not in seen_keys:
                    seen_keys.add(ext_key)
                    requirements.append(
                        ParsedRequirement(
                            source_game=source_game,
                            source_mod_id=source_mod_id,
                            target_game=source_game,
                            target_mod_id=None,
                            target_name=name,
                            dependency_type=RequirementType.EXTERNAL,
                            is_external=True,
                            external_url=url,
                        )
                    )

    return requirements
