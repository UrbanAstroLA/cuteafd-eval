import re
from dataclasses import dataclass

from .errors import LexError


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    pos: int


_NUM = re.compile(r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPS2 = ("==", "!=", "<=", ">=", "&&", "||")
_OPS1 = set("+-*/%^(),=<>!;")


def tokenize(src):
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        m = _NUM.match(src, i)
        if m:
            text = m.group(0)
            value = float(text) if (m.group(1) or m.group(2)) else int(text)
            out.append(Token("NUM", value, i))
            i = m.end()
            continue
        m = _NAME.match(src, i)
        if m:
            out.append(Token("NAME", m.group(0), i))
            i = m.end()
            continue
        if src[i:i + 2] in _OPS2:
            out.append(Token("OP", src[i:i + 2], i))
            i += 2
            continue
        if c in _OPS1:
            out.append(Token("OP", c, i))
            i += 1
            continue
        raise LexError(f"unexpected character {c!r}", i)
    out.append(Token("EOF", None, n))
    return out
