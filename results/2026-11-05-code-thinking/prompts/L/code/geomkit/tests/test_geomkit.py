import math
from fractions import Fraction as F

import pytest

from geomkit import (GeometryError, Point, Polygon, Segment, WKTError, convex_hull, dumps, loads, orientation,
                     segment_intersection)


def P(x, y):
    return Point(x, y)


SQUARE = [(0, 0), (4, 0), (4, 4), (0, 4)]


# ---- points and orientation ----

def test_point_coordinates_exact():
    p = Point("1/3", F(1, 2))
    assert p.x == F(1, 3) and p.y == F(1, 2)
    assert isinstance(Point(2, 3).x, F)
    assert Point("-0.25", 0).x == F(-1, 4)
    assert Point(1, 2) == Point(F(2, 2), "2")
    assert len({Point(1, 2), Point("1", "2/1"), Point(2, 1)}) == 2


def test_point_rejects_float_and_bool():
    for bad in (0.5, True, None, [1]):
        with pytest.raises(TypeError):
            Point(bad, 0)
    with pytest.raises(Exception):
        Point(1, 2).x = 5


def test_point_ordering():
    pts = [P(1, 5), P(0, 9), P(1, -1), P(0, 0)]
    assert sorted(pts) == [P(0, 0), P(0, 9), P(1, -1), P(1, 5)]
    assert P(0, 1) < P(0, 2) <= P(0, 2) and P(3, 0) > P(2, 100) >= P(2, 100)


def test_orientation():
    assert orientation(P(0, 0), P(1, 0), P(0, 1)) == 1
    assert orientation((0, 0), (0, 1), (1, 0)) == -1
    assert orientation((0, 0), (1, 1), ("1/3", "1/3")) == 0
    assert orientation((1, 1), (1, 1), (5, 7)) == 0


# ---- segments ----

def test_segment_basics():
    s = Segment((0, 0), (3, 4))
    assert s.a == P(0, 0) and s.b == P(3, 4)
    assert s.length() == pytest.approx(5.0)
    assert s.contains(("3/2", 2)) and s.contains((0, 0)) and s.contains((3, 4))
    assert not s.contains((6, 8)) and not s.contains((1, 1))
    assert Segment((0, 0), (1, 1)) != Segment((1, 1), (0, 0))
    with pytest.raises(GeometryError):
        Segment((1, 2), ("1", "2"))
    assert issubclass(GeometryError, ValueError)


def test_intersection_crossing_exact():
    r = segment_intersection(Segment((0, 0), (1, 1)), Segment((0, 1), (3, -2)))
    assert r == P(F(1, 2), F(1, 2))
    r = segment_intersection(Segment((0, 0), (3, 1)), Segment((0, 1), (1, 0)))
    assert r == P(F(3, 4), F(1, 4))


def test_intersection_touching_and_disjoint():
    assert segment_intersection(Segment((0, 0), (2, 0)), Segment((1, 0), (1, 5))) == P(1, 0)
    assert segment_intersection(Segment((0, 0), (2, 2)), Segment((2, 2), (5, 0))) == P(2, 2)
    assert segment_intersection(Segment((0, 0), (1, 1)), Segment((2, 0), (3, -1))) is None
    assert segment_intersection(Segment((0, 0), (2, 0)), Segment((0, 1), (2, 1))) is None
    assert segment_intersection(Segment((0, 0), (1, 0)), Segment((2, 1), (2, -1))) is None


def test_intersection_collinear():
    r = segment_intersection(Segment((4, 4), (0, 0)), Segment((1, 1), (6, 6)))
    assert r == Segment((1, 1), (4, 4))
    assert segment_intersection(Segment((0, 0), (1, 1)), Segment((1, 1), (3, 3))) == P(1, 1)
    assert segment_intersection(Segment((0, 0), (1, 1)), Segment((2, 2), (3, 3))) is None
    r = segment_intersection(Segment((0, 3), (0, 0)), Segment((0, 2), (0, 1)))
    assert r == Segment((0, 1), (0, 2))
    r = segment_intersection(Segment((0, 2), (2, 0)), Segment((3, -1), (1, 1)))
    assert r == Segment((1, 1), (2, 0))


