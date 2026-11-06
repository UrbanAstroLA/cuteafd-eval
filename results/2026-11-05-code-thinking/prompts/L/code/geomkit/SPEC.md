Build a Python package named `geomkit`: exact 2D computational geometry on rational coordinates, with a WKT-like text format. Python 3.12, standard library only.

## Files

- `geomkit/__init__.py` — re-exports `Point`, `Segment`, `Polygon`, `orientation`, `segment_intersection`, `convex_hull`, `loads`, `dumps`, `GeometryError`, `WKTError`.
- `geomkit/errors.py` — `GeometryError(ValueError)` and `WKTError(GeometryError)`.
- `geomkit/primitives.py` — `Point`, `Segment`, `orientation`, `segment_intersection`.
- `geomkit/polygon.py` — `Polygon`.
- `geomkit/hull.py` — `convex_hull`.
- `geomkit/wkt.py` — `loads` and `dumps`.

All arithmetic is exact with `fractions.Fraction`; no floats except where stated.

## primitives.py

- `Point(x, y)` — immutable and hashable, attributes `x`, `y` stored as `Fraction`. Each coordinate may be an `int`, a `Fraction`, or a `str` accepted by `Fraction(str)` (e.g. `"1/3"`, `"-0.25"`); a `float`, a `bool` or any other type raises `TypeError`. Points compare equal by coordinates and order lexicographically by `(x, y)` (`<`, `<=`, `>`, `>=`).
- Wherever a point is taken as an argument below (constructors included), an `(x, y)` tuple is also accepted and converted with `Point(x, y)`.
- `orientation(a, b, c) -> int` — the sign of the cross product `(b - a) × (c - a)`: `1` if `a, b, c` turn counter-clockwise, `-1` if clockwise, `0` if collinear (including coincident points).
- `Segment(a, b)` — immutable and hashable, attributes `a`, `b` (`Point`s, kept in the given order). `a == b` raises `GeometryError`. Two segments are equal only if both endpoints are equal in the same order.
  - `length() -> float` — `math.hypot` of the float differences.
  - `contains(p) -> bool` — `p` lies on the closed segment.
- `segment_intersection(s, t)` — the intersection of two closed segments: `None` if they do not meet; a `Point` if they meet in exactly one point (crossing, touching, or collinear segments sharing only an endpoint); a `Segment` if they overlap along a positive length, whose `a` is the lexicographically smaller endpoint of the overlap.

## polygon.py

`Polygon(vertices)` — `vertices` is an iterable of points. If there are at least two and the last equals the first, the last is dropped. Then raise `GeometryError` if there are fewer than 3 vertices, two cyclically consecutive vertices are equal, or the signed area is 0. Self-intersection is not checked; behaviour below assumes a simple polygon.

- `vertices` — tuple of `Point`, in the given order. Two polygons are equal iff their `vertices` are equal. Polygons are hashable.
- `signed_area() -> Fraction` — shoelace formula, positive for counter-clockwise order. `area()` — its absolute value.
- `perimeter() -> float` — sum of the edge lengths (`Segment.length`).
- `centroid() -> Point` — exact centroid of the enclosed region: `cx = Σ (xᵢ + xᵢ₊₁)(xᵢyᵢ₊₁ − xᵢ₊₁yᵢ) / (6A)`, likewise `cy` with `y`, where `A` is the signed area and indices wrap around.
- `locate(p) -> str` — `"boundary"` if `p` lies on any edge (vertices included), otherwise `"inside"` or `"outside"`.
- `contains(p, include_boundary=True) -> bool` — based on `locate`.
- `is_convex() -> bool` — true iff all non-zero `orientation`s of cyclically consecutive vertex triples have the same sign (collinear runs are allowed).

## hull.py

`convex_hull(points, keep_collinear=False) -> list[Point]` — duplicates are ignored.

- No points: `[]`. One distinct point: `[p]`.
- All distinct points collinear: with `keep_collinear` false, the two extreme points `[min, max]` (lexicographic); with it true, every distinct point in ascending lexicographic order.
- Otherwise the hull vertices in counter-clockwise order, starting at the lexicographically smallest point. With `keep_collinear` false, points lying on a hull edge between two vertices are excluded; with it true, they are included, in order along the edge.

## wkt.py

Grammar (keywords case-insensitive; any whitespace, including none, may surround `(`, `)` and `,`; at least one whitespace between the two numbers of a coordinate pair and none needed after a keyword):

- `POINT (x y)` → `Point`
- `LINESTRING (x1 y1, x2 y2)` → `Segment` — exactly two pairs.
- `POLYGON ((x1 y1, x2 y2, ..., x1 y1))` → `Polygon` — one ring, at least 4 pairs, last pair equal to the first.

A number matches `-?[0-9]+(\.[0-9]+|/[0-9]+)?` and is converted exactly (`"0.25"` → `1/4`, `"3/6"` → `1/2`); a zero denominator is a syntax error.

- `loads(text)` — leading and trailing whitespace is ignored. An unknown keyword, any syntax error, a wrong pair count, an unclosed ring or trailing text raises `WKTError`; a `GeometryError` raised while building the shape (e.g. a degenerate segment or polygon) propagates as is.
- `dumps(geom)` — canonical text: uppercase keyword, one space, then the coordinates; pairs as `x y` separated by `", "`; a polygon ring lists its vertices in order and repeats the first at the end. A number is written as an integer if its denominator is 1, otherwise as `n/d` in lowest terms with the sign on `n`. Examples: `POINT (1 -1/2)`, `LINESTRING (0 0, 3 4)`, `POLYGON ((0 0, 4 0, 0 3, 0 0))`. Any other argument type raises `TypeError`.
- `loads(dumps(g)) == g` for every `Point`, `Segment` and `Polygon`.
