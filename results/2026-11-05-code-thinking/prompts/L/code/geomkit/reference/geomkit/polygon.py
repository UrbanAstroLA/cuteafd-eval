from fractions import Fraction

from .errors import GeometryError
from .primitives import Point, Segment, _cross, _on_segment, as_point


class Polygon:
    __slots__ = ("vertices",)

    def __init__(self, vertices):
        vs = [as_point(p) for p in vertices]
        if len(vs) >= 2 and vs[-1] == vs[0]:
            vs.pop()
        if len(vs) < 3:
            raise GeometryError("a polygon needs at least 3 vertices")
        for i in range(len(vs)):
            if vs[i] == vs[(i + 1) % len(vs)]:
                raise GeometryError("repeated consecutive vertex")
        object.__setattr__(self, "vertices", tuple(vs))
        if self.signed_area() == 0:
            raise GeometryError("polygon has zero area")

    def __setattr__(self, k, v):
        raise AttributeError("Polygon is immutable")

    def __eq__(self, o):
        return isinstance(o, Polygon) and self.vertices == o.vertices

    def __hash__(self):
        return hash(self.vertices)

    def __repr__(self):
        return f"Polygon({list(self.vertices)!r})"

    def _edges(self):
        vs = self.vertices
        return [(vs[i], vs[(i + 1) % len(vs)]) for i in range(len(vs))]

    def signed_area(self):
        return sum((a.x * b.y - b.x * a.y for a, b in self._edges()), Fraction(0)) / 2

    def area(self):
        return abs(self.signed_area())

    def perimeter(self):
        return sum(Segment(a, b).length() for a, b in self._edges())

    def centroid(self):
        a6 = 6 * self.signed_area()
        cx = cy = Fraction(0)
        for a, b in self._edges():
            f = a.x * b.y - b.x * a.y
            cx += (a.x + b.x) * f
            cy += (a.y + b.y) * f
        return Point(cx / a6, cy / a6)

    def locate(self, p):
        p = as_point(p)
        inside = False
        for a, b in self._edges():
            if _on_segment(a, b, p):
                return "boundary"
            if (a.y > p.y) != (b.y > p.y):
                x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)
                if p.x < x:
                    inside = not inside
        return "inside" if inside else "outside"

    def contains(self, p, include_boundary=True):
        where = self.locate(p)
        return where == "inside" or (include_boundary and where == "boundary")

    def is_convex(self):
        vs, n = self.vertices, len(self.vertices)
        signs = set()
        for i in range(n):
            c = _cross(vs[i], vs[(i + 1) % n], vs[(i + 2) % n])
            if c:
                signs.add(c > 0)
        return len(signs) == 1
