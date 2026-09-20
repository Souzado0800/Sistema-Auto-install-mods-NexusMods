"""Secure credential storage and retrieval for Nexus Mods API key."""

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICE_NAME = "AutoInstallModMySummerCar"
USERNAME = "nexus_api_key"

USER_CONFIG_DIR = Path.home() / ".config" / "AutoInstallModMySummerCar"
CREDENTIALS_FILE = USER_CONFIG_DIR / "credentials.json"


class CredentialManager:
    """Manages secure retrieval and persistence of sensitive credentials."""

    SERVICE_NAME = "AutoInstallModMySummerCar"
    USERNAME = "nexus_api_key"
    USER_CONFIG_DIR: Path | None = None
    CREDENTIALS_FILE: Path | None = None

    @classmethod
    def _credentials_file(cls) -> Path:
        if cls.CREDENTIALS_FILE is not None:
            return cls.CREDENTIALS_FILE
        return CREDENTIALS_FILE

    @classmethod
    def _user_config_dir(cls) -> Path:
        if cls.USER_CONFIG_DIR is not None:
            return cls.USER_CONFIG_DIR
        return USER_CONFIG_DIR

    @classmethod
    def get_api_key(cls, config_path: Path | None = None) -> str | None:
        """
        Hierarchically resolves the Nexus API key:
        1. NEXUS_API_KEY environment variable.
        2. OS Keyring (SecretService / Keyring).
        3. User-local credentials file (~/.config/AutoInstallModMySummerCar/credentials.json, 0600).
        4. Project config.json.
        """
        # 1. Environment variable
        env_key = os.environ.get("NEXUS_API_KEY", "").strip()
        if env_key:
            return env_key

        # 2. OS Keyring
        try:
            import keyring
            keyring_key = keyring.get_password(cls.SERVICE_NAME, cls.USERNAME)
            if keyring_key and keyring_key.strip():
                return keyring_key.strip()
        except Exception as e:
            logger.debug("Keyring retrieval failed or unavailable: %s", e)

        # 3. User-local secure credentials file
        cred_file = cls._credentials_file()
        if cred_file.exists():
            try:
                data = json.loads(cred_file.read_text(encoding="utf-8"))
                stored_key = data.get("nexus_api_key", "").strip()
                if stored_key:
                    return stored_key
            except Exception as e:
                logger.debug("Reading %s failed: %s", cred_file, e)

        # 4. Project config.json
        cfg_file = config_path or Path("config.json")
        if cfg_file.exists():
            try:
                cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
                cfg_key = cfg_data.get("nexus_api_key", "").strip()
                if cfg_key:
                    return cfg_key
            except Exception as e:
                logger.debug("Reading %s failed: %s", cfg_file, e)

        return None

    @classmethod
    def save_api_key(cls, api_key: str, config_path: Path | None = None) -> bool:
        """
        Securely persists the API key to the OS Keyring and user-local credentials file.
        Returns True if stored successfully in at least one secure store.
        """
        cleaned_key = api_key.strip()
        if not cleaned_key:
            return False

        saved = False

        # 1. Try OS Keyring
        try:
            import keyring
            keyring.set_password(cls.SERVICE_NAME, cls.USERNAME, cleaned_key)
            saved = True
            logger.info("Saved API key to OS Keyring.")
        except Exception as e:
            logger.debug("Keyring storage failed: %s", e)

        # 2. Save to user-local credentials file with 0600 permissions
        try:
            config_dir = cls._user_config_dir()
            config_dir.mkdir(parents=True, exist_ok=True)
            # Restrict directory permissions to 0700
            config_dir.chmod(0o700)

            payload = {"nexus_api_key": cleaned_key}
            cred_file = cls._credentials_file()
            cred_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            # Restrict file permissions to 0600 (owner read/write only)
            cred_file.chmod(0o600)
            saved = True
            logger.info("Saved API key to %s (chmod 0600).", cred_file)
        except Exception as e:
            logger.error("Failed writing credentials file %s: %s", cls._credentials_file(), e)

        # Also populate current process environment
        os.environ["NEXUS_API_KEY"] = cleaned_key
        return saved

    @classmethod
    def delete_api_key(cls) -> bool:
        """Removes the stored API key from keyring and local file without touching unrelated keys."""
        deleted = False
        try:
            import keyring
            keyring.delete_password(cls.SERVICE_NAME, cls.USERNAME)
            deleted = True
        except Exception:
            pass
        cred_file = cls._credentials_file()
        if cred_file.exists():
            try:
                cred_file.unlink()
                deleted = True
            except Exception:
                pass
        os.environ.pop("NEXUS_API_KEY", None)
        return deleted

    @classmethod
    def redact(cls, text: str, api_key: str | None = None) -> str:
        """Redacts the API key from a string or message."""
        if not text:
            return text
        key = api_key or os.environ.get("NEXUS_API_KEY", "")
        if key and len(key) >= 8:
            text = text.replace(key, "[REDACTED_API_KEY]")
        # Redact generic patterns resembling API keys in apikey header or param
        text = re.sub(r'(apikey["\':\s=]+)[a-zA-Z0-9_\-\.]{20,}', r'\1[REDACTED]', text, flags=re.IGNORECASE)
        return text
