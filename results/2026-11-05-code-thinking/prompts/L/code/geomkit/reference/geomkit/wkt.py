import re
from fractions import Fraction

from .errors import WKTError
from .polygon import Polygon
from .primitives import Point, Segment

_NUM = r"-?[0-9]+(?:\.[0-9]+|/[0-9]+)?"
_PAIR = re.compile(rf"\s*({_NUM})\s+({_NUM})\s*")
_KEYWORD = re.compile(r"[A-Za-z]+")


def _number(text):
    if "/" in text:
        n, d = text.split("/")
        if int(d) == 0:
            raise WKTError(f"zero denominator in {text!r}")
        return Fraction(int(n), int(d))
    return Fraction(text)


def _parens(body):
    body = body.strip()
    if not (body.startswith("(") and body.endswith(")")):
        raise WKTError("expected parenthesised list")
    return body[1:-1]


def _pairs(inner):
    out = []
    for part in inner.split(","):
        m = _PAIR.fullmatch(part)
        if not m:
            raise WKTError(f"bad coordinate pair {part!r}")
        out.append(Point(_number(m.group(1)), _number(m.group(2))))
    return out


def loads(text):
    text = text.strip()
    m = _KEYWORD.match(text)
    if not m:
        raise WKTError("missing keyword")
    kw, body = m.group(0).upper(), text[m.end():]
    if kw == "POINT":
        pts = _pairs(_parens(body))
        if len(pts) != 1:
            raise WKTError("POINT takes one coordinate pair")
        return pts[0]
    if kw == "LINESTRING":
        pts = _pairs(_parens(body))
        if len(pts) != 2:
            raise WKTError("LINESTRING takes exactly two coordinate pairs")
        return Segment(pts[0], pts[1])
    if kw == "POLYGON":
        pts = _pairs(_parens(_parens(body)))
        if len(pts) < 4:
            raise WKTError("a ring needs at least 4 coordinate pairs")
        if pts[0] != pts[-1]:
            raise WKTError("ring is not closed")
        return Polygon(pts)
    raise WKTError(f"unknown keyword {m.group(0)!r}")


def _fmt(q):
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def _fmt_pairs(points):
    return ", ".join(f"{_fmt(p.x)} {_fmt(p.y)}" for p in points)


def dumps(geom):
    if isinstance(geom, Point):
        return f"POINT ({_fmt_pairs([geom])})"
    if isinstance(geom, Segment):
        return f"LINESTRING ({_fmt_pairs([geom.a, geom.b])})"
    if isinstance(geom, Polygon):
        vs = list(geom.vertices)
        return f"POLYGON (({_fmt_pairs(vs + [vs[0]])}))"
    raise TypeError(f"cannot serialise {type(geom).__name__}")
