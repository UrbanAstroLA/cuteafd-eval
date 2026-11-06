import math
from fractions import Fraction

from .errors import GeometryError


def _coord(v):
    if isinstance(v, bool) or isinstance(v, float):
        raise TypeError(f"unsupported coordinate {v!r}")
    if isinstance(v, (int, Fraction)):
        return Fraction(v)
    if isinstance(v, str):
        return Fraction(v)
    raise TypeError(f"unsupported coordinate {v!r}")


class Point:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        object.__setattr__(self, "x", _coord(x))
        object.__setattr__(self, "y", _coord(y))

    def __setattr__(self, k, v):
        raise AttributeError("Point is immutable")

    def _t(self):
        return (self.x, self.y)

    def __eq__(self, o):
        return isinstance(o, Point) and self._t() == o._t()

    def __hash__(self):
        return hash(self._t())

    def __lt__(self, o):
        if not isinstance(o, Point):
            return NotImplemented
        return self._t() < o._t()

    def __le__(self, o):
        if not isinstance(o, Point):
            return NotImplemented
        return self._t() <= o._t()

    def __gt__(self, o):
        if not isinstance(o, Point):
            return NotImplemented
        return self._t() > o._t()

    def __ge__(self, o):
        if not isinstance(o, Point):
            return NotImplemented
        return self._t() >= o._t()

    def __repr__(self):
        return f"Point({str(self.x)!r}, {str(self.y)!r})"


def as_point(p):
    if isinstance(p, Point):
        return p
    if isinstance(p, tuple) and len(p) == 2:
        return Point(*p)
    raise TypeError(f"not a point: {p!r}")


def _cross(a, b, c):
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def orientation(a, b, c):
    v = _cross(as_point(a), as_point(b), as_point(c))
    return (v > 0) - (v < 0)


class Segment:
    __slots__ = ("a", "b")

    def __init__(self, a, b):
        a, b = as_point(a), as_point(b)
        if a == b:
            raise GeometryError("degenerate segment")
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "b", b)

    def __setattr__(self, k, v):
        raise AttributeError("Segment is immutable")

    def __eq__(self, o):
        return isinstance(o, Segment) and self.a == o.a and self.b == o.b

    def __hash__(self):
        return hash((self.a, self.b))

    def __repr__(self):
        return f"Segment({self.a!r}, {self.b!r})"

    def length(self):
        return math.hypot(float(self.b.x - self.a.x), float(self.b.y - self.a.y))

    def contains(self, p):
        p = as_point(p)
        return _on_segment(self.a, self.b, p)


def _on_segment(a, b, p):
    return (_cross(a, b, p) == 0 and min(a.x, b.x) <= p.x <= max(a.x, b.x)
            and min(a.y, b.y) <= p.y <= max(a.y, b.y))


def segment_intersection(s, t):
    p1, p2, q1, q2 = s.a, s.b, t.a, t.b
    d1, d2 = _cross(q1, q2, p1), _cross(q1, q2, p2)
    d3, d4 = _cross(p1, p2, q1), _cross(p1, p2, q2)
    if d1 == 0 and d2 == 0:  # collinear (s lies on t's line)
        lo = max(min(p1, p2), min(q1, q2))
        hi = min(max(p1, p2), max(q1, q2))
        if lo > hi:
            return None
        if lo == hi:
            return lo
        return Segment(lo, hi)
    if ((d1 > 0 and d2 > 0) or (d1 < 0 and d2 < 0) or (d3 > 0 and d4 > 0) or (d3 < 0 and d4 < 0)):
        return None
    # lines cross at a single point lying on both segments
    rx, ry = p2.x - p1.x, p2.y - p1.y
    sx, sy = q2.x - q1.x, q2.y - q1.y
    den = rx * sy - ry * sx
    t_ = ((q1.x - p1.x) * sy - (q1.y - p1.y) * sx) / den
    return Point(p1.x + t_ * rx, p1.y + t_ * ry)
