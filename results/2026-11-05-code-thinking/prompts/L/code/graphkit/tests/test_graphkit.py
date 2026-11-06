import math

import pytest

from graphkit import (CycleError, Graph, GraphError, NodeNotFound, has_cycle, parse_edge_list, reachable,
                      shortest_path, strongly_connected_components, to_edge_list, topological_sort)


def build(edges, nodes=()):
    g = Graph()
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(*e)
    return g


def assert_valid_cycle(g, cyc):
    assert len(cyc) >= 2 and cyc[0] == cyc[-1]
    for a, b in zip(cyc, cyc[1:]):
        assert g.has_edge(a, b), (a, b)


def test_add_and_query():
    g = build([("a", "b", 2), ("a", "c"), ("b", "c", 0.5)])
    assert g.nodes() == ["a", "b", "c"]
    assert g.edges() == [("a", "b", 2), ("a", "c", 1.0), ("b", "c", 0.5)]
    assert len(g) == 3 and "a" in g and "z" not in g
    assert g.weight("b", "c") == 0.5
    assert g.successors("a") == ["b", "c"]
    assert g.predecessors("c") == ["a", "b"]


def test_add_node_idempotent_keeps_index():
    g = build([("x", "y")])
    g.add_node("z")
    g.add_node("x")
    assert g.nodes() == ["x", "y", "z"]


def test_replace_edge_keeps_position():
    g = build([("a", "b"), ("a", "c")])
    g.add_edge("a", "b", 7)
    assert g.edges() == [("a", "b", 7), ("a", "c", 1.0)]


def test_negative_weight_rejected():
    with pytest.raises(ValueError):
        Graph().add_edge("a", "b", -1)


def test_remove_edge_and_node():
    g = build([("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")])
    g.remove_edge("a", "b")
    assert not g.has_edge("a", "b")
    with pytest.raises(GraphError):
        g.remove_edge("a", "b")
    g.remove_node("c")
    assert g.nodes() == ["a", "b", "d"]
    assert g.edges() == [("a", "d", 1.0)]
    assert g.predecessors("a") == []
    with pytest.raises(NodeNotFound):
        g.remove_node("c")


def test_missing_node_errors():
    g = build([("a", "b")])
    with pytest.raises(NodeNotFound):
        g.successors("q")
    with pytest.raises(KeyError):
        g.predecessors("q")
    with pytest.raises(GraphError):
        g.weight("b", "a")


def test_toposort_tie_break_by_index():
    g = build([("d", "b"), ("c", "b"), ("b", "a")], nodes=["a", "b", "c", "d", "e"])
    # ready sets: {c,d,e} -> c; {d,e} -> d; {b,e} -> b (index 1); {a,e} -> a; {e}
    assert topological_sort(g) == ["c", "d", "b", "a", "e"]


def test_toposort_simple_chain_ints():
    g = build([(3, 2), (2, 1), (1, 0)])
    assert topological_sort(g) == [3, 2, 1, 0]
    assert not has_cycle(g)


def test_toposort_cycle_error():
    g = build([("a", "b"), ("b", "c"), ("c", "d"), ("d", "b"), ("a", "e")])
    with pytest.raises(CycleError) as ei:
        topological_sort(g)
    assert_valid_cycle(g, ei.value.cycle)
    assert set(ei.value.cycle) == {"b", "c", "d"}
    assert has_cycle(g)
    assert issubclass(CycleError, GraphError)


def test_self_loop_is_cycle():
    g = build([("a", "a")])
    with pytest.raises(CycleError) as ei:
        topological_sort(g)
    assert ei.value.cycle == ["a", "a"]


def test_shortest_path_weighted():
    g = build([("s", "a", 1), ("a", "t", 5), ("s", "b", 2), ("b", "c", 1), ("c", "t", 1), ("s", "t", 10)])
    assert shortest_path(g, "s", "t") == (4, ["s", "b", "c", "t"])


def test_shortest_path_zero_weights_and_same_node():
    g = build([("a", "b", 0), ("b", "c", 0)])
    assert shortest_path(g, "a", "c") == (0, ["a", "b", "c"])
    assert shortest_path(g, "b", "b") == (0, ["b"])


def test_shortest_path_unreachable_and_missing():
    g = build([("a", "b")], nodes=["z"])
    d, p = shortest_path(g, "b", "a")
    assert d == math.inf and p == []
    with pytest.raises(NodeNotFound):
        shortest_path(g, "a", "nope")


def test_shortest_path_float_weights():
    g = build([("a", "b", 0.25), ("b", "c", 0.5), ("a", "c", 1.0)])
    d, p = shortest_path(g, "a", "c")
    assert d == pytest.approx(0.75) and p == ["a", "b", "c"]


def test_reachable():
    g = build([("c", "a"), ("a", "b"), ("d", "c")], nodes=["e"])
    assert g.nodes() == ["e", "c", "a", "b", "d"]
    assert reachable(g, "c") == ["c", "a", "b"]
    assert reachable(g, "e") == ["e"]
    with pytest.raises(NodeNotFound):
        reachable(g, "x")


def test_scc_order_and_content():
    g = build([("a", "b"), ("b", "a"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "c"), ("f", "f")],
              nodes=["g"])
    assert g.nodes() == ["g", "a", "b", "c", "d", "e", "f"]
    assert strongly_connected_components(g) == [["g"], ["a", "b"], ["c", "d", "e"], ["f"]]


def test_scc_deep_path_no_recursion_error():
    g = Graph()
    n = 5000
    for i in range(n - 1):
        g.add_edge(i, i + 1)
    comps = strongly_connected_components(g)
    assert len(comps) == n
    assert comps[0] == [0] and comps[-1] == [n - 1]
    g.add_edge(n - 1, 0)
    assert strongly_connected_components(g) == [list(range(n))]


def test_parse_edge_list():
    text = "# comment\n\n a b 2.5 \nb c\n  # indented comment\nlonely\nc a 0\n"
    g = parse_edge_list(text)
    assert g.nodes() == ["a", "b", "c", "lonely"]
    assert g.edges() == [("a", "b", 2.5), ("b", "c", 1.0), ("c", "a", 0.0)]


@pytest.mark.parametrize("text,line", [("a b\nb c x\n", 2), ("\n\na b -1\n", 3), ("a b 1 2\n", 1)])
def test_parse_errors_have_line_numbers(text, line):
    with pytest.raises(ValueError) as ei:
        parse_edge_list(text)
    assert f"line {line}" in str(ei.value)


def test_to_edge_list_format():
    g = build([("a", "b", 2), ("b", "c", 0.5)], nodes=["iso"])
    assert to_edge_list(g) == "a b 2\nb c 0.5\niso\n"
    assert to_edge_list(Graph()) == ""


def test_round_trip():
    g = build([("n1", "n2", 3), ("n2", "n3", 1.5), ("n3", "n1", 0)], nodes=["solo"])
    h = parse_edge_list(to_edge_list(g))
    assert h.edges() == [(u, v, float(w)) for u, v, w in g.edges()]
    assert set(h.nodes()) == set(g.nodes())
