"""Nexus Mods API integration and models package."""

from .api import BASE_API_URL, NexusApiClient
from .auth import AuthError, CredentialsManager
from .models import (
    DownloadLink,
    FileCategory,
    ModFile,
    ModMetadata,
    RateLimitStatus,
    UserTier,
    UserValidate,
)
from .rate_limiter import NexusRateLimiter
from .requirements_parser import ParsedRequirement, parse_requirements_from_description
from .resolver import FileResolver

__all__ = [
    "BASE_API_URL",
    "AuthError",
    "CredentialsManager",
    "DownloadLink",
    "FileCategory",
    "FileResolver",
    "ModFile",
    "ModMetadata",
    "NexusApiClient",
    "NexusRateLimiter",
    "ParsedRequirement",
    "RateLimitStatus",
    "UserTier",
    "UserValidate",
    "parse_requirements_from_description",
]
