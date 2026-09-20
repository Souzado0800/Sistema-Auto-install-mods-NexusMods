"""Tests for dependency graph DAG, cycle detection, and topological sorting."""

import pytest

from dependencies.graph import DependencyGraph
from dependencies.models import (
    DependencyCycleError,
    DependencyEdge,
    DependencyNode,
    DependencyType,
)


def test_linear_dependency_resolution():
    """
    Mod A depends on Framework B.
    Framework B depends on Library C.
    Topological installation order MUST be: Library C -> Framework B -> Mod A.
    """
    graph = DependencyGraph()

    node_a = DependencyNode(game_domain="skyrim", mod_id=1, name="Mod A", is_requested=True)
    node_b = DependencyNode(game_domain="skyrim", mod_id=2, name="Framework B", is_requested=False)
    node_c = DependencyNode(game_domain="skyrim", mod_id=3, name="Library C", is_requested=False)

    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_node(node_c)

    # Edge: A depends on B
    graph.add_edge(DependencyEdge(source=node_a.key, target=node_b.key, dep_type=DependencyType.REQUIRED))
    # Edge: B depends on C
    graph.add_edge(DependencyEdge(source=node_b.key, target=node_c.key, dep_type=DependencyType.REQUIRED))

    order = graph.get_installation_order()
    order_names = [n.name for n in order]

    assert order_names == ["Library C", "Framework B", "Mod A"]


def test_diamond_dependency_resolution():
    r"""
          Mod A
         /     \
    Framework B  Framework C
         \     /
          Core D
    Installation order: Core D MUST be installed before B and C, and both before A.
    """
    graph = DependencyGraph()

    node_a = DependencyNode(game_domain="skyrim", mod_id=1, name="Mod A")
    node_b = DependencyNode(game_domain="skyrim", mod_id=2, name="Framework B")
    node_c = DependencyNode(game_domain="skyrim", mod_id=3, name="Framework C")
    node_d = DependencyNode(game_domain="skyrim", mod_id=4, name="Core D")

    for n in (node_a, node_b, node_c, node_d):
        graph.add_node(n)

    graph.add_edge(DependencyEdge(source=node_a.key, target=node_b.key))
    graph.add_edge(DependencyEdge(source=node_a.key, target=node_c.key))
    graph.add_edge(DependencyEdge(source=node_b.key, target=node_d.key))
    graph.add_edge(DependencyEdge(source=node_c.key, target=node_d.key))

    order = graph.get_installation_order()
    order_names = [n.name for n in order]

    assert order_names[0] == "Core D"
    assert order_names[-1] == "Mod A"
    assert set(order_names[1:3]) == {"Framework B", "Framework C"}


def test_cycle_detection():
    """
    A -> B -> C -> A
    Must detect cycle and raise DependencyCycleError with cycle path.
    """
    graph = DependencyGraph()

    node_a = DependencyNode(game_domain="skyrim", mod_id=1, name="Mod A")
    node_b = DependencyNode(game_domain="skyrim", mod_id=2, name="Mod B")
    node_c = DependencyNode(game_domain="skyrim", mod_id=3, name="Mod C")

    for n in (node_a, node_b, node_c):
        graph.add_node(n)

    graph.add_edge(DependencyEdge(source=node_a.key, target=node_b.key))
    graph.add_edge(DependencyEdge(source=node_b.key, target=node_c.key))
    graph.add_edge(DependencyEdge(source=node_c.key, target=node_a.key))

    with pytest.raises(DependencyCycleError) as exc_info:
        graph.get_installation_order()

    assert "Dependency cycle detected" in str(exc_info.value)
    assert len(exc_info.value.cycle) >= 3


def test_multi_dependee_deduplication():
    """
    Five mods all depend on the same Core Framework X.
    Core Framework X should appear only once in the installation plan.
    """
    graph = DependencyGraph()
    core_x = DependencyNode(game_domain="skyrim", mod_id=99, name="Core Framework X")
    graph.add_node(core_x)

    for i in range(1, 6):
        mod = DependencyNode(game_domain="skyrim", mod_id=i, name=f"Consumer {i}")
        graph.add_node(mod)
        graph.add_edge(DependencyEdge(source=mod.key, target=core_x.key))

    order = graph.get_installation_order()
    # Core X must be first and appear exactly once
    assert order[0].name == "Core Framework X"
    assert len(order) == 6
    assert [n.name for n in order].count("Core Framework X") == 1