# ---- polygons ----

def test_polygon_construction_rules():
    assert Polygon(SQUARE + [(0, 0)]).vertices == tuple(P(*v) for v in SQUARE)
    assert Polygon(SQUARE) == Polygon([P(*v) for v in SQUARE])
    assert Polygon(SQUARE) != Polygon(SQUARE[1:] + SQUARE[:1])
    for bad in ([(0, 0), (1, 1)], [(0, 0), (1, 0), (1, 0), (0, 1)], [(0, 0), (1, 1), (2, 2)],
                [(0, 0), (1, 0), (0, 0)], [(0, 0), (1, 0), (0, 1), (0, 1)]):
        with pytest.raises(GeometryError):
            Polygon(bad)


def test_area_and_orientation_sign():
    ccw = Polygon([(0, 0), (3, 0), (0, 2)])
    cw = Polygon([(0, 0), (0, 2), (3, 0)])
    assert ccw.signed_area() == 3 and cw.signed_area() == -3
    assert cw.area() == 3 and isinstance(cw.area(), F)
    tri = Polygon([(0, 0), ("1/2", 0), (0, "1/3")])
    assert tri.area() == F(1, 12)


def test_perimeter_float():
    assert Polygon([(0, 0), (3, 0), (3, 4)]).perimeter() == pytest.approx(12.0)
    assert isinstance(Polygon(SQUARE).perimeter(), float)


def test_centroid_exact():
    assert Polygon([(0, 0), (1, 0), (0, 1)]).centroid() == P(F(1, 3), F(1, 3))
    L = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
    assert L.centroid() == P(F(5, 6), F(5, 6))
    assert Polygon(list(reversed(L.vertices))).centroid() == P(F(5, 6), F(5, 6))
    # collinear vertex on an edge does not change the result
    assert Polygon([(0, 0), (2, 0), (4, 0), (4, 4), (0, 4)]).centroid() == P(2, 2)


def test_locate():
    L = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
    assert L.locate(("1/2", "1/2")) == "inside"
    assert L.locate(("3/2", "3/2")) == "outside"
    assert L.locate((1, "3/2")) == "boundary"
    assert L.locate((2, 0)) == "boundary"
    assert L.locate((1, 1)) == "boundary"
    assert L.locate((3, 1)) == "outside"
    # ray from these points passes exactly through vertices
    assert L.locate(("1/2", 1)) == "inside"
    assert L.locate((-1, 1)) == "outside"
    assert L.locate((-1, 0)) == "outside"
    assert L.locate(("1/2", 2)) == "boundary"


def test_contains_include_boundary():
    sq = Polygon(SQUARE)
    assert sq.contains((4, 2)) and not sq.contains((4, 2), include_boundary=False)
    assert sq.contains((2, 2), include_boundary=False)
    assert not sq.contains((5, 2))


def test_is_convex():
    assert Polygon(SQUARE).is_convex()
    assert Polygon(list(reversed(SQUARE))).is_convex()
    assert Polygon([(0, 0), (2, 0), (4, 0), (4, 4), (0, 4)]).is_convex()
    assert not Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]).is_convex()


# ---- convex hull ----

def test_hull_basic_order():
    pts = [(2, 2), (0, 0), (4, 0), (4, 4), (0, 4), (1, 3), (3, 1), (0, 0)]
    assert convex_hull(pts) == [P(0, 0), P(4, 0), P(4, 4), P(0, 4)]


def test_hull_collinear_points():
    pts = [(0, 0), (2, 0), (4, 0), (4, 2), (4, 4), (2, 4), (0, 4), (0, 2), (2, 2), (1, 1)]
    assert convex_hull(pts) == [P(0, 0), P(4, 0), P(4, 4), P(0, 4)]
    assert convex_hull(pts, keep_collinear=True) == [P(0, 0), P(2, 0), P(4, 0), P(4, 2), P(4, 4), P(2, 4),
                                                     P(0, 4), P(0, 2)]
    tri = [(0, 0), (6, 0), (0, 6), (3, 3), (1, 5), (2, 0), (1, 1)]
    assert convex_hull(tri) == [P(0, 0), P(6, 0), P(0, 6)]
    assert convex_hull(tri, keep_collinear=True) == [P(0, 0), P(2, 0), P(6, 0), P(3, 3), P(1, 5), P(0, 6)]


