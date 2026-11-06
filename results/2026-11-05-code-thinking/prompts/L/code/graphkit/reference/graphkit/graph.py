from .errors import GraphError, NodeNotFound


class Graph:
    def __init__(self):
        self._succ = {}  # node -> dict(v -> weight), insertion ordered
        self._pred = {}  # node -> set(u)

    def _index(self):
        return {n: i for i, n in enumerate(self._succ)}

    def _need(self, n):
        if n not in self._succ:
            raise NodeNotFound(n)

    def add_node(self, n):
        if n not in self._succ:
            self._succ[n] = {}
            self._pred[n] = set()

    def add_edge(self, u, v, weight=1.0):
        if weight < 0:
            raise ValueError("negative weight")
        self.add_node(u)
        self.add_node(v)
        self._succ[u][v] = weight
        self._pred[v].add(u)

    def remove_edge(self, u, v):
        if u not in self._succ or v not in self._succ[u]:
            raise GraphError(f"no edge {u!r} -> {v!r}")
        del self._succ[u][v]
        self._pred[v].discard(u)

    def remove_node(self, n):
        self._need(n)
        for v in self._succ[n]:
            self._pred[v].discard(n)
        for u in self._pred[n]:
            self._succ[u].pop(n, None)
        del self._succ[n]
        del self._pred[n]

    def has_edge(self, u, v):
        return u in self._succ and v in self._succ[u]

    def weight(self, u, v):
        if not self.has_edge(u, v):
            raise GraphError(f"no edge {u!r} -> {v!r}")
        return self._succ[u][v]

    def nodes(self):
        return list(self._succ)

    def edges(self):
        return [(u, v, w) for u, d in self._succ.items() for v, w in d.items()]

    def successors(self, n):
        self._need(n)
        return list(self._succ[n])

    def predecessors(self, n):
        self._need(n)
        idx = self._index()
        return sorted(self._pred[n], key=idx.__getitem__)

    def __len__(self):
        return len(self._succ)

    def __contains__(self, n):
        return n in self._succ
