import pytest
import networkx as nx
from src.utilities.plotting import get_predecessors, common_predecessors


def test_get_predecessors():
    digraph = nx.DiGraph()

    nodes = [x for x in range(10)]

    for i in range(10):
        digraph.add_edge(i, i + 1)

    for node in nodes:
        preds = get_predecessors(digraph, node, root=0)
        rev_nodes = [x for x in range(node, -1, -1)]
        assert preds == rev_nodes, f"Predecessors with root incorrect for node {i}."

    for node in nodes:
        preds = get_predecessors(digraph, node)
        rev_nodes = [x for x in range(node, -1, -1)]
        assert preds == rev_nodes, f"Predecessors without root incorrect for node {node}."

    digraph.add_edge(5, 11)
    for j in range(11, 15):
        digraph.add_edge(j, j + 1)

    preds = get_predecessors(digraph, 15, root=0)
    assert preds == [
        15,
        14,
        13,
        12,
        11,
        5,
        4,
        3,
        2,
        1,
        0,
    ], "Predecessors incorrect for branch with root 0."
    preds = get_predecessors(digraph, 15, root=0)
    assert preds == [
        15,
        14,
        13,
        12,
        11,
        5,
        4,
        3,
        2,
        1,
        0,
    ], "Predecessors incorrect for branch with not root."
    preds = get_predecessors(digraph, 15, root=12)
    assert preds == [15, 14, 13, 12], "Predecessors incorrect for branch with root 12."


def test_common_predecessors():
    digraph = nx.DiGraph()

    for i in range(10):
        digraph.add_edge(i, i + 1)

    single_node = [10]
    intersect, union = common_predecessors(digraph, nodes=single_node)
    assert union == {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, "Union for single node is incorrect!"
    assert intersect == union, "Single node's sets don't match each other."

    opposite_ends = [0, 10]
    intersect, union = common_predecessors(digraph, nodes=opposite_ends)
    assert union == {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, "Union for opposite ends is incorrect."
    assert intersect == {0}, "Intersection for opposite ends in incorrect."

    digraph.add_edge(5, 11)
    for j in range(11, 15):
        digraph.add_edge(j, j + 1)

    branch_ends = [10, 15]
    intersect, union = common_predecessors(digraph, nodes=branch_ends)
    assert union == {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}
    assert intersect == {0, 1, 2, 3, 4, 5}, "Intersection for branch ends is incorrect."

    star_digraph_nodes = [x for x in range(10)]

    star_digraph = nx.DiGraph()
    for i in star_digraph_nodes[
        1:
    ]:  # Graph is a central node at 0 with single edge to each of nine other nodes
        star_digraph.add_edge(0, i)

    intersect, union = common_predecessors(star_digraph, nodes=star_digraph_nodes)
    assert union == set(star_digraph_nodes)
    assert intersect == {0}
