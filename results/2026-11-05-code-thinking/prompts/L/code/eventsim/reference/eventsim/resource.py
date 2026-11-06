from .errors import SimError
from .stats import Tally, TimeSeries


class Request:
    def __init__(self, resource, requested_at):
        self.resource = resource
        self.requested_at = requested_at
        self.granted_at = None
        self.released_at = None
        self._waiters = []


class Resource:
    def __init__(self, env, capacity=1):
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            raise ValueError("capacity must be an int >= 1")
        self.env = env
        self.capacity = capacity
        self._users = []
        self._queue = []
        self.waits = Tally()
        self.busy = TimeSeries(env, 0)
        self.queue_length = TimeSeries(env, 0)

    @property
    def count(self):
        return len(self._users)

    @property
    def queue(self):
        return list(self._queue)

    def _grant(self, req):
        now = self.env.now
        req.granted_at = now
        self._users.append(req)
        self.waits.observe(now - req.requested_at)
        self.busy.update(len(self._users))
        for w in req._waiters:
            w._resume_later(0, req)
        req._waiters = []

    def request(self):
        req = Request(self, self.env.now)
        if len(self._users) < self.capacity and not self._queue:
            self._grant(req)
        else:
            self._queue.append(req)
            self.queue_length.update(len(self._queue))
        return req

    def release(self, req):
        if req.resource is not self or req.granted_at is None or req.released_at is not None:
            raise SimError("request is not held")
        req.released_at = self.env.now
        self._users.remove(req)
        self.busy.update(len(self._users))
        while self._queue and len(self._users) < self.capacity:
            nxt = self._queue.pop(0)
            self.queue_length.update(len(self._queue))
            self._grant(nxt)

    def utilisation(self, until=None):
        return self.busy.mean(until) / self.capacity