def test_hull_degenerate():
    assert convex_hull([]) == []
    assert convex_hull([(1, 1), (1, 1)]) == [P(1, 1)]
    line = [(3, 3), (1, 1), (2, 2), (0, 0), (2, 2)]
    assert convex_hull(line) == [P(0, 0), P(3, 3)]
    assert convex_hull(line, keep_collinear=True) == [P(0, 0), P(1, 1), P(2, 2), P(3, 3)]
    vertical = [(0, 5), (0, 1), (0, 3)]
    assert convex_hull(vertical) == [P(0, 1), P(0, 5)]


def test_hull_exact_rationals():
    # (1/2, 1/4) lies exactly on the edge from (1/3, 0) to (2/3, 1/2); (2/3, 1/5) is interior
    pts = [("1/3", 0), (1, 0), ("2/3", "1/2"), ("1/2", "1/4"), (F(2, 3), F(1, 5))]
    assert convex_hull(pts) == [P(F(1, 3), 0), P(1, 0), P(F(2, 3), F(1, 2))]
    assert convex_hull(pts, keep_collinear=True) == [P(F(1, 3), 0), P(1, 0), P(F(2, 3), F(1, 2)),
                                                     P(F(1, 2), F(1, 4))]


# ---- WKT ----

def test_loads_shapes_and_numbers():
    assert loads("POINT (1 -1/2)") == P(1, F(-1, 2))
    assert loads("  point(0.25   3/6)  ") == P(F(1, 4), F(1, 2))
    assert loads("LineString ( 0 0 ,3 4 )") == Segment((0, 0), (3, 4))
    poly = loads("POLYGON((0 0, 4 0, 0 3, 0 0))")
    assert poly == Polygon([(0, 0), (4, 0), (0, 3)])


def test_dumps_canonical():
    assert dumps(P(1, F(-1, 2))) == "POINT (1 -1/2)"
    assert dumps(Point("0.5", "-6/4")) == "POINT (1/2 -3/2)"
    assert dumps(Segment((0, 0), (3, 4))) == "LINESTRING (0 0, 3 4)"
    assert dumps(Polygon([(0, 0), (4, 0), (0, 3), (0, 0)])) == "POLYGON ((0 0, 4 0, 0 3, 0 0))"
    with pytest.raises(TypeError):
        dumps((1, 2))


def test_wkt_round_trip():
    shapes = [P(F(-7, 3), 0), Segment((F(1, 3), 2), (-5, F(9, 7))),
              Polygon([(0, 0), (F(5, 2), 0), (3, 3), (F(-1, 3), 2)])]
    for g in shapes:
        assert loads(dumps(g)) == g


def test_loads_errors():
    bad = ["POINT (1)", "POINT (1 2 3)", "POINT (1 2", "POINT 1 2", "POINT (1 2) x", "POINT (1/0 2)",
           "POINT (.5 1)", "POINT (1e3 1)", "POINT (+1 2)", "CIRCLE (1 2)", "LINESTRING (0 0)",
           "LINESTRING (0 0, 1 1, 2 2)", "POLYGON ((0 0, 1 0, 0 1))", "POLYGON ((0 0, 1 0, 0 1, 1 1))",
           "POLYGON ((0 0, 4 0, 0 3, 0 0), (1 1, 2 1, 1 2, 1 1))", "POINT (1,2)", "POINT (1-2)", ""]
    for text in bad:
        with pytest.raises(WKTError):
            loads(text)


def test_loads_geometry_errors_propagate():
    for text in ("LINESTRING (1 1, 1 1)", "POLYGON ((0 0, 1 1, 2 2, 0 0))"):
        with pytest.raises(GeometryError) as ei:
            loads(text)
        assert not isinstance(ei.value, WKTError)
