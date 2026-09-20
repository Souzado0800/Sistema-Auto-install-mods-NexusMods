"""Synthetic mock server and latency simulator for benchmarking."""

import asyncio
from typing import Any

import httpx


# Synthetic dataset: 30 requested mods + 10 shared dependencies = 40 components
def generate_synthetic_dataset() -> dict[str, Any]:
    mods_db: dict[int, dict[str, Any]] = {}
    files_db: dict[int, list[dict[str, Any]]] = {}

    # 10 core frameworks (IDs 1000 - 1009)
    for i in range(10):
        mod_id = 1000 + i
        mods_db[mod_id] = {
            "name": f"Framework {chr(65 + i)}",
            "author": "CoreTeam",
            "version": "2.0",
            "description": "Fundamental core engine library",
        }
        files_db[mod_id] = [{
            "file_id": 2000 + i,
            "name": f"Framework {chr(65 + i)} Main File",
            "file_name": f"framework_{chr(65 + i).lower()}.zip",
            "size_in_bytes": 1024 * 1024 * 2,  # 2 MB
            "category_id": 1,
            "is_primary": True,
            "uploaded_timestamp": 1700000000,
        }]

    # 30 consumer mods (IDs 101 - 130)
    for i in range(1, 31):
        mod_id = 100 + i
        # Each consumer mod depends on 1 or 2 frameworks
        dep_framework_1 = 1000 + (i % 5)
        dep_framework_2 = 1000 + ((i + 2) % 10)
        desc = (
            f"Mod #{i} requires "
            f'<a href="https://www.nexusmods.com/skyrimspecialedition/mods/{dep_framework_1}">Framework</a> and '
            f'<a href="https://www.nexusmods.com/skyrimspecialedition/mods/{dep_framework_2}">Framework 2</a>.'
        )
        mods_db[mod_id] = {
            "name": f"Expansion Pack {i}",
            "author": f"Author_{i}",
            "version": f"1.{i}",
            "description": desc,
        }
        files_db[mod_id] = [{
            "file_id": 3000 + i,
            "name": f"Expansion Pack {i} Release",
            "file_name": f"expansion_{i}.zip",
            "size_in_bytes": 1024 * 1024 * 5,  # 5 MB
            "category_id": 1,
            "is_primary": True,
            "uploaded_timestamp": 1700000000 + i,
        }]

    return {"mods": mods_db, "files": files_db}


class MockNexusTransport(httpx.AsyncBaseTransport):
    """Simulates Nexus Mods REST API with artificial network latency (e.g. 25ms per roundtrip)."""

    def __init__(self, latency_ms: float = 25.0):
        self.dataset = generate_synthetic_dataset()
        self.latency_seconds = latency_ms / 1000.0
        self.request_count: int = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        if self.latency_seconds > 0:
            await asyncio.sleep(self.latency_seconds)

        url_path = request.url.path

        # /v1/users/validate.json
        if url_path.endswith("/users/validate.json"):
            return httpx.Response(
                200,
                json={"user_id": 1, "name": "BenchmarkUser", "is_premium": True},
            )

        # /games/{game}/mods/{id}.json
        if "/mods/" in url_path and url_path.endswith(".json") and "/files" not in url_path:
            mod_id = int(url_path.split("/")[-1].replace(".json", ""))
            mod_data = self.dataset["mods"].get(mod_id, {"name": f"Mod #{mod_id}", "description": ""})
            return httpx.Response(200, json=mod_data)

        # /games/{game}/mods/{id}/files.json
        if url_path.endswith("/files.json"):
            mod_id = int(url_path.split("/")[-2])
            files = self.dataset["files"].get(mod_id, [])
            return httpx.Response(200, json={"files": files})

        # /download_link.json
        if "download_link.json" in url_path:
            return httpx.Response(
                200,
                json=[{"name": "Synthetic CDN", "URI": "https://cdn.example.com/file.zip"}],
            )

        return httpx.Response(404, json={"message": "Not Found"})
