from fractions import Fraction

from .errors import UnknownUnitError

BASE = ("kg", "m", "s", "A", "K", "mol", "cd")

PREFIXES = {
    "T": Fraction(10) ** 12, "G": Fraction(10) ** 9, "M": Fraction(10) ** 6, "k": Fraction(10) ** 3,
    "h": Fraction(10) ** 2, "da": Fraction(10), "d": Fraction(1, 10), "c": Fraction(1, 100),
    "m": Fraction(1, 1000), "u": Fraction(1, 10 ** 6), "n": Fraction(1, 10 ** 9), "p": Fraction(1, 10 ** 12),
}


def _d(kg=0, m=0, s=0, A=0, K=0, mol=0, cd=0):
    return (kg, m, s, A, K, mol, cd)


# symbol: (factor, dims, prefixable)
UNITS = {
    "m": (Fraction(1), _d(m=1), True),
    "g": (Fraction(1, 1000), _d(kg=1), True),
    "s": (Fraction(1), _d(s=1), True),
    "A": (Fraction(1), _d(A=1), True),
    "K": (Fraction(1), _d(K=1), True),
    "mol": (Fraction(1), _d(mol=1), True),
    "cd": (Fraction(1), _d(cd=1), True),
    "N": (Fraction(1), _d(kg=1, m=1, s=-2), True),
    "J": (Fraction(1), _d(kg=1, m=2, s=-2), True),
    "W": (Fraction(1), _d(kg=1, m=2, s=-3), True),
    "Pa": (Fraction(1), _d(kg=1, m=-1, s=-2), True),
    "Hz": (Fraction(1), _d(s=-1), True),
    "C": (Fraction(1), _d(s=1, A=1), True),
    "V": (Fraction(1), _d(kg=1, m=2, s=-3, A=-1), True),
    "L": (Fraction(1, 1000), _d(m=3), True),
    "min": (Fraction(60), _d(s=1), False),
    "h": (Fraction(3600), _d(s=1), False),
}

DERIVED = ("N", "J", "W", "Pa", "Hz", "C", "V")


def _fmt_term(sym, e):
    return sym if e == 1 else f"{sym}^{e}"


class Unit:
    """A unit: exact SI factor, dimension exponents in BASE order, and ordered (symbol, exponent) terms."""

    def __init__(self, factor, dims, terms=()):
        self.factor = Fraction(factor)
        self.dims = tuple(dims)
        self.terms = tuple(terms)

    @classmethod
    def atom(cls, text):
        if text in UNITS:
            f, dims, _ = UNITS[text]
            return cls(f, dims, ((text, 1),))
        for p in sorted(PREFIXES, key=len, reverse=True):
            if text.startswith(p) and len(text) > len(p):
                rest = text[len(p):]
                if rest in UNITS and UNITS[rest][2]:
                    f, dims, _ = UNITS[rest]
                    return cls(PREFIXES[p] * f, dims, ((text, 1),))
        raise UnknownUnitError(text)

    @property
    def symbol(self):
        num = [_fmt_term(s, e) for s, e in self.terms if e > 0]
        den = [_fmt_term(s, -e) for s, e in self.terms if e < 0]
        if not den:
            return "*".join(num)
        top = "*".join(num) if num else "1"
        if len(den) == 1:
            return f"{top}/{den[0]}"
        return f"{top}/({'*'.join(den)})"

    @property
    def dimensionless(self):
        return all(e == 0 for e in self.dims)

    def __mul__(self, other):
        if not isinstance(other, Unit):
            return NotImplemented
        terms = dict(self.terms)
        for s, e in other.terms:
            terms[s] = terms.get(s, 0) + e
        return Unit(self.factor * other.factor, tuple(a + b for a, b in zip(self.dims, other.dims)),
                    tuple((s, e) for s, e in terms.items() if e != 0))

    def __pow__(self, n):
        if isinstance(n, bool) or not isinstance(n, int):
            raise TypeError("unit exponent must be an int")
        return Unit(self.factor ** n, tuple(d * n for d in self.dims),
                    tuple((s, e * n) for s, e in self.terms if e * n != 0))

    def __truediv__(self, other):
        if not isinstance(other, Unit):
            return NotImplemented
        return self * other ** -1

    def __eq__(self, other):
        if not isinstance(other, Unit):
            return NotImplemented
        return self.factor == other.factor and self.dims == other.dims

    def __hash__(self):
        return hash((self.factor, self.dims))

    def __repr__(self):
        return f"Unit({self.symbol!r})"


def base_unit(dims):
    u = Unit(1, (0,) * 7)
    for sym, e in zip(BASE, dims):
        if e:
            u = u * Unit(1, (0,) * 7, ((sym, e),))
    return Unit(1, dims, u.terms)
