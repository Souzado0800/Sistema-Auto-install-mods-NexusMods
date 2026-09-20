"""Official Nexus Mods REST API client (v1)."""

from typing import Any

import httpx

from cache.cache_manager import CacheManager
from utils.logging import get_logger
from utils.retry import RetryConfig, retry_async

from .models import DownloadLink, ModFile, ModMetadata, UserValidate
from .rate_limiter import NexusRateLimiter

logger = get_logger("nexus.api")

BASE_API_URL = "https://api.nexusmods.com/v1"
APP_NAME = "NexusAutoInstaller"
APP_VERSION = "1.0.0"


class NexusApiClient:
    """
    Async client for the official Nexus Mods v1 API.
    Features:
    - Persistent HTTP connection pooling
    - Integration with CacheManager for metadata & files
    - Dynamic header-based rate limiting
    - Automatic retries on transient errors (429, 5xx, timeouts)
    """

    def __init__(
        self,
        api_key: str,
        cache_manager: CacheManager | None = None,
        rate_limiter: NexusRateLimiter | None = None,
        base_url: str = BASE_API_URL,
        timeout: float = 20.0,
    ):
        self.api_key = api_key
        self.cache = cache_manager
        self.rate_limiter = rate_limiter or NexusRateLimiter()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or initialize the persistent httpx client with connection pooling."""
        if self._client is None or self._client.is_closed:
            headers = {
                "apikey": self.api_key,
                "Application-Name": APP_NAME,
                "Application-Version": APP_VERSION,
                "Accept": "application/json",
            }
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout,
                limits=limits,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the persistent HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute request with rate limiting, header tracking, and retries."""
        client = await self.get_client()
        url = f"{self.base_url}{endpoint}"

        async def _do_req() -> httpx.Response:
            await self.rate_limiter.acquire()
            req_headers = dict(client.headers)
            if headers:
                req_headers.update(headers)

            response = await client.request(method, url, params=params, headers=req_headers)
            self.rate_limiter.update_from_headers(response.headers)

            if response.status_code == 429:
                await self.rate_limiter.handle_rate_limited(response)
                response.raise_for_status()

            response.raise_for_status()
            return response

        return await retry_async(_do_req, config=RetryConfig(max_retries=3), op_name=f"API {endpoint}")

    async def validate_key(self) -> UserValidate:
        """Validate user credentials and check membership tier (Free vs Premium)."""
        response = await self._request("GET", "/users/validate.json")
        data = response.json()
        logger.info(f"Authenticated as {data.get('name')} (Premium: {data.get('is_premium', False)})")
        return UserValidate(**data)

    async def get_mod(self, game_domain: str, mod_id: int) -> ModMetadata:
        """Fetch metadata for a mod by game domain and mod ID (cached)."""
        cache_key = f"mod:{game_domain}:{mod_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for mod {cache_key}")
                return ModMetadata(**cached)

        endpoint = f"/games/{game_domain}/mods/{mod_id}.json"
        response = await self._request("GET", endpoint)
        raw_data = response.json()

        metadata = ModMetadata(
            game_domain=game_domain,
            mod_id=mod_id,
            name=raw_data.get("name", "Unknown Mod"),
            author=raw_data.get("author", "Unknown"),
            version=raw_data.get("version"),
            summary=raw_data.get("summary"),
            description=raw_data.get("description"),
            picture_url=raw_data.get("picture_url"),
            updated_timestamp=raw_data.get("updated_timestamp", 0),
        )

        if self.cache:
            self.cache.set(cache_key, metadata.model_dump())

        return metadata

    async def get_mod_files(self, game_domain: str, mod_id: int) -> list[ModFile]:
        """Fetch all files associated with a mod (cached)."""
        cache_key = f"files:{game_domain}:{mod_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for files {cache_key}")
                return [ModFile(**f) for f in cached]

        endpoint = f"/games/{game_domain}/mods/{mod_id}/files.json"
        response = await self._request("GET", endpoint)
        raw_data = response.json()

        files: list[ModFile] = []
        raw_files = raw_data.get("files", [])
        for f in raw_files:
            size_kb_val = f.get("size_kb") or 0
            size_bytes_val = f.get("size_in_bytes") or (size_kb_val * 1024)
            mod_file = ModFile(
                file_id=f["file_id"],
                mod_id=mod_id,
                game_domain=game_domain,
                name=f.get("name") or "",
                version=f.get("version"),
                category_id=f.get("category_id") or 1,
                category_name=f.get("category_name") or "MAIN",
                size_bytes=size_bytes_val,
                size_kb=size_kb_val,
                file_name=f.get("file_name") or "",
                md5=f.get("mod_version"),  # Nexus stores md5 or hash in file metadata if available
                sha256=f.get("sha256"),
                is_primary=bool(f.get("is_primary", False)),
                uploaded_timestamp=f.get("uploaded_timestamp") or 0,
                description=f.get("description"),
            )
            files.append(mod_file)

        if self.cache:
            self.cache.set(cache_key, [f.model_dump() for f in files])

        return files

    async def get_download_links(
        self,
        game_domain: str,
        mod_id: int,
        file_id: int,
        key: str | None = None,
        expires: int | None = None,
    ) -> list[DownloadLink]:
        """
        Request download links for a specific file.
        For Free users, key and expires (from nxm:// protocol or site) are required.
        For Premium users, returns direct CDN links.
        """
        endpoint = f"/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link.json"
        params: dict[str, Any] = {}
        if key:
            params["key"] = key
        if expires:
            params["expires"] = expires

        response = await self._request("GET", endpoint, params=params if params else None)
        links_data = response.json()
        return [DownloadLink(**link) for link in links_data]

    async def get_mod_requirements(
        self,
        game_domain: str,
        mod_id: int,
    ) -> list[dict[str, Any]]:
        """
        Query Nexus Mods GraphQL API v2 for official structured dependencies.
        Returns list of requirement nodes (modId, modName, notes, url, externalRequirement).
        """
        cache_key = f"graphql_reqs:{game_domain}:{mod_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        game_id = "2600" if game_domain.lower() == "mysummercar" else None
        if not game_id:
            return []

        query = """
        query GetModRequirements($modId: ID!, $gameId: ID!) {
          mod(modId: $modId, gameId: $gameId) {
            modRequirements {
              nexusRequirements {
                nodes {
                  modId
                  modName
                  notes
                  url
                  externalRequirement
                }
              }
            }
          }
        }
        """
        client = await self.get_client()
        try:
            resp = await client.post(
                "https://api.nexusmods.com/v2/graphql",
                json={"query": query, "variables": {"modId": str(mod_id), "gameId": str(game_id)}},
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            mod_data = data.get("data", {}).get("mod") or {}
            reqs_data = mod_data.get("modRequirements") or {}
            nexus_reqs = reqs_data.get("nexusRequirements") or {}
            nodes = nexus_reqs.get("nodes") or []

            if self.cache:
                self.cache.set(cache_key, nodes)
            return nodes
        except Exception as e:
            logger.debug(f"GraphQL requirements query failed for {game_domain}:{mod_id}: {e}")
            return []
