import heapq
import itertools
import math

from .errors import CycleError, NodeNotFound


def _find_cycle(g, candidates):
    """Return a cycle among `candidates` (nodes left after Kahn); every such node has an in-edge from the set."""
    cand = set(candidates)
    start = candidates[0]
    # walk backwards along predecessors inside cand until a node repeats
    seen, order, n = {}, [], start
    while n not in seen:
        seen[n] = len(order)
        order.append(n)
        n = next(p for p in g.predecessors(n) if p in cand)
    cyc = order[seen[n]:]
    cyc.reverse()
    return cyc + [cyc[0]]


def topological_sort(g):
    nodes = g.nodes()
    idx = {n: i for i, n in enumerate(nodes)}
    indeg = {n: 0 for n in nodes}
    for u, v, _ in g.edges():
        indeg[v] += 1
    heap = [idx[n] for n in nodes if indeg[n] == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        n = nodes[heapq.heappop(heap)]
        out.append(n)
        for v in g.successors(n):
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, idx[v])
    if len(out) != len(nodes):
        rest = [n for n in nodes if indeg[n] > 0]
        raise CycleError(_find_cycle(g, rest))
    return out


def has_cycle(g):
    try:
        topological_sort(g)
        return False
    except CycleError:
        return True


def shortest_path(g, src, dst):
    for n in (src, dst):
        if n not in g:
            raise NodeNotFound(n)
    if src == dst:
        return 0, [src]
    dist, prev = {src: 0}, {}
    tie = itertools.count()
    heap = [(0, next(tie), src)]
    done = set()
    while heap:
        d, _, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == dst:
            break
        for v in g.successors(u):
            nd = d + g.weight(u, v)
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, next(tie), v))
    if dst not in dist:
        return math.inf, []
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return dist[dst], path[::-1]


def reachable(g, src):
    if src not in g:
        raise NodeNotFound(src)
    seen, stack = {src}, [src]
    while stack:
        for v in g.successors(stack.pop()):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return [n for n in g.nodes() if n in seen]


def strongly_connected_components(g):
    nodes = g.nodes()
    idx = {n: i for i, n in enumerate(nodes)}
    index, low, on, stack, comps = {}, {}, set(), [], []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(g.successors(root)))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        while work:
            n, it = work[-1]
            advanced = False
            for v in it:
                if v not in index:
                    index[v] = low[v] = counter
                    counter += 1
                    stack.append(v)
                    on.add(v)
                    work.append((v, iter(g.successors(v))))
                    advanced = True
                    break
                if v in on:
                    low[n] = min(low[n], index[v])
            if advanced:
                continue
            work.pop()
            if work:
                p = work[-1][0]
                low[p] = min(low[p], low[n])
            if low[n] == index[n]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == n:
                        break
                comps.append(sorted(comp, key=idx.__getitem__))
    comps.sort(key=lambda c: idx[c[0]])
    return comps
