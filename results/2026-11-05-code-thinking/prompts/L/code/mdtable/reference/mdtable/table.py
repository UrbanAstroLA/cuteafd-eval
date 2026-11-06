import re

ALIGNS = (None, "left", "right", "center")
_NUM = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")


class Table:
    def __init__(self, headers, rows, aligns=None):
        self.headers = list(headers)
        if len(set(self.headers)) != len(self.headers):
            raise ValueError("duplicate header names")
        self.rows = [list(r) for r in rows]
        for r in self.rows:
            if len(r) != len(self.headers):
                raise ValueError("row length does not match headers")
        self.aligns = [None] * len(self.headers) if aligns is None else list(aligns)
        if len(self.aligns) != len(self.headers) or any(a not in ALIGNS for a in self.aligns):
            raise ValueError("invalid aligns")

    def __eq__(self, other):
        if not isinstance(other, Table):
            return NotImplemented
        return (self.headers, self.rows, self.aligns) == (other.headers, other.rows, other.aligns)

    def __repr__(self):
        return f"Table({self.headers!r}, {self.rows!r}, {self.aligns!r})"

    def _index(self, name):
        try:
            return self.headers.index(name)
        except ValueError:
            raise KeyError(name) from None

    def column(self, name):
        i = self._index(name)
        return [r[i] for r in self.rows]

    def records(self):
        return [dict(zip(self.headers, r)) for r in self.rows]

    def select(self, names):
        names = list(names)
        if len(set(names)) != len(names):
            raise ValueError("duplicate names in selection")
        idx = [self._index(n) for n in names]
        return Table(names, [[r[i] for i in idx] for r in self.rows], [self.aligns[i] for i in idx])

    def filter(self, predicate):
        rows = [r for r in self.rows if predicate(dict(zip(self.headers, r)))]
        return Table(self.headers, rows, self.aligns)

    def sort(self, by, descending=False):
        names = [by] if isinstance(by, str) else list(by)
        idx = [self._index(n) for n in names]
        rows = list(self.rows)
        for i in reversed(idx):
            empty = [r for r in rows if r[i] == ""]
            full = [r for r in rows if r[i] != ""]
            full.sort(key=lambda r: _key(r[i]), reverse=descending)
            rows = full + empty
        return Table(self.headers, rows, self.aligns)


def _key(cell):
    if _NUM.fullmatch(cell):
        return (0, float(cell), "", "")
    return (1, 0.0, cell.casefold(), cell)
