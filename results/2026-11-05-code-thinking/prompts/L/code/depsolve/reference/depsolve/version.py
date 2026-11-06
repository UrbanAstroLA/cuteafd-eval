import re
from functools import total_ordering

_NUM = r"(0|[1-9][0-9]*)"
_IDENT = re.compile(r"[0-9A-Za-z-]+")
_CORE = re.compile(rf"{_NUM}\.{_NUM}\.{_NUM}(?:-(.+))?")


def _parse_prerelease(text):
    out = []
    for ident in text.split("."):
        if not _IDENT.fullmatch(ident):
            raise ValueError(f"bad pre-release identifier {ident!r}")
        if ident.isdigit():
            if len(ident) > 1 and ident[0] == "0":
                raise ValueError(f"leading zero in {ident!r}")
            out.append(int(ident))
        else:
            out.append(ident)
    return tuple(out)


def _pre_key(pre):
    # numeric identifiers sort before alphanumeric ones
    return tuple((0, x, "") if isinstance(x, int) else (1, 0, x) for x in pre)


@total_ordering
class Version:
    __slots__ = ("_t",)

    def __init__(self, major, minor, patch, prerelease=()):
        object.__setattr__(self, "_t", (int(major), int(minor), int(patch), tuple(prerelease)))

    def __setattr__(self, k, v):
        raise AttributeError("Version is immutable")

    major = property(lambda self: self._t[0])
    minor = property(lambda self: self._t[1])
    patch = property(lambda self: self._t[2])
    prerelease = property(lambda self: self._t[3])

    @classmethod
    def parse(cls, text):
        if not isinstance(text, str):
            raise ValueError("version must be a string")
        m = _CORE.fullmatch(text)
        if not m:
            raise ValueError(f"invalid version {text!r}")
        pre = _parse_prerelease(m.group(4)) if m.group(4) is not None else ()
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)

    def _key(self):
        major, minor, patch, pre = self._t
        return (major, minor, patch, 1 if not pre else 0, _pre_key(pre))

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._t == other._t

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() < other._key()

    def __hash__(self):
        return hash(self._t)

    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + ".".join(str(x) for x in self.prerelease)
        return s

    def __repr__(self):
        return f"Version({str(self)!r})"
