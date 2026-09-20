"""Directed Acyclic Graph (DAG) for dependency resolution and cycle detection."""

from graphlib import TopologicalSorter

from browser.normalizer import CanonicalModKey
from utils.logging import get_logger

from .models import DependencyCycleError, DependencyEdge, DependencyNode

logger = get_logger("nexus.dependencies.graph")


class DependencyGraph:
    """
    Represents a directed graph of mods and dependencies.
    Node: CanonicalModKey
    Edge: A -> B indicates Mod A depends on Mod B.
    Installation order guarantees dependencies (B) are installed before dependees (A).
    """

    def __init__(self):
        self.nodes: dict[CanonicalModKey, DependencyNode] = {}
        # Adjacency list: key -> set of keys it depends on
        self.dependencies: dict[CanonicalModKey, set[CanonicalModKey]] = {}
        self.edges: list[DependencyEdge] = []

    def add_node(self, node: DependencyNode) -> None:
        """Register a mod node in the graph."""
        if node.key not in self.nodes:
            self.nodes[node.key] = node
            self.dependencies[node.key] = set()

    def add_edge(self, edge: DependencyEdge) -> None:
        """Add a directed dependency edge (source depends on target)."""
        self.edges.append(edge)
        if edge.source not in self.dependencies:
            self.dependencies[edge.source] = set()
        self.dependencies[edge.source].add(edge.target)

    def detect_cycles(self) -> list[str] | None:
        """
        Detect if any directed cycles exist in the graph using DFS 3-color traversal.
        Returns the cycle path as a list of mod keys if found, else None.
        """
        # States: 0 = unvisited (white), 1 = visiting (gray), 2 = visited (black)
        state: dict[CanonicalModKey, int] = {k: 0 for k in self.dependencies}
        path: list[CanonicalModKey] = []

        def dfs(u: CanonicalModKey) -> list[CanonicalModKey] | None:
            state[u] = 1
            path.append(u)

            for v in self.dependencies.get(u, set()):
                if v not in state or state[v] == 0:
                    cycle = dfs(v)
                    if cycle:
                        return cycle
                elif state[v] == 1:
                    # Found cycle: extract subpath from v to current
                    idx = path.index(v)
                    return path[idx:] + [v]

            path.pop()
            state[u] = 2
            return None

        for node_key in list(self.dependencies.keys()):
            if state[node_key] == 0:
                cycle = dfs(node_key)
                if cycle:
                    # Convert to human-readable names
                    return [
                        f"{self.nodes[k].name or str(k)} ({k})" if k in self.nodes else str(k)
                        for k in cycle
                    ]

        return None

    def get_installation_order(self) -> list[DependencyNode]:
        """
        Compute the topological installation order.
        Raises DependencyCycleError if a cycle is present.
        """
        cycle = self.detect_cycles()
        if cycle:
            raise DependencyCycleError(cycle)

        # TopologicalSorter expects: node -> predecessors (dependencies)
        ts: TopologicalSorter = TopologicalSorter()
        for node_key, deps in self.dependencies.items():
            valid_deps = [d for d in deps if d in self.nodes]
            ts.add(node_key, *valid_deps)

        ordered_keys = list(ts.static_order())
        return [self.nodes[k] for k in ordered_keys if k in self.nodes]
