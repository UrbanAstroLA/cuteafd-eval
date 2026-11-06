"""Continuation-passing backtracking matcher. Captures are an immutable tuple of spans (or None)."""


def _seq(items, idx, s, i, caps, k):
    if idx == len(items):
        return k(i, caps)
    return _m(items[idx], s, i, caps, lambda j, c: _seq(items, idx + 1, s, j, c, k))


def _m(node, s, i, caps, k):
    t = node[0]
    if t == "char":
        if i < len(s) and node[1](s[i]):
            return k(i + 1, caps)
        return None
    if t == "bol":
        return k(i, caps) if i == 0 else None
    if t == "eol":
        return k(i, caps) if i == len(s) else None
    if t == "seq":
        return _seq(node[1], 0, s, i, caps, k)
    if t == "alt":
        for branch in node[1]:
            r = _m(branch, s, i, caps, k)
            if r is not None:
                return r
        return None
    if t == "group":
        idx, inner = node[1], node[2]
        if idx is None:
            return _m(inner, s, i, caps, k)

        def close(j, c):
            return k(j, c[:idx] + ((i, j),) + c[idx + 1:])

        return _m(inner, s, i, caps, close)
    if t == "rep":
        _, sub, lo, hi, greedy = node

        def loop(count, j, c):
            def more():
                if hi is not None and count >= hi:
                    return None

                def nxt(j2, c2):
                    if j2 == j and count >= lo:
                        return None
                    return loop(count + 1, j2, c2)

                return _m(sub, s, j, c, nxt)

            if count < lo:
                return more()
            if greedy:
                r = more()
                return r if r is not None else k(j, c)
            r = k(j, c)
            return r if r is not None else more()

        return loop(0, i, caps)
    raise AssertionError(node)


def match_at(tree, ngroups, s, i, require_end=False):
    """Return a tuple of spans (index 0 is the whole match) or None."""
    caps = (None,) * (ngroups + 1)
    n = len(s)

    def done(j, c):
        if require_end and j != n:
            return None
        return ((i, j),) + c[1:]

    return _m(tree, s, i, caps, done)
