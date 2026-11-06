import re

from .version import Version, _NUM

_PARTIAL = re.compile(rf"{_NUM}(?:\.{_NUM})?")
_OPS = (">=", "<=", "==", "!=", ">", "<", "^", "~")


def _as_version(v):
    return v if isinstance(v, Version) else Version.parse(v)


def _parse_comparator(text):
    """Return (op, lower Version, upper Version | None, text). For ^ and ~, op is '^'/'~' with an upper bound."""
    if text == "*":
        return ("*", None, None)
    for op in _OPS:
        if text.startswith(op):
            break
    else:
        raise ValueError(f"bad comparator {text!r}")
    vtext = text[len(op):]
    if not vtext:
        raise ValueError(f"missing version in {text!r}")
    m = _PARTIAL.fullmatch(vtext)
    if m and op not in ("==", "!="):
        parts = [int(m.group(1))] + ([int(m.group(2))] if m.group(2) is not None else [])
        v = Version(*(parts + [0] * (3 - len(parts))))
    else:
        v = Version.parse(vtext)
        parts = [v.major, v.minor, v.patch]
    upper = None
    if op == "^":
        nz = next((i for i, p in enumerate(parts) if p != 0), len(parts) - 1)
        bump = parts[:nz] + [parts[nz] + 1]
        upper = Version(*(bump + [0] * (3 - len(bump))))
    elif op == "~":
        if len(parts) >= 2:
            upper = Version(parts[0], parts[1] + 1, 0)
        else:
            upper = Version(parts[0] + 1, 0, 0)
    return (op, v, upper)


class Constraint:
    def __init__(self, comparators, text):
        self._comparators = comparators
        self._text = text

    @classmethod
    def parse(cls, text):
        if not isinstance(text, str):
            raise ValueError("constraint must be a string")
        pieces = ["".join(p.split()) for p in text.split(",")]
        if any(not p for p in pieces):
            raise ValueError(f"empty comparator in {text!r}")
        return cls([_parse_comparator(p) for p in pieces], ",".join(pieces))

    def _holds(self, op, v, upper, x):
        if op == "*":
            return True
        if op == ">=":
            return x >= v
        if op == ">":
            return x > v
        if op == "<=":
            return x <= v
        if op == "<":
            return x < v
        if op == "==":
            return x == v
        if op == "!=":
            return x != v
        return v <= x < upper  # ^ and ~

    def allows(self, version):
        x = _as_version(version)
        if not all(self._holds(op, v, up, x) for op, v, up in self._comparators):
            return False
        if x.prerelease:
            return any(v is not None and v.prerelease and (v.major, v.minor, v.patch) == (x.major, x.minor, x.patch)
                       for _, v, _ in self._comparators)
        return True

    def __str__(self):
        return self._text

    def __repr__(self):
        return f"Constraint({self._text!r})"
