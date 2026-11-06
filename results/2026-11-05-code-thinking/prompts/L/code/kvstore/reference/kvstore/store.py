import time

from .errors import TransactionError

_MISSING = object()


class Store:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._data = {}  # key -> (value, expires_at)
        self._undo = []  # stack of dicts: key -> previous entry or _MISSING

    def _live(self, key):
        e = self._data.get(key)
        if e is None:
            return None
        if e[1] is not None and self._clock() >= e[1]:
            return None
        return e

    def _record(self, key):
        if self._undo:
            log = self._undo[-1]
            if key not in log:
                log[key] = self._data.get(key, _MISSING)

    def set(self, key, value, ttl=None):
        if ttl is not None and not ttl > 0:
            raise ValueError("ttl must be > 0")
        self._record(key)
        self._data[key] = (value, None if ttl is None else self._clock() + ttl)

    def get(self, key):
        e = self._live(key)
        return None if e is None else e[0]

    def delete(self, key):
        live = self._live(key) is not None
        if key in self._data:
            self._record(key)
            del self._data[key]
        return live

    def count(self, value):
        return sum(1 for k in self._data if (e := self._live(k)) is not None and e[0] == value)

    def keys(self, prefix=""):
        return sorted(k for k in self._data if k.startswith(prefix) and self._live(k) is not None)

    def ttl(self, key):
        e = self._live(key)
        if e is None:
            return -1
        if e[1] is None:
            return None
        return e[1] - self._clock()

    def begin(self):
        self._undo.append({})

    def rollback(self):
        if not self._undo:
            raise TransactionError("no transaction")
        log = self._undo.pop()
        for k, prev in log.items():
            if prev is _MISSING:
                self._data.pop(k, None)
            else:
                self._data[k] = prev

    def commit(self):
        if not self._undo:
            raise TransactionError("no transaction")
        self._undo.clear()

    @property
    def depth(self):
        return len(self._undo)

    def snapshot(self):
        out = {}
        for k in self._data:
            e = self._live(k)
            if e is not None:
                out[k] = {"value": e[0], "expires_at": e[1]}
        return out
