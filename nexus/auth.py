"""Nexus Mods authentication and credential manager."""

import os

from utils.logging import get_logger

logger = get_logger("nexus.auth")


class AuthError(Exception):
    """Raised when authentication with Nexus Mods fails."""


class CredentialsManager:
    """Manages secure retrieval and validation of the Nexus Mods API key."""

    def __init__(self, api_key: str | None = None):
        self._api_key = self._resolve_api_key(api_key)

    @property
    def api_key(self) -> str:
        if not self._api_key:
            raise AuthError(
                "Nexus Mods API key not found! Please set the 'NEXUS_API_KEY' environment variable "
                "or specify it in config.json.\n"
                "Get your key at: https://www.nexusmods.com/users/myaccount?tab=api"
            )
        return self._api_key

    def has_key(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _resolve_api_key(passed_key: str | None) -> str | None:
        # 1. Passed explicitly in constructor/config
        if passed_key and passed_key.strip():
            return passed_key.strip()

        # 2. Environment variable
        env_key = os.environ.get("NEXUS_API_KEY")
        if env_key and env_key.strip():
            return env_key.strip()

        # 3. Check for .env file in current or parent dirs
        for env_path in [".env", "../.env"]:
            if os.path.isfile(env_path):
                try:
                    with open(env_path, encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("NEXUS_API_KEY="):
                                return line.strip().split("=", 1)[1].strip().strip("'\"")
                except Exception:
                    pass

        return None
