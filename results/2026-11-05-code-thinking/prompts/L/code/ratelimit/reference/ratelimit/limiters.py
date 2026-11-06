import math
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    remaining: int
    retry_after: float


def check_size(name, v):
    if type(v) is not int or v < 1:
        raise ValueError(f"{name} must be an int >= 1")


def check_positive(name, v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError(f"{name} must be a finite number > 0")


class _Limiter:
    def __init__(self, size, clock):
        self._size = size
        self._clock = clock
        self._latest = clock()
        self._init_state(self._latest)

    def _now(self):
        r = self._clock()
        if r > self._latest:
            self._latest = r
        return self._latest

    def _check_cost(self, cost):
        if type(cost) is not int or cost < 1 or cost > self._size:
            raise ValueError(f"cost must be an int from 1 to {self._size}")

    def acquire(self, cost=1):
        self._check_cost(cost)
        return self._decide(self._now(), cost, True)

    def peek(self, cost=1):
        self._check_cost(cost)
        return self._decide(self._now(), cost, False)

    def reset(self):
        self._init_state(self._now())


class TokenBucket(_Limiter):
    def __init__(self, capacity, refill_rate, clock=time.monotonic):
        check_size("capacity", capacity)
        check_positive("refill_rate", refill_rate)
        self.capacity = capacity
        self.refill_rate = refill_rate
        super().__init__(capacity, clock)

    def _init_state(self, now):
        self._tokens = float(self.capacity)
        self._last = now

    def _refill(self, now):
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.refill_rate)
        self._last = now

    def _decide(self, now, cost, consume):
        self._refill(now)
        if self._tokens >= cost:
            left = self._tokens - cost
            if consume:
                self._tokens = left
            return Decision(True, math.floor(left), 0.0)
        return Decision(False, math.floor(self._tokens), (cost - self._tokens) / self.refill_rate)

    @property
    def tokens(self):
        self._refill(self._now())
        return float(self._tokens)


class FixedWindow(_Limiter):
    def __init__(self, limit, window, clock=time.monotonic):
        check_size("limit", limit)
        check_positive("window", window)
        self.limit = limit
        self.window = window
        super().__init__(limit, clock)

    def _init_state(self, now):
        self._index = None
        self._count = 0

    def _decide(self, now, cost, consume):
        idx = math.floor(now / self.window)
        if idx != self._index:
            self._index = idx
            self._count = 0
        if self._count + cost <= self.limit:
            if consume:
                self._count += cost
                return Decision(True, self.limit - self._count, 0.0)
            return Decision(True, self.limit - self._count - cost, 0.0)
        return Decision(False, self.limit - self._count, (idx + 1) * self.window - now)


class SlidingLog(_Limiter):
    def __init__(self, limit, window, clock=time.monotonic):
        check_size("limit", limit)
        check_positive("window", window)
        self.limit = limit
        self.window = window
        super().__init__(limit, clock)

    def _init_state(self, now):
        self._log = []

    def _decide(self, now, cost, consume):
        self._log = [t for t in self._log if now - t < self.window]
        live = len(self._log)
        if live + cost <= self.limit:
            if consume:
                self._log.extend([now] * cost)
            return Decision(True, self.limit - live - cost, 0.0)
        ts = sorted(self._log)
        k = live + cost - self.limit
        return Decision(False, self.limit - live, ts[k - 1] + self.window - now)
