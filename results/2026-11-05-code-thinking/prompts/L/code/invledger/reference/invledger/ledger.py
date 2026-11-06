import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from .errors import InsufficientStock, UnknownSKU

_SKU = re.compile(r"[A-Z0-9-]{1,32}")


def _qty(q):
    if isinstance(q, bool) or not isinstance(q, int):
        raise TypeError("quantity must be an int")
    return q


def _cost(v):
    if isinstance(v, bool) or not isinstance(v, (int, str, Decimal)):
        raise TypeError("cost must be int, str or Decimal")
    try:
        d = Decimal(v)
    except InvalidOperation:
        raise ValueError(f"invalid cost {v!r}") from None
    if not d.is_finite() or d < 0:
        raise ValueError(f"invalid cost {v!r}")
    return d


@dataclass(frozen=True)
class Movement:
    seq: int
    kind: str
    sku: str
    qty: int
    unit_cost: Optional[Decimal]
    amount: Decimal
    ref: Optional[str]


class _Item:
    def __init__(self, last_cost):
        self.layers = []      # [qty, cost]
        self.backorders = []  # [qty, cost]
        self.last_cost = last_cost
        self.variance = Decimal(0)

    def on_hand(self):
        return sum(q for q, _ in self.layers) - sum(q for q, _ in self.backorders)


class Ledger:
    def __init__(self, allow_negative=False):
        self.allow_negative = allow_negative
        self._items = {}
        self._moves = []

    # -- helpers --
    def _item(self, sku):
        try:
            return self._items[sku]
        except (KeyError, TypeError):
            raise UnknownSKU(sku) from None

    def _record(self, kind, sku, qty, unit_cost, amount, ref):
        m = Movement(len(self._moves) + 1, kind, sku, qty, unit_cost, amount, ref)
        self._moves.append(m)
        return m

    @staticmethod
    def _inbound(it, qty, cost):
        it.last_cost = cost
        while qty and it.backorders:
            b = it.backorders[0]
            c = min(qty, b[0])
            it.variance += c * (cost - b[1])
            b[0] -= c
            qty -= c
            if b[0] == 0:
                it.backorders.pop(0)
        if qty:
            it.layers.append([qty, cost])

    @staticmethod
    def _consume(it, qty):
        total = Decimal(0)
        while qty and it.layers:
            layer = it.layers[0]
            c = min(qty, layer[0])
            total += c * layer[1]
            layer[0] -= c
            qty -= c
            if layer[0] == 0:
                it.layers.pop(0)
        return total, qty

    # -- operations --
    def receive(self, sku, qty, unit_cost, ref=None):
        if not isinstance(sku, str) or not _SKU.fullmatch(sku):
            raise ValueError(f"invalid SKU {sku!r}")
        _qty(qty)
        if qty < 1:
            raise ValueError("qty must be at least 1")
        cost = _cost(unit_cost)
        it = self._items.get(sku)
        if it is None:
            it = self._items[sku] = _Item(cost)
        self._inbound(it, qty, cost)
        return self._record("receipt", sku, qty, cost, qty * cost, ref)

    def issue(self, sku, qty, ref=None):
        it = self._item(sku)
        _qty(qty)
        if qty < 1:
            raise ValueError("qty must be at least 1")
        avail = it.on_hand()
        if qty > avail and not self.allow_negative:
            raise InsufficientStock(sku, qty, avail)
        total, short = self._consume(it, qty)
        if short:
            it.backorders.append([short, it.last_cost])
            total += short * it.last_cost
        return self._record("issue", sku, -qty, None, -total, ref)

    def adjust(self, sku, delta, unit_cost=None, ref=None):
        it = self._item(sku)
        _qty(delta)
        if delta == 0:
            raise ValueError("delta must be non-zero")
        if delta > 0:
            cost = it.last_cost if unit_cost is None else _cost(unit_cost)
            self._inbound(it, delta, cost)
            return self._record("adjust", sku, delta, cost, delta * cost, ref)
        if unit_cost is not None:
            raise ValueError("unit_cost not allowed for a negative adjustment")
        avail = it.on_hand()
        if -delta > avail:
            raise InsufficientStock(sku, -delta, avail)
        total, _ = self._consume(it, -delta)
        return self._record("adjust", sku, delta, None, -total, ref)

    # -- queries --
    def skus(self):
        return sorted(self._items)

    def on_hand(self, sku):
        return self._item(sku).on_hand()

    def value(self, sku):
        it = self._item(sku)
        return sum((q * c for q, c in it.layers), Decimal(0)) - sum((q * c for q, c in it.backorders), Decimal(0))

    def layers(self, sku):
        return [(q, c) for q, c in self._item(sku).layers]

    def backorders(self, sku):
        return [(q, c) for q, c in self._item(sku).backorders]

    def last_cost(self, sku):
        return self._item(sku).last_cost

    def variance(self, sku):
        return self._item(sku).variance

    def movements(self, sku=None):
        if sku is None:
            return list(self._moves)
        self._item(sku)
        return [m for m in self._moves if m.sku == sku]
