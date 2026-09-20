"""My Summer Car and MSCLoader environment auto-detection."""

import logging
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

KNOWN_GAME_CANDIDATES = [
    Path("/home/souza/My Summer Car"),
    Path.home() / "My Summer Car",
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam" / "steamapps" / "common" / "My Summer Car",
    Path.home() / ".steam" / "steam" / "steamapps" / "common" / "My Summer Car",
    Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common" / "My Summer Car",
]


class MSCEnvironment(NamedTuple):
    game_dir: Path
    mods_dir: Path
    is_mscloader_present: bool
    details: str


class MSCDetector:
    """Detects My Summer Car game directories and MSCLoader setup on Linux and Steam."""

    @classmethod
    def detect(cls, preferred_mods_dir: Path | None = None) -> MSCEnvironment | None:
        """
        Auto-detects the game root and mods folder.
        If preferred_mods_dir exists, respects it.
        """
        if preferred_mods_dir and preferred_mods_dir.is_dir():
            # Check if preferred mods dir is valid
            game_dir = preferred_mods_dir.parent if preferred_mods_dir.name == "Mods" else preferred_mods_dir
            is_loader = cls._check_mscloader(game_dir, preferred_mods_dir)
            return MSCEnvironment(
                game_dir=game_dir,
                mods_dir=preferred_mods_dir,
                is_mscloader_present=is_loader,
                details="Preferred mods directory configured",
            )

        # Check known candidates
        for candidate in KNOWN_GAME_CANDIDATES:
            if candidate.exists():
                resolved_game = candidate.resolve()
                mods_dir = candidate / "Mods"
                if not mods_dir.exists():
                    mods_dir = resolved_game / "Mods"

                # If mods dir still doesn't exist, check if game root exists and create Mods if appropriate
                if not mods_dir.exists():
                    mods_dir = resolved_game / "Mods"

                is_loader = cls._check_mscloader(resolved_game, mods_dir)
                return MSCEnvironment(
                    game_dir=resolved_game,
                    mods_dir=mods_dir,
                    is_mscloader_present=is_loader,
                    details=f"Detected at {resolved_game}",
                )

        return None

    @classmethod
    def _check_mscloader(cls, game_dir: Path, mods_dir: Path) -> bool:
        """Checks for MSCLoader files."""
        # Managed dll check
        managed_loader = game_dir / "mysummercar_Data" / "Managed" / "MSCLoader.dll"
        if managed_loader.is_file():
            return True

        # Mods folder check
        if mods_dir.exists() and (mods_dir / "MSCLoader.dll").is_file():
            return True

        # Game root check
        if (game_dir / "MSCLoader.dll").is_file():
            return True

        # If Mods/ directory exists with Assets/ folder, it's configured for MSCLoader
        if mods_dir.exists() and (mods_dir / "Assets").is_dir():
            return True

        return False
