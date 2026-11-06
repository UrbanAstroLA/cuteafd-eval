Build a Python package named `graphkit`: a directed, weighted graph with standard algorithms and a plain-text edge-list format. Python 3.12, standard library only.

## Files

- `graphkit/__init__.py` — re-exports `Graph`, `GraphError`, `CycleError`, `NodeNotFound`, `topological_sort`, `has_cycle`, `shortest_path`, `strongly_connected_components`, `reachable`, `parse_edge_list`, `to_edge_list`.
- `graphkit/errors.py` — the exception classes.
- `graphkit/graph.py` — `Graph`.
- `graphkit/algorithms.py` — the algorithms.
- `graphkit/io.py` — the text format.

## errors.py

- `GraphError(Exception)` — base class.
- `NodeNotFound(GraphError, KeyError)` — raised when an operation names a node that is not in the graph.
- `CycleError(GraphError)` — `CycleError(cycle)` stores attribute `cycle`: a list of nodes `[n0, n1, ..., nk]` with `nk == n0` and an edge from each element to the next.

## graph.py

Nodes are hashable values (tests use strings and ints). The graph remembers insertion order: a node's *index* is its position in insertion order, and every ordering rule below refers to it.

- `Graph()` — empty graph.
- `add_node(n)` — add `n` if absent (adding an existing node changes nothing, including its index).
- `add_edge(u, v, weight=1.0)` — add both endpoints if absent (`u` first), then add or replace the edge `u -> v`. `weight` is an int or float `>= 0`; a negative weight raises `ValueError`. Self-loops are allowed.
- `remove_edge(u, v)` — remove the edge; raises `GraphError` if it does not exist.
- `remove_node(n)` — remove `n` and all edges touching it; raises `NodeNotFound` if missing. The remaining nodes keep their relative order.
- `has_edge(u, v)`, `weight(u, v)` (raises `GraphError` if there is no such edge).
- `nodes()` — list of nodes in index order.
- `edges()` — list of `(u, v, weight)` sorted by the index of `u`, then by the order in which the edges leaving `u` were first added (replacing an edge's weight keeps its place).
- `successors(n)` — list of `v` for edges `n -> v`, in the same order as `edges()`; `predecessors(n)` — list of `u` for edges `u -> n`, in index order of `u`. Both raise `NodeNotFound` for a missing node.
- `len(g)` is the number of nodes; `n in g` tests membership.

## algorithms.py

- `topological_sort(g) -> list` — Kahn's algorithm, where among all nodes that are ready at any step the one with the smallest index is taken next. Raises `CycleError` (with a valid `cycle`) if the graph has a cycle, including a self-loop.
- `has_cycle(g) -> bool`.
- `shortest_path(g, src, dst) -> (distance, path)` — Dijkstra on the edge weights. `path` is the list of nodes from `src` to `dst` inclusive. `src == dst` gives `(0, [src])`. If `dst` is unreachable, return `(math.inf, [])`. Raises `NodeNotFound` if either node is missing.
- `reachable(g, src) -> list` — every node reachable from `src` (including `src`), in index order. Raises `NodeNotFound` if missing.
- `strongly_connected_components(g) -> list[list]` — every node appears in exactly one component; nodes inside a component are in index order; components are ordered by the index of their first node. Must not hit Python's recursion limit on a 5,000-node path graph.

## io.py

- `parse_edge_list(text) -> Graph`. One item per line. Leading and trailing whitespace is ignored; blank lines and lines whose first non-space character is `#` are skipped. A line with one field `n` adds node `n`. A line with two fields `u v` adds an edge with weight 1. A line with three fields `u v w` adds an edge with weight `float(w)`. Node names are strings. A weight that is not a number, a negative weight, or a line with more than three fields raises `ValueError` whose message contains `line N` with `N` the 1-based line number.
- `to_edge_list(g) -> str`. First one line `u v w` for every edge in `edges()` order, where `w` is `format(float(weight), "g")`; then one line `n` for every node with no incoming and no outgoing edges, in index order. Lines are joined with `\n` and the result ends with a single `\n` (the empty graph gives `""`). Nodes are written with `str()`.

Round trip: for a graph whose nodes are strings without whitespace, `parse_edge_list(to_edge_list(g))` has the same `edges()` (weights as floats) and the same set of nodes.
