from .primitives import _cross, as_point


def convex_hull(points, keep_collinear=False):
    pts = sorted(set(as_point(p) for p in points))
    if len(pts) <= 1:
        return pts
    if all(_cross(pts[0], pts[-1], p) == 0 for p in pts):
        return pts if keep_collinear else [pts[0], pts[-1]]

    def bad(c):
        return c < 0 if keep_collinear else c <= 0

    def chain(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and bad(_cross(out[-2], out[-1], p)):
                out.pop()
            out.append(p)
        return out

    lower, upper = chain(pts), chain(reversed(pts))
    return lower[:-1] + upper[:-1]
