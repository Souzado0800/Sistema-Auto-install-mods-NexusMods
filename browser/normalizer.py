"""Nexus Mods URL normalization and canonical key extraction."""

import re
from typing import NamedTuple
from urllib.parse import parse_qs, urlparse


class CanonicalModKey(NamedTuple):
    game_domain: str
    mod_id: int

    def __str__(self) -> str:
        return f"{self.game_domain}:{self.mod_id}"


class NormalizedModUrl:
    """Represents a validated and normalized Nexus Mods URL."""

    def __init__(
        self,
        original_url: str,
        game_domain: str,
        mod_id: int,
        file_id: int | None = None,
        nxm_key: str | None = None,
        nxm_expires: int | None = None,
        name: str | None = None,
    ):
        self.original_url = original_url
        self.game_domain = game_domain.lower()
        self.mod_id = mod_id
        self.file_id = file_id
        self.nxm_key = nxm_key
        self.nxm_expires = nxm_expires
        self.name = name

    @property
    def key(self) -> CanonicalModKey:
        return CanonicalModKey(self.game_domain, self.mod_id)

    @property
    def canonical_url(self) -> str:
        return f"https://www.nexusmods.com/{self.game_domain}/mods/{self.mod_id}"

    def __repr__(self) -> str:
        return f"NormalizedModUrl({self.canonical_url})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, NormalizedModUrl):
            return self.key == other.key
        return False

    def __hash__(self) -> int:
        return hash(self.key)


# Regex patterns for web URLs and nxm:// links
WEB_MOD_REGEX = re.compile(
    r"^https?://(?:www\.)?nexusmods\.com/(?P<game>[a-zA-Z0-9_\-]+)/mods/(?P<id>\d+)",
    re.IGNORECASE,
)
NXM_MOD_REGEX = re.compile(
    r"^nxm://(?P<game>[a-zA-Z0-9_\-]+)/mods/(?P<id>\d+)(?:/files/(?P<file_id>\d+))?",
    re.IGNORECASE,
)


def normalize_nexus_url(raw_url: str) -> NormalizedModUrl | None:
    """
    Parse and normalize a raw Nexus Mods URL into a canonical representation.
    Returns None if the URL does not represent a valid Nexus mod page.
    """
    cleaned = raw_url.strip()
    if not cleaned or cleaned.startswith("#"):
        return None

    # Check NXM protocol: nxm://<game>/mods/<id>/files/<file_id>?key=...&expires=...
    if cleaned.lower().startswith("nxm://"):
        match = NXM_MOD_REGEX.match(cleaned)
        if match:
            game = match.group("game").lower()
            mod_id = int(match.group("id"))
            file_id = int(match.group("file_id")) if match.group("file_id") else None

            # Parse query params for nxm key/expires
            parsed = urlparse(cleaned)
            params = parse_qs(parsed.query)
            key = params.get("key", [None])[0]
            expires = int(params.get("expires", [0])[0]) if params.get("expires") else None

            return NormalizedModUrl(
                original_url=cleaned,
                game_domain=game,
                mod_id=mod_id,
                file_id=file_id,
                nxm_key=key,
                nxm_expires=expires,
            )
        return None

    # Check Web URL: https://www.nexusmods.com/<game>/mods/<id>
    match = WEB_MOD_REGEX.search(cleaned)
    if match:
        game = match.group("game").lower()
        mod_id = int(match.group("id"))
        return NormalizedModUrl(
            original_url=cleaned,
            game_domain=game,
            mod_id=mod_id,
        )

    return None
