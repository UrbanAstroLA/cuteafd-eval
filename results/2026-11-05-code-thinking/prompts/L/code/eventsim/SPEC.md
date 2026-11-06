Build a Python package named `eventsim`: a discrete-event simulation kernel with generator-based processes, a capacity-limited resource, and statistics collectors. Python 3.12, standard library only.

## Files

- `eventsim/__init__.py` — re-exports `Environment`, `Process`, `Timeout`, `Resource`, `Request`, `Tally`, `TimeSeries`, `SimError`.
- `eventsim/errors.py` — `SimError(Exception)`.
- `eventsim/core.py` — `Environment`, `Process`, `Timeout`.
- `eventsim/resource.py` — `Resource`, `Request`.
- `eventsim/stats.py` — `Tally`, `TimeSeries`.

## core.py

`Environment(initial_time=0)` has a clock `now` (read-only property) and an event queue. Every event has a time, a priority (int, lower runs first) and a sequence number from a per-environment counter that increases each time an event is scheduled. Events run in ascending `(time, priority, sequence)` order, so events with equal time and priority run in the order they were scheduled. Running an event first sets `now` to its time. Events the package schedules internally use priority 0.

- `schedule(delay, callback, priority=0)` — schedule `callback()` (no arguments) at `now + delay`. A negative delay raises `ValueError`.
- `peek()` — time of the next event, or `math.inf` if the queue is empty.
- `process(gen, name=None) -> Process` — `gen` must be a generator object (anything else, including a generator function, raises `TypeError`). Schedules the process's first step at `now`; the generator does not run during this call. The default name is `"process-<k>"`, where `k` counts all processes created in this environment, starting at 1.
- `run(until=None)` — with `until=None`, run events until the queue is empty. Otherwise run every event whose time is strictly less than `until` (including events scheduled while running), then set `now = until`; other events stay queued for a later `run`. `until < now` raises `ValueError`. An exception raised by a process or callback propagates out of `run` unchanged.

`Timeout(delay, value=None)` — a negative `delay` raises `ValueError`.

A *step* of a process sends a value into its generator (`None` for the first step) and acts on what is yielded:

- `Timeout` — schedule the next step at `now + delay`, sending `value`.
- `Request` — schedule the next step at the time the request is granted (at `now` if it is already granted), sending the request itself. The step is always scheduled as a new event, never run immediately.
- `Process` — schedule the next step at the time that process finishes (at `now` if it has already finished), sending its return value. Several processes waiting on the same process are scheduled in the order they started waiting.
- anything else — raise `SimError`.

When the generator returns, the process finishes. `Process` attributes: `name`; `is_alive` (`True` until it finishes); `value` (the generator's return value, `None` until then).

## resource.py

`Resource(env, capacity=1)` — `capacity` must be an `int` >= 1, else `ValueError`. Its *start time* is `env.now` at creation. `request` and `release` may be called from anywhere, not only from processes.

- `request() -> Request` — submits a request at once. If `count < capacity` and no request is waiting, it is granted immediately; otherwise it joins the end of the FIFO queue.
- `release(req)` — `req` must be a granted, not yet released request of this resource, else `SimError`. Frees its slot, then grants waiting requests from the head of the queue while a slot is free. It does not suspend the caller.
- `count` — the number of granted, unreleased requests. `queue` — a new list of the waiting requests, head first.
- `waits` — a `Tally` that observes `granted_at - requested_at` at every grant (an immediate grant observes 0).
- `busy` and `queue_length` — `TimeSeries` (initial level 0, created with the resource) that are updated to `count` and `len(queue)` whenever those change.
- `utilisation(until=None)` — `busy.mean(until) / capacity`.

`Request` attributes: `resource`, `requested_at`, `granted_at` (`None` until granted), `released_at` (`None` until released).

## stats.py

`Tally()` summarises observations:

- `observe(x)`; attributes `count` and `total` (sum; `0` when empty), `minimum` and `maximum` (`None` when empty).
- `mean()` — `total / count`, or `None` when empty.
- `variance()` — sample variance (divisor `count - 1`), or `None` when `count < 2`.

`TimeSeries(env, initial=0)` records a piecewise-constant level from its *start time* `env.now` (attribute `start`).

- `update(value)` — the level is `value` from `env.now` on. When several updates happen at the same time, the last one wins.
- `level` — the current level.
- `mean(until=None)` — the time-weighted average level over `[start, until]` (`until` defaults to `env.now`): the integral of the level over that interval divided by `until - start`. If `until == start`, return the level in effect at `start` (after any updates made at that time). `until` earlier than `start` or later than `env.now` raises `ValueError`. Always returns a `float`.
