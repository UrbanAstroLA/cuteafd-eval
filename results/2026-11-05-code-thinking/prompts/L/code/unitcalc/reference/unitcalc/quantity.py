import math
from fractions import Fraction

from .errors import DimensionError
from .units import DERIVED, Unit, base_unit


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _as_unit(u):
    if isinstance(u, Unit):
        return u
    if isinstance(u, str):
        from .parser import parse_unit
        return parse_unit(u)
    raise TypeError("unit must be a str or Unit")


_ONE = Unit(1, (0,) * 7)


class Quantity:
    __hash__ = None

    def __init__(self, value, unit=""):
        if not _is_number(value):
            raise TypeError("value must be an int or float")
        self.value = value
        self.unit = _as_unit(unit)

    # ---- conversion ----
    def _si(self):
        return Fraction(self.value) * self.unit.factor

    def to(self, unit):
        target = _as_unit(unit)
        if target.dims != self.unit.dims:
            raise DimensionError(f"cannot convert {self.unit.symbol!r} to {target.symbol!r}")
        return Quantity(float(Fraction(self.value) * self.unit.factor / target.factor), target)

    def to_base(self):
        return self.to(base_unit(self.unit.dims))

    def simplify(self):
        from .units import UNITS
        for sym in DERIVED:
            if UNITS[sym][1] == self.unit.dims:
                return self.to(Unit.atom(sym))
        return self.to_base()

    def __float__(self):
        if not self.unit.dimensionless:
            raise DimensionError("quantity is not dimensionless")
        return float(self._si())

    # ---- arithmetic ----
    @staticmethod
    def _wrap(x):
        if isinstance(x, Quantity):
            return x
        if _is_number(x):
            return Quantity(x, _ONE)
        return None

    def __add__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return Quantity(self.value + o.to(self.unit).value, self.unit)

    def __radd__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return o + self

    def __sub__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return Quantity(self.value - o.to(self.unit).value, self.unit)

    def __rsub__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return o - self

    def __mul__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return Quantity(self.value * o.value, self.unit * o.unit)

    def __rmul__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return o * self

    def __truediv__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return Quantity(self.value / o.value, self.unit / o.unit)

    def __rtruediv__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        return o / self

    def __pow__(self, n):
        if isinstance(n, bool) or not isinstance(n, int):
            raise TypeError("exponent must be an int")
        return Quantity(self.value ** n, self.unit ** n)

    def __neg__(self):
        return Quantity(-self.value, self.unit)

    def __abs__(self):
        return Quantity(abs(self.value), self.unit)

    # ---- comparison ----
    def _pair(self, other):
        o = self._wrap(other)
        if o is None:
            return None
        if o.unit.dims != self.unit.dims:
            raise DimensionError("incompatible dimensions")
        return float(self._si()), float(o._si())

    def __eq__(self, other):
        o = self._wrap(other)
        if o is None:
            return NotImplemented
        if o.unit.dims != self.unit.dims:
            return False
        a, b = float(self._si()), float(o._si())
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0)

    def __lt__(self, other):
        p = self._pair(other)
        if p is None:
            return NotImplemented
        return not self == other and p[0] < p[1]

    def __le__(self, other):
        p = self._pair(other)
        if p is None:
            return NotImplemented
        return self == other or p[0] < p[1]

    def __gt__(self, other):
        p = self._pair(other)
        if p is None:
            return NotImplemented
        return not self == other and p[0] > p[1]

    def __ge__(self, other):
        p = self._pair(other)
        if p is None:
            return NotImplemented
        return self == other or p[0] > p[1]

    # ---- formatting ----
    def __format__(self, spec):
        text = format(self.value, spec or "g")
        return f"{text} {self.unit.symbol}" if self.unit.symbol else text

    def __str__(self):
        return format(self, "")

    def __repr__(self):
        return f"Quantity({self.value!r}, {self.unit.symbol!r})"
