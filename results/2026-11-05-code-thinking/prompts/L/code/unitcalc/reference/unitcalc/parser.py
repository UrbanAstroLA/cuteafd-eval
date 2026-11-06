import re

from .errors import ParseError
from .units import Unit

_TOKEN = re.compile(r"\s*(?:(?P<name>[A-Za-z]+)|(?P<int>-?[0-9]+)|(?P<op>[*/^()]))")
_NUMBER = re.compile(r"\s*[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")
ONE = Unit(1, (0,) * 7)


def _tokenize(text):
    toks, i = [], 0
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        m = _TOKEN.match(text, i)
        if not m:
            raise ParseError(f"unexpected character {text[i]!r}", i)
        kind = m.lastgroup
        toks.append((kind, m.group(kind), m.start(kind)))
        i = m.end()
    toks.append(("end", None, len(text)))
    return toks


class _P:
    def __init__(self, text):
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expr(self):
        u = self.term()
        while self.peek()[0] == "op" and self.peek()[1] in "*/":
            op = self.take()[1]
            rhs = self.term()
            u = u * rhs if op == "*" else u / rhs
        return u

    def term(self):
        u = self.factor()
        if self.peek()[0] == "op" and self.peek()[1] == "^":
            self.take()
            kind, val, pos = self.take()
            if kind != "int":
                raise ParseError("expected integer exponent", pos)
            u = u ** int(val)
        return u

    def factor(self):
        kind, val, pos = self.take()
        if kind == "name":
            return Unit.atom(val)
        if kind == "int" and val == "1":
            return ONE
        if kind == "op" and val == "(":
            u = self.expr()
            kind, val, pos = self.take()
            if not (kind == "op" and val == ")"):
                raise ParseError("expected ')'", pos)
            return u
        raise ParseError("unexpected token" if kind != "end" else "unexpected end of input", pos)


def parse_unit(text):
    if text.strip() == "":
        return ONE
    p = _P(text)
    u = p.expr()
    kind, val, pos = p.peek()
    if kind != "end":
        raise ParseError("unexpected token", pos)
    return u


def parse_quantity(text):
    from .quantity import Quantity
    m = _NUMBER.match(text)
    if not m:
        raise ParseError("expected a number", len(text) - len(text.lstrip()))
    num = m.group(0).strip()
    value = float(num) if any(c in num for c in ".eE") else int(num)
    rest = text[m.end():]
    offset = m.end()
    try:
        unit = parse_unit(rest)
    except ParseError as e:
        raise ParseError("bad unit", e.pos + offset) from None
    return Quantity(value, unit)
