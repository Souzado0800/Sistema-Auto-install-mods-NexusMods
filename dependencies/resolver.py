"""High-level dependency resolver and installation planner."""

import asyncio

from pydantic import BaseModel

from browser.normalizer import CanonicalModKey, NormalizedModUrl
from database.repositories import InstallationRepository, ModRepository
from nexus.api import NexusApiClient
from nexus.models import ModFile, ModMetadata
from nexus.requirements_parser import ParsedRequirement, RequirementType, parse_requirements_from_description
from nexus.resolver import FileResolver
from utils.logging import get_logger

from .graph import DependencyGraph
from .models import DependencyEdge, DependencyNode, DependencyType

logger = get_logger("nexus.dependencies.resolver")


class InstallationPlan(BaseModel):
    """Execution blueprint generated after dependency resolution and deduplication."""
    requested_mods: list[DependencyNode]
    discovered_dependencies: list[DependencyNode]
    already_installed: list[DependencyNode]
    to_download: list[DependencyNode]
    installation_order: list[DependencyNode]
    external_requirements: list[ParsedRequirement]
    conflicts: list[str] = []
    total_download_bytes: int = 0
    requires_user_selection: bool = False
    dependency_data_status: str = "VERIFIED_OFFICIAL_GRAPHQL"
    requested_mods_count: int = 0
    dependency_relations_count: int = 0
    unique_dependencies_count: int = 0
    total_unique_components: int = 0
    shared_in_batch_mods: list[int] = []


