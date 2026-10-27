from .graph import Graph


def parse_edge_list(text):
    g = Graph()
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if len(f) == 1:
            g.add_node(f[0])
        elif len(f) == 2:
            g.add_edge(f[0], f[1], 1.0)
        elif len(f) == 3:
            try:
                w = float(f[2])
            except ValueError:
                raise ValueError(f"line {i}: bad weight {f[2]!r}") from None
            if w < 0:
                raise ValueError(f"line {i}: negative weight")
            g.add_edge(f[0], f[1], w)
        else:
            raise ValueError(f"line {i}: too many fields")
    return g


def to_edge_list(g):
    lines = [f"{u} {v} {format(float(w), 'g')}" for u, v, w in g.edges()]
    touched = set()
    for u, v, _ in g.edges():
        touched.add(u)
        touched.add(v)
    lines += [str(n) for n in g.nodes() if n not in touched]
    return "".join(line + "\n" for line in lines)
