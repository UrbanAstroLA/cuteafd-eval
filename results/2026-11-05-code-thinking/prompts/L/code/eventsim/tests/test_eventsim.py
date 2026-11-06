import math

import pytest

from eventsim import Environment, Process, Request, Resource, SimError, Tally, TimeSeries, Timeout


def customer(env, res, name, arrive, service, log):
    yield Timeout(arrive)
    req = res.request()
    got = yield req
    assert got is req
    log.append((env.now, name))
    yield Timeout(service)
    res.release(req)
    return req


# ---- environment and event ordering ----

def test_schedule_ties_run_in_scheduling_order():
    env = Environment()
    log = []
    for name, delay in (("a", 2), ("b", 1), ("c", 2), ("d", 1)):
        env.schedule(delay, lambda name=name: log.append((env.now, name)))
    env.run()
    assert log == [(1, "b"), (1, "d"), (2, "a"), (2, "c")]
    assert env.now == 2


def test_schedule_priority_breaks_ties_before_sequence():
    env = Environment()
    log = []
    env.schedule(1, lambda: log.append("a"))
    env.schedule(1, lambda: log.append("b"), priority=-1)
    env.schedule(0.5, lambda: log.append("c"), priority=5)
    env.schedule(1, lambda: log.append("d"))
    env.run()
    assert log == ["c", "b", "a", "d"]


def test_negative_delays_rejected():
    env = Environment()
    with pytest.raises(ValueError):
        env.schedule(-1, lambda: None)
    with pytest.raises(ValueError):
        Timeout(-0.5)


def test_peek_and_initial_time():
    env = Environment(initial_time=10)
    assert env.now == 10
    assert env.peek() == math.inf
    env.schedule(3, lambda: None)
    assert env.peek() == 13
    env.run()
    assert env.now == 13 and env.peek() == math.inf


def test_process_requires_generator():
    env = Environment()

    def gen():
        yield Timeout(1)

    with pytest.raises(TypeError):
        env.process(gen)
    with pytest.raises(TypeError):
        env.process(lambda: None)


def test_process_does_not_start_until_run_and_names():
    env = Environment()
    log = []

    def worker(tag):
        log.append((env.now, tag))
        yield Timeout(3)
        log.append((env.now, tag))
        return tag.upper()

    p1 = env.process(worker("x"))
    p2 = env.process(worker("y"), name="second")
    p3 = env.process(worker("z"))
    assert isinstance(p1, Process)
    assert log == []
    assert (p1.name, p2.name, p3.name) == ("process-1", "second", "process-3")
    assert p1.is_alive and p1.value is None
    env.run()
    assert log == [(0, "x"), (0, "y"), (0, "z"), (3, "x"), (3, "y"), (3, "z")]
    assert not p1.is_alive and p1.value == "X"


def test_timeout_value_is_sent():
    env = Environment()
    got = []

    def p():
        got.append((yield Timeout(2, "hi")))
        got.append((yield Timeout(0)))

    env.process(p())
    env.run()
    assert got == ["hi", None]


def test_interleaved_processes_tie_order():
    env = Environment()
    log = []

    def ticker(name, period):
        while True:
            log.append((env.now, name))
            yield Timeout(period)

    env.process(ticker("A", 3))
    env.process(ticker("B", 2))
    env.run(until=7)
    assert log == [(0, "A"), (0, "B"), (2, "B"), (3, "A"), (4, "B"), (6, "A"), (6, "B")]


def test_run_until_is_exclusive_and_resumable():
    env = Environment()
    log = []

    def ticker():
        while True:
            log.append(env.now)
            yield Timeout(2)

    env.process(ticker())
    env.run(until=4)
    assert log == [0, 2] and env.now == 4 and env.peek() == 4
    env.run(until=7)
    assert log == [0, 2, 4, 6] and env.now == 7
    env.run(until=7)
    assert log == [0, 2, 4, 6]
    with pytest.raises(ValueError):
        env.run(until=3)


def test_run_until_on_empty_queue_advances_clock():
    env = Environment()
    env.run()
    assert env.now == 0
    env.run(until=5)
    assert env.now == 5


def test_exception_in_process_propagates():
    env = Environment()

    def bad():
        yield Timeout(3)
        raise KeyError("boom")

    env.process(bad())
    with pytest.raises(KeyError):
        env.run()
    assert env.now == 3


def test_unsupported_yield_raises_simerror():
    env = Environment()

    def bad():
        yield 5

    env.process(bad())
    with pytest.raises(SimError):
        env.run()


def test_waiting_on_process_gets_return_value():
    env = Environment()
    log = []

    def child():
        yield Timeout(4)
        return 42

    def parent(tag, c, delay):
        yield Timeout(delay)
        v = yield c
        log.append((env.now, tag, v))

    c = env.process(child())
    env.process(parent("late", c, 6))
    env.process(parent("p1", c, 1))
    env.process(parent("p2", c, 0))
    env.run()
    assert log == [(4, "p2", 42), (4, "p1", 42), (6, "late", 42)]


# ---- resource ----

def test_resource_fifo_single_server():
    env = Environment()
    res = Resource(env)
    log = []
    procs = [env.process(customer(env, res, n, a, 5, log)) for n, a in (("c0", 0), ("c1", 1), ("c2", 2))]
    env.run()
    assert log == [(0, "c0"), (5, "c1"), (10, "c2")]
    reqs = [p.value for p in procs]
    assert isinstance(reqs[0], Request)
    assert [(r.requested_at, r.granted_at, r.released_at) for r in reqs] == [(0, 0, 5), (1, 5, 10), (2, 10, 15)]
    assert env.now == 15