class DependencyResolver:
    """
    Coordinates recursive dependency discovery, deduplication,
    cycle checking, and topological installation plan generation.
    """

    def __init__(
        self,
        api_client: NexusApiClient,
        mod_repo: ModRepository | None = None,
        installation_repo: InstallationRepository | None = None,
        install_optional: bool = False,
        concurrency_limit: int = 8,
    ):
        self.api = api_client
        self.mod_repo = mod_repo
        self.inst_repo = installation_repo
        self.install_optional = install_optional
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.graph = DependencyGraph()
        self.external_reqs: list[ParsedRequirement] = []
        self._processed_keys: set[CanonicalModKey] = set()

    async def resolve_plan(self, target_mods: list[NormalizedModUrl]) -> InstallationPlan:
        """Resolve all dependencies for the requested mods and build an InstallationPlan."""
        logger.info(f"Beginning dependency resolution for {len(target_mods)} initial mods...")

        self.graph = DependencyGraph()
        self.external_reqs = []
        self._processed_keys = set()

        # 1. Resolve requested mods and their dependencies recursively
        resolve_tasks = [
            self._resolve_mod_recursive(url, is_requested=True)
            for url in target_mods
        ]
        await asyncio.gather(*resolve_tasks)

        # 2. Check for cycles and determine installation sequence
        installation_order = self.graph.get_installation_order()

        # 3. Categorize nodes
        requested = [n for n in self.graph.nodes.values() if n.is_requested]
        discovered_deps = [n for n in self.graph.nodes.values() if not n.is_requested]
        installed = [n for n in self.graph.nodes.values() if n.is_installed]
        to_download = [n for n in installation_order if not n.is_installed]
        total_bytes = sum(n.file_size for n in to_download)

        dep_relations_count = len(self.graph.edges)
        unique_deps_count = len(discovered_deps)
        total_unique = len(self.graph.nodes)

        # Detect dependencies already present in requested batch
        targets = {e.target for e in self.graph.edges}
        shared_in_batch = [n.mod_id for n in requested if n.key in targets]

        # Populate dependency_of metadata
        for edge in self.graph.edges:
            target_node = self.graph.nodes.get(edge.target)
            if target_node:
                source_node = self.graph.nodes.get(edge.source)
                source_name = source_node.name if source_node else f"Mod #{edge.source.mod_id}"
                if source_name not in target_node.dependency_of:
                    target_node.dependency_of.append(source_name)

        logger.info(
            f"Resolution complete: {len(requested)} requested, {dep_relations_count} relations, "
            f"{unique_deps_count} unique dependencies ({total_unique} total components). "
            f"{len(installed)} already installed, {len(to_download)} need download ({total_bytes / (1024*1024):.2f} MB)."
        )

        return InstallationPlan(
            requested_mods=requested,
            discovered_dependencies=discovered_deps,
            already_installed=installed,
            to_download=to_download,
            installation_order=installation_order,
            external_requirements=self.external_reqs,
            total_download_bytes=total_bytes,
            requested_mods_count=len(requested),
            dependency_relations_count=dep_relations_count,
            unique_dependencies_count=unique_deps_count,
            total_unique_components=total_unique,
            shared_in_batch_mods=shared_in_batch,
        )

    async def _resolve_mod_recursive(
        self,
        mod_target: NormalizedModUrl,
        is_requested: bool = False,
    ) -> DependencyNode | None:
        """Fetch metadata, files, and requirements for a mod, recursing on dependencies."""
        key = mod_target.key

        # Multi-dependee deduplication: if already processed or being processed, reuse node
        if key in self._processed_keys:
            node = self.graph.nodes.get(key)
            if node and is_requested:
                node.is_requested = True
            return node

        self._processed_keys.add(key)

        try:
            async with self.semaphore:
                # 1. Fetch metadata
                meta: ModMetadata = await self.api.get_mod(key.game_domain, key.mod_id)
                if self.mod_repo:
                    self.mod_repo.upsert_mod(meta.model_dump())

                # 2. Fetch available files
                files: list[ModFile] = await self.api.get_mod_files(key.game_domain, key.mod_id)
                if self.mod_repo:
                    self.mod_repo.upsert_files(key.game_domain, key.mod_id, [f.model_dump() for f in files])

            selected_file = FileResolver.select_main_file(files, preferred_file_id=mod_target.file_id)

            # 3. Check if already installed
            is_inst = False
            if self.inst_repo:
                is_inst = self.inst_repo.is_installed(key.game_domain, key.mod_id)

            node = DependencyNode(
                game_domain=key.game_domain,
                mod_id=key.mod_id,
                name=meta.name,
                version=meta.version,
                is_requested=is_requested,
                is_installed=is_inst,
                file_id=selected_file.file_id if selected_file else None,
                file_name=selected_file.file_name if selected_file else None,
                file_size=selected_file.size_bytes if selected_file else 0,
                hash_expected=selected_file.md5 or selected_file.sha256 if selected_file else None,
            )
            self.graph.add_node(node)

            # 4. Extract dependencies: GraphQL API v2 first, augmented by description parsing
            reqs: list[ParsedRequirement] = []
            seen_target_ids: set[int] = set()

            if hasattr(self.api, "get_mod_requirements"):
                try:
                    gql_nodes = await self.api.get_mod_requirements(key.game_domain, key.mod_id)
                    for gn in gql_nodes:
                        tid = gn.get("modId")
                        is_ext = bool(gn.get("externalRequirement")) or (tid is None or tid == 0)
                        clean_target_name = gn.get("modName") or (f"Mod #{tid}" if tid else "External Requirement")

                        if tid and tid > 0:
                            seen_target_ids.add(tid)

                        reqs.append(
                            ParsedRequirement(
                                source_game=key.game_domain,
                                source_mod_id=key.mod_id,
                                target_game=key.game_domain,
                                target_mod_id=tid if (tid and tid > 0) else None,
                                target_name=clean_target_name,
                                dependency_type=RequirementType.REQUIRED,
                                version_constraint=gn.get("notes"),
                                is_external=is_ext,
                                external_url=gn.get("url"),
                            )
                        )
                except Exception as e:
                    logger.debug(f"GraphQL requirement query failed for {key}: {e}")

            # Augment with description parser
            desc_reqs = parse_requirements_from_description(
                key.game_domain, key.mod_id, meta.description
            )
            for dr in desc_reqs:
                if dr.target_mod_id and dr.target_mod_id in seen_target_ids:
                    continue
                reqs.append(dr)

            subtasks = []
            for req in reqs:
                if req.is_external:
                    if req not in self.external_reqs:
                        self.external_reqs.append(req)
                    continue

                if req.target_mod_id:
                    target_key = CanonicalModKey(req.target_game, req.target_mod_id)
                    # Register dependency edge: current mod depends on target mod
                    self.graph.add_edge(
                        DependencyEdge(
                            source=key,
                            target=target_key,
                            dep_type=DependencyType(req.dependency_type),
                            description=req.target_name,
                        )
                    )
                    if self.mod_repo:
                        self.mod_repo.add_dependency({
                            "source_game_domain": key.game_domain,
                            "source_mod_id": key.mod_id,
                            "target_game_domain": req.target_game,
                            "target_mod_id": req.target_mod_id,
                            "target_name": req.target_name,
                            "dependency_type": req.dependency_type,
                        })

                    # Recurse on child dependency
                    child_url = NormalizedModUrl(
                        original_url=f"https://www.nexusmods.com/{req.target_game}/mods/{req.target_mod_id}",
                        game_domain=req.target_game,
                        mod_id=req.target_mod_id,
                    )
                    subtasks.append(self._resolve_mod_recursive(child_url, is_requested=False))

            if subtasks:
                await asyncio.gather(*subtasks)

            return node

        except Exception as e:
            logger.error(f"Error resolving mod {key}: {e}")
            # Create a placeholder node to preserve graph structure
            placeholder = DependencyNode(
                game_domain=key.game_domain,
                mod_id=key.mod_id,
                name=f"Mod #{key.mod_id} (Unresolved)",
                is_requested=is_requested,
            )
            self.graph.add_node(placeholder)
            return placeholder
