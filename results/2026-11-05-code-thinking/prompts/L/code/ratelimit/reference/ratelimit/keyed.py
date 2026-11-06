from collections import OrderedDict


class KeyedLimiter:
    def __init__(self, factory, max_keys=None):
        if max_keys is not None and (type(max_keys) is not int or max_keys < 1):
            raise ValueError("max_keys must be None or an int >= 1")
        self._factory = factory
        self.max_keys = max_keys
        self._limiters = OrderedDict()

    def acquire(self, key, cost=1):
        lim = self._limiters.get(key)
        if lim is None:
            if self.max_keys is not None and len(self._limiters) >= self.max_keys:
                self._limiters.popitem(last=False)
            lim = self._limiters[key] = self._factory()
        else:
            self._limiters.move_to_end(key)
        return lim.acquire(cost)

    def peek(self, key, cost=1):
        lim = self._limiters.get(key)
        if lim is None:
            lim = self._factory()
        return lim.peek(cost)

    def keys(self):
        return list(self._limiters)

    def reset(self, key):
        return self._limiters.pop(key, None) is not None

    def __len__(self):
        return len(self._limiters)

    def __contains__(self, key):
        return key in self._limiters
