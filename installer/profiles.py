"""Game profiles and path detection."""

import json
from pathlib import Path

from pydantic import BaseModel, Field

from utils.logging import get_logger
from utils.paths import normalize_path

logger = get_logger("nexus.installer.profiles")


class GameProfile(BaseModel):
    """Configuration profile defining game structure and mod installation strategy."""
    game: str
    display_name: str
    mods_directory: str = ""  # Relative to game root (e.g. "Data", "mods")
    archive_types: list[str] = ["zip", "tar", "7z"]
    install_strategy: str = "extract"
    subfolder_mappings: dict[str, str] = Field(default_factory=dict)
    executable_hints: list[str] = Field(default_factory=list)


class ProfileManager:
    """Manages loading game profiles and discovering local game install paths."""

    def __init__(self, profiles_dir: str | Path = "profiles"):
        self.profiles_dir = normalize_path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, GameProfile] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load all .json profile definitions from profiles directory."""
        for file in self.profiles_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                profile = GameProfile(**data)
                self._profiles[profile.game.lower()] = profile
            except Exception as e:
                logger.warning(f"Failed to load profile {file.name}: {e}")

    def get_profile(self, game_domain: str) -> GameProfile:
        """Retrieve profile for game domain, or fallback to generic profile."""
        domain = game_domain.lower()
        if domain in self._profiles:
            return self._profiles[domain]

        # Return generic fallback
        return GameProfile(
            game="generic",
            display_name="Generic Game Profile",
            mods_directory="",
            archive_types=["zip", "tar", "7z"],
            install_strategy="extract",
        )

    @staticmethod
    def detect_game_directory(game_domain: str) -> Path | None:
        """
        Attempt to automatically discover the game installation directory
        across standard Steam, GOG, and Epic Games locations on Linux/Windows.
        """
        home = Path.home()
        candidates: list[Path] = []

        # Linux Steam paths
        steam_linux = [
            home / ".steam" / "steam" / "steamapps" / "common",
            home / ".local" / "share" / "Steam" / "steamapps" / "common",
        ]

        # Map common game domains to directory name hints
        game_names = {
            "skyrimspecialedition": ["Skyrim Special Edition"],
            "skyrim": ["Skyrim"],
            "fallout4": ["Fallout 4"],
            "cyberpunk2077": ["Cyberpunk 2077"],
            "starfield": ["Starfield"],
            "witcher3": ["The Witcher 3"],
            "baldursgate3": ["Baldurs Gate 3"],
        }

        hints = game_names.get(game_domain.lower(), [game_domain])

        for base in steam_linux:
            if base.is_dir():
                for hint in hints:
                    p = base / hint
                    if p.is_dir():
                        candidates.append(p)

        return candidates[0] if candidates else None