def test_resource_capacity_two():
    env = Environment()
    res = Resource(env, capacity=2)
    log = []
    for n, s in (("a", 4), ("b", 2), ("c", 3), ("d", 1)):
        env.process(customer(env, res, n, 0, s, log))
    env.run(until=3)
    assert res.count == 2 and len(res.queue) == 1
    env.run()
    assert log == [(0, "a"), (0, "b"), (2, "c"), (4, "d")]
    assert res.count == 0 and res.queue == []


def test_release_then_rerequest_goes_to_back_of_queue():
    env = Environment()
    res = Resource(env)
    log = []

    def greedy():
        req = res.request()
        yield req
        log.append((env.now, "A1"))
        yield Timeout(5)
        res.release(req)
        req2 = res.request()
        yield req2
        log.append((env.now, "A2"))
        res.release(req2)

    env.process(greedy())
    env.process(customer(env, res, "B", 1, 2, log))
    env.run()
    assert log == [(0, "A1"), (5, "B"), (7, "A2")]


def test_grant_resumes_via_event_queue():
    env = Environment()
    res = Resource(env)
    log = []

    def holder():
        req = res.request()
        yield req
        yield Timeout(5)
        res.release(req)
        log.append("A released")

    def waiter():
        req = res.request()
        yield req
        log.append("B granted")

    env.process(holder())
    env.process(waiter())
    env.schedule(1, lambda: env.schedule(4, lambda: log.append("C")))
    env.run()
    assert log == ["A released", "C", "B granted"]


def test_immediate_grant_still_yields_control():
    env = Environment()
    res = Resource(env)
    log = []

    def a():
        req = res.request()
        assert req.granted_at == 0
        yield req
        log.append("A")

    def b():
        log.append("B")
        yield Timeout(0)

    env.process(a())
    env.process(b())
    env.run()
    assert log == ["B", "A"]


def test_release_errors_and_queue_copy():
    env = Environment()
    res = Resource(env)
    other = Resource(env)
    r1 = res.request()
    r2 = res.request()
    assert r1.granted_at == 0 and r2.granted_at is None
    q = res.queue
    q.clear()
    assert res.queue == [r2]
    with pytest.raises(SimError):
        res.release(r2)
    res.release(r1)
    assert r2.granted_at == 0 and res.count == 1 and res.queue == []
    with pytest.raises(SimError):
        res.release(r1)
    with pytest.raises(SimError):
        res.release(other.request())


def test_resource_capacity_validation():
    env = Environment()
    for bad in (0, -1, 1.5):
        with pytest.raises(ValueError):
            Resource(env, capacity=bad)


def test_resource_statistics():
    env = Environment()
    res = Resource(env)
    log = []
    for n, a in (("c0", 0), ("c1", 1), ("c2", 2)):
        env.process(customer(env, res, n, a, 5, log))
    env.run(until=20)
    w = res.waits
    assert w.count == 3 and w.total == 12
    assert w.mean() == 4 and w.minimum == 0 and w.maximum == 8
    assert w.variance() == pytest.approx(16.0)
    assert res.utilisation() == pytest.approx(0.75)
    assert res.utilisation(15) == pytest.approx(1.0)
    assert res.utilisation(0) == 1.0
    assert res.queue_length.mean() == pytest.approx(0.6)
    assert res.queue_length.mean(5) == pytest.approx(7 / 5)
    assert res.busy.level == 0


def test_resource_created_mid_run_uses_its_start_time():
    env = Environment(initial_time=10)
    holder = {}

    def setup():
        yield Timeout(10)
        res = Resource(env, capacity=2)
        holder["res"] = res
        req = res.request()
        yield Timeout(5)
        res.release(req)

    env.process(setup())
    env.run(until=40)
    res = holder["res"]
    assert res.busy.start == 20
    assert res.utilisation() == pytest.approx(5 / 20 / 2)


# ---- statistics ----

def test_tally():
    t = Tally()
    assert t.count == 0 and t.total == 0
    assert t.mean() is None and t.minimum is None and t.maximum is None and t.variance() is None
    t.observe(3)
    assert t.mean() == 3 and t.variance() is None
    t2 = Tally()
    for x in (2, 4, 4, 4, 5, 5, 7, 9):
        t2.observe(x)
    assert t2.count == 8 and t2.total == 40 and t2.mean() == 5
    assert (t2.minimum, t2.maximum) == (2, 9)
    assert t2.variance() == pytest.approx(32 / 7)


def test_timeseries_time_weighted_mean():
    env = Environment()
    ts = TimeSeries(env, 2)
    assert ts.level == 2
    env.schedule(0, lambda: ts.update(4))
    env.schedule(3, lambda: ts.update(1))
    env.schedule(3, lambda: ts.update(0))
    env.schedule(5, lambda: ts.update(10))
    env.run(until=10)
    assert ts.level == 10
    assert ts.mean() == pytest.approx(6.2)
    assert ts.mean(5) == pytest.approx(2.4)
    assert ts.mean(4) == pytest.approx(3.0)
    m0 = ts.mean(0)
    assert m0 == 4.0 and isinstance(m0, float)
    with pytest.raises(ValueError):
        ts.mean(11)
    with pytest.raises(ValueError):
        ts.mean(-1)
