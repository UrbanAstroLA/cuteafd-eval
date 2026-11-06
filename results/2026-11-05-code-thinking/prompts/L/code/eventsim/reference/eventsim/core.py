import heapq
import inspect
import math

from .errors import SimError


class Timeout:
    def __init__(self, delay, value=None):
        if delay < 0:
            raise ValueError("negative delay")
        self.delay = delay
        self.value = value


class Process:
    def __init__(self, env, gen, name):
        self.env = env
        self.name = name
        self.is_alive = True
        self.value = None
        self._gen = gen
        self._waiters = []

    def _resume_later(self, delay, value):
        self.env.schedule(delay, lambda: self._step(value))

    def _step(self, send):
        from .resource import Request
        try:
            target = self._gen.send(send)
        except StopIteration as stop:
            self.is_alive = False
            self.value = stop.value
            for w in self._waiters:
                w._resume_later(0, self.value)
            self._waiters = []
            return
        if isinstance(target, Timeout):
            self._resume_later(target.delay, target.value)
        elif isinstance(target, Request):
            if target.granted_at is not None:
                self._resume_later(0, target)
            else:
                target._waiters.append(self)
        elif isinstance(target, Process):
            if not target.is_alive:
                self._resume_later(0, target.value)
            else:
                target._waiters.append(self)
        else:
            raise SimError(f"process {self.name} yielded unsupported object {target!r}")


class Environment:
    def __init__(self, initial_time=0):
        self._now = initial_time
        self._queue = []
        self._seq = 0
        self._nproc = 0

    @property
    def now(self):
        return self._now

    def schedule(self, delay, callback, priority=0):
        if delay < 0:
            raise ValueError("negative delay")
        heapq.heappush(self._queue, (self._now + delay, priority, self._seq, callback))
        self._seq += 1

    def peek(self):
        return self._queue[0][0] if self._queue else math.inf

    def process(self, gen, name=None):
        if not inspect.isgenerator(gen):
            raise TypeError("process() needs a generator")
        self._nproc += 1
        p = Process(self, gen, name if name is not None else f"process-{self._nproc}")
        p._resume_later(0, None)
        return p

    def run(self, until=None):
        if until is not None and until < self._now:
            raise ValueError("until is in the past")
        while self._queue and (until is None or self._queue[0][0] < until):
            t, _, _, cb = heapq.heappop(self._queue)
            self._now = t
            cb()
        if until is not None:
            self._now = until
