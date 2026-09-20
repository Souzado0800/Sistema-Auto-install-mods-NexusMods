"""Pydantic domain models for Nexus Mods data."""

from enum import Enum, StrEnum

from pydantic import BaseModel


class UserTier(StrEnum):
    FREE = "free"
    SUPPORTER = "supporter"
    PREMIUM = "premium"


class UserValidate(BaseModel):
    user_id: int
    name: str
    is_premium: bool = False
    is_supporter: bool = False
    email: str | None = None
    profile_url: str | None = None

    @property
    def tier(self) -> UserTier:
        if self.is_premium:
            return UserTier.PREMIUM
        if self.is_supporter:
            return UserTier.SUPPORTER
        return UserTier.FREE


class ModMetadata(BaseModel):
    game_domain: str
    mod_id: int
    name: str
    author: str | None = "Unknown"
    version: str | None = None
    summary: str | None = None
    description: str | None = None
    picture_url: str | None = None
    updated_timestamp: int | None = 0

    @property
    def canonical_url(self) -> str:
        return f"https://www.nexusmods.com/{self.game_domain}/mods/{self.mod_id}"


class FileCategory(int, Enum):
    MAIN = 1
    UPDATE = 2
    OPTIONAL = 3
    OLD_VERSION = 4
    MISCELLANEOUS = 5


class ModFile(BaseModel):
    file_id: int
    mod_id: int
    game_domain: str
    name: str
    version: str | None = None
    category_id: int = 1
    category_name: str = "MAIN"
    size_bytes: int = 0
    size_kb: int = 0
    file_name: str = ""
    md5: str | None = None
    sha256: str | None = None
    is_primary: bool = False
    uploaded_timestamp: int = 0
    description: str | None = None

    @property
    def is_main(self) -> bool:
        return self.category_id == 1 or self.category_name.upper() == "MAIN"


class DownloadLink(BaseModel):
    name: str
    short_name: str | None = None
    URI: str


class RateLimitStatus(BaseModel):
    hourly_limit: int = 500
    hourly_remaining: int = 500
    hourly_reset: str | None = None
    daily_limit: int = 20000
    daily_remaining: int = 20000
    daily_reset: str | None = None
