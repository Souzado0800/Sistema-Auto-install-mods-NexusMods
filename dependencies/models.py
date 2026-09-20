"""Data models for dependency graph and resolution."""

from enum import StrEnum

from pydantic import BaseModel

from browser.normalizer import CanonicalModKey


class DependencyType(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    RECOMMENDED = "RECOMMENDED"
    INCOMPATIBLE = "INCOMPATIBLE"
    ALREADY_INSTALLED = "ALREADY_INSTALLED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class ComponentState(StrEnum):
    INSTALLED = "INSTALLED"
    ALREADY_INSTALLED = "ALREADY_INSTALLED"
    UPDATED = "UPDATED"
    REPAIRED = "REPAIRED"
    SKIPPED = "SKIPPED"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    BLOCKED_BY_DEPENDENCY = "BLOCKED_BY_DEPENDENCY"
    FAILED_DOWNLOAD = "FAILED_DOWNLOAD"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    FAILED_INSTALL = "FAILED_INSTALL"
    CONFLICT = "CONFLICT"


class DependencyNode(BaseModel):
    game_domain: str
    mod_id: int
    name: str = ""
    version: str | None = None
    is_requested: bool = False
    is_installed: bool = False
    file_id: int | None = None
    file_name: str | None = None
    file_size: int = 0
    download_url: str | None = None
    hash_expected: str | None = None
    state: ComponentState = ComponentState.SKIPPED
    blocked_by: str | None = None
    dependency_of: list[str] = []

    @property
    def key(self) -> CanonicalModKey:
        return CanonicalModKey(self.game_domain, self.mod_id)

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DependencyNode):
            return self.key == other.key
        return False


class DependencyEdge(BaseModel):
    source: CanonicalModKey
    target: CanonicalModKey
    dep_type: DependencyType = DependencyType.REQUIRED
    version_constraint: str | None = None
    description: str | None = None


class DependencyCycleError(Exception):
    """Raised when a circular dependency is detected in the graph."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        cycle_str = " -> ".join(cycle)
        super().__init__(f"Dependency cycle detected: {cycle_str}")
