import copy
import dataclasses

import pytest

from ratelimit import (ConfigError, Decision, FixedWindow, KeyedLimiter, RateLimited, RateLimitError, Registry,
                       SlidingLog, TokenBucket)


class FakeClock:
    def __init__(self, t=100.0):
        self.t = t

    def __call__(self):
        return self.t

    def set(self, t):
        self.t = t


@pytest.fixture
def clock():
    return FakeClock()


def test_decision_is_frozen_dataclass():
    d = Decision(True, 3, 0.0)
    assert [f.name for f in dataclasses.fields(Decision)] == ["allowed", "remaining", "retry_after"]
    assert d == Decision(allowed=True, remaining=3, retry_after=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.allowed = False


def test_token_bucket_consume_and_deny(clock):
    b = TokenBucket(3, 0.5, clock=clock)
    assert [b.acquire() for _ in range(3)] == [Decision(True, 2, 0.0), Decision(True, 1, 0.0),
                                               Decision(True, 0, 0.0)]
    assert b.acquire() == Decision(False, 0, 2.0)
    clock.set(101.0)
    assert b.tokens == 0.5
    assert b.peek() == Decision(False, 0, 1.0)
    assert b.peek(2) == Decision(False, 0, 3.0)
    clock.set(102.0)
    assert b.acquire() == Decision(True, 0, 0.0)
    assert b.tokens == 0.0


def test_token_bucket_refill_caps_and_all_or_nothing(clock):
    b = TokenBucket(4, 2, clock=clock)
    assert b.acquire(3) == Decision(True, 1, 0.0)
    clock.set(100.25)
    assert b.acquire(2) == Decision(False, 1, 0.25)
    assert b.tokens == 1.5
    clock.set(200.0)
    assert b.tokens == 4.0
    assert b.acquire(4) == Decision(True, 0, 0.0)


def test_token_bucket_peek_does_not_consume(clock):
    b = TokenBucket(2, 1, clock=clock)
    assert b.peek(2) == Decision(True, 0, 0.0)
    assert b.peek(2) == Decision(True, 0, 0.0)
    assert b.acquire() == Decision(True, 1, 0.0)
    assert b.peek(1) == Decision(True, 0, 0.0)


def test_clock_going_backwards_stands_still(clock):
    b = TokenBucket(2, 1, clock=clock)
    b.acquire(2)
    clock.set(101.0)
    assert b.tokens == 1.0
    clock.set(90.0)
    assert b.tokens == 1.0
    assert b.acquire() == Decision(True, 0, 0.0)
    clock.set(101.5)
    assert b.tokens == 0.5
    c2 = FakeClock(25.0)
    w = FixedWindow(1, 10, clock=c2)
    w.acquire()
    c2.set(19.0)
    assert w.acquire() == Decision(False, 0, 5.0)


def test_fixed_window_aligned_to_zero(clock):
    clock.set(25.0)
    w = FixedWindow(3, 10, clock=clock)
    assert w.acquire() == Decision(True, 2, 0.0)
    assert w.acquire(2) == Decision(True, 0, 0.0)
    assert w.acquire() == Decision(False, 0, 5.0)
    clock.set(29.5)
    assert w.peek() == Decision(False, 0, 0.5)
    clock.set(30.0)
    assert w.acquire() == Decision(True, 2, 0.0)
    assert w.acquire(3) == Decision(False, 2, 10.0)
    assert w.peek(2) == Decision(True, 0, 0.0)


def test_fixed_window_skipped_windows_reset(clock):
    w = FixedWindow(2, 0.5, clock=clock)
    w.acquire(2)
    clock.set(1000.25)
    assert w.acquire() == Decision(True, 1, 0.0)
    assert w.acquire(2) == Decision(False, 1, 0.25)


def test_sliding_log_retry_after(clock):
    clock.set(0.0)
    s = SlidingLog(4, 10, clock=clock)
    s.acquire()
    clock.set(1.0)
    assert s.acquire(2) == Decision(True, 1, 0.0)
    clock.set(2.5)
    assert s.acquire() == Decision(True, 0, 0.0)
    clock.set(5.0)
    assert s.peek() == Decision(False, 0, 5.0)
    assert s.peek(2) == Decision(False, 0, 6.0)
    assert s.peek(4) == Decision(False, 0, 7.5)
    assert s.acquire(3) == Decision(False, 0, 6.0)


def test_sliding_log_expiry_boundary(clock):
    clock.set(0.0)
    s = SlidingLog(2, 10, clock=clock)
    s.acquire()
    clock.set(1.0)
    s.acquire()
    clock.set(9.75)
    assert s.acquire() == Decision(False, 0, 0.25)
    clock.set(10.0)
    assert s.acquire() == Decision(True, 0, 0.0)
    assert s.peek() == Decision(False, 0, 1.0)
    clock.set(11.0)
    assert s.peek() == Decision(True, 0, 0.0)
    assert s.peek(2) == Decision(False, 1, 9.0)


def test_reset(clock):
    b = TokenBucket(2, 1, clock=clock)
    b.acquire(2)
    b.reset()
    assert b.tokens == 2.0
    w = FixedWindow(1, 60, clock=clock)
    w.acquire()
    w.reset()
    assert w.acquire() == Decision(True, 0, 0.0)
    s = SlidingLog(1, 60, clock=clock)
    s.acquire()
    s.reset()
    assert s.acquire() == Decision(True, 0, 0.0)


@pytest.mark.parametrize("make", [
    lambda c: TokenBucket(0, 1, clock=c), lambda c: TokenBucket(2.0, 1, clock=c),
    lambda c: TokenBucket(2, 0, clock=c), lambda c: TokenBucket(2, -1, clock=c),
    lambda c: TokenBucket(True, 1, clock=c), lambda c: TokenBucket(2, float("inf"), clock=c),
    lambda c: FixedWindow(1, True, clock=c), lambda c: FixedWindow(-1, 5, clock=c),
    lambda c: SlidingLog(3, 0.0, clock=c), lambda c: SlidingLog("3", 1, clock=c),
])
def test_constructor_validation(make, clock):
    with pytest.raises(ValueError):
        make(clock)


@pytest.mark.parametrize("cost", [0, -1, 4, 1.0, True, "1"])
def test_cost_validation(cost, clock):
    for lim in (TokenBucket(3, 1, clock=clock), FixedWindow(3, 1, clock=clock), SlidingLog(3, 1, clock=clock)):
        with pytest.raises(ValueError):
            lim.acquire(cost)
        with pytest.raises(ValueError):
            lim.peek(cost)


def test_keyed_independent_keys(clock):
    k = KeyedLimiter(lambda: FixedWindow(1, 10, clock=clock))
    assert k.acquire("a").allowed
    assert not k.acquire("a").allowed
    assert k.acquire("b").allowed
    assert len(k) == 2 and "a" in k and "c" not in k


def test_keyed_peek_does_not_track(clock):
    k = KeyedLimiter(lambda: TokenBucket(2, 1, clock=clock))
    assert k.peek("x", 2) == Decision(True, 0, 0.0)
    assert "x" not in k and k.keys() == []
    k.acquire("x", 2)
    assert k.peek("x") == Decision(False, 0, 1.0)


def test_keyed_lru_eviction(clock):
    k = KeyedLimiter(lambda: FixedWindow(1, 10, clock=clock), max_keys=2)
    k.acquire("a")
    k.acquire("b")
    assert k.keys() == ["a", "b"]
    assert not k.acquire("a").allowed
    assert k.keys() == ["b", "a"]
    k.peek("b")
    assert k.keys() == ["b", "a"]
    k.acquire("c")
    assert k.keys() == ["a", "c"]
    assert k.acquire("b").allowed
    assert k.keys() == ["c", "b"]


def test_keyed_reset_and_validation(clock):
    k = KeyedLimiter(lambda: FixedWindow(1, 10, clock=clock))
    k.acquire("a")
    assert k.reset("a") is True
    assert k.reset("a") is False
    assert k.acquire("a").allowed
    for bad in (0, -2, 1.5, True):
        with pytest.raises(ValueError):
            KeyedLimiter(lambda: None, max_keys=bad)


CONFIG = {
    "defaults": {"window": 60, "per_key": True, "max_keys": 2},
    "policies": {
        "api": {"type": "token_bucket", "capacity": 2, "refill_rate": 0.5, "per_key": False},
        "login": {"type": "sliding_log", "limit": 2},
        "export": {"type": "fixed_window", "limit": 1, "window": 3600, "per_key": False},
    },
}


def test_registry_from_config(clock):
    cfg = copy.deepcopy(CONFIG)
    reg = Registry.from_config(cfg, clock=clock)
    assert cfg == CONFIG
    assert reg.names() == ["api", "export", "login"]
    assert "login" in reg and "nope" not in reg
    assert reg.check("api") == Decision(True, 1, 0.0)
    assert reg.check("api", cost=2) == Decision(False, 1, 2.0)
    assert reg.check("export") == Decision(True, 0, 0.0)
    assert reg.peek("export") == Decision(False, 0, 3500.0)


def test_registry_per_key_with_defaults(clock):
    reg = Registry.from_config(CONFIG, clock=clock)
    assert reg.check("login", "alice").allowed
    clock.set(110.0)
    assert reg.check("login", "alice") == Decision(True, 0, 0.0)
    assert reg.check("login", "alice") == Decision(False, 0, 50.0)
    assert reg.peek("login", "bob") == Decision(True, 1, 0.0)
    reg.check("login", "bob")
    reg.check("login", "carol")
    assert reg.check("login", "alice") == Decision(True, 1, 0.0)


def test_registry_key_rules(clock):
    reg = Registry.from_config(CONFIG, clock=clock)
    with pytest.raises(ValueError):
        reg.check("login")
    with pytest.raises(ValueError):
        reg.check("login", 5)
    with pytest.raises(ValueError):
        reg.check("api", "alice")
    with pytest.raises(ValueError):
        reg.check("api", cost=3)
    with pytest.raises(KeyError):
        reg.check("missing")
    with pytest.raises(KeyError):
        reg.peek("missing")


def test_registry_enforce(clock):
    reg = Registry(clock=clock)
    reg.add("w", {"type": "fixed_window", "limit": 1, "window": 8})
    assert reg.enforce("w") is None
    with pytest.raises(RateLimited) as ei:
        reg.enforce("w")
    assert ei.value.policy == "w" and ei.value.retry_after == 4.0
    assert isinstance(ei.value, RateLimitError)


def test_registry_add_rules(clock):
    reg = Registry(clock=clock)
    reg.add("a", {"type": "sliding_log", "limit": 1, "window": 1, "per_key": True, "max_keys": 1})
    with pytest.raises(ConfigError):
        reg.add("a", {"type": "sliding_log", "limit": 1, "window": 1})
    with pytest.raises(ConfigError):
        reg.add("", {"type": "sliding_log", "limit": 1, "window": 1})
    assert reg.names() == ["a"]
    reg.check("a", "k1")
    assert reg.peek("a", "k1").allowed is False
    reg.check("a", "k2")
    assert reg.peek("a", "k1").allowed is True


@pytest.mark.parametrize("spec,field", [
    ({"limit": 1, "window": 1}, "type"),
    ({"type": "leaky_bucket", "limit": 1}, "type"),
    ({"type": "token_bucket", "capacity": 1}, "refill_rate"),
    ({"type": "token_bucket", "capacity": 1, "refill_rate": 1, "window": 5}, "window"),
    ({"type": "fixed_window", "limit": True, "window": 1}, "limit"),
    ({"type": "fixed_window", "limit": 1, "window": -5}, "window"),
    ({"type": "sliding_log", "limit": 1.0, "window": 1}, "limit"),
    ({"type": "sliding_log", "limit": 1, "window": 1, "per_key": 1}, "per_key"),
    ({"type": "sliding_log", "limit": 1, "window": 1, "max_keys": 5}, "max_keys"),
    ({"type": "sliding_log", "limit": 1, "window": 1, "per_key": True, "max_keys": 0}, "max_keys"),
    ({"type": "sliding_log", "limit": 1, "window": "1"}, "window"),
])
def test_policy_spec_errors(spec, field, clock):
    with pytest.raises(ConfigError) as ei:
        Registry.from_config({"policies": {"pol_x": spec}}, clock=clock)
    msg = str(ei.value)
    assert "pol_x" in msg and field in msg
    assert not isinstance(ei.value, (ValueError, TypeError))


@pytest.mark.parametrize("config,word", [
    ({"policies": {}, "extra": 1}, "extra"),
    ({"defaults": {}}, "policies"),
    ({"policies": []}, "policies"),
    ({"policies": {}, "defaults": {"type": "sliding_log"}}, "type"),
    ({"policies": {}, "defaults": {"burst": 3}}, "burst"),
    ({"policies": {}, "defaults": 5}, "defaults"),
])
def test_top_level_config_errors(config, word, clock):
    with pytest.raises(ConfigError) as ei:
        Registry.from_config(config, clock=clock)
    assert word in str(ei.value)
    with pytest.raises(ConfigError):
        Registry.from_config(["policies"], clock=clock)
    with pytest.raises(ConfigError):
        Registry.from_config({"policies": {"p": "token_bucket"}}, clock=clock)


def test_defaults_applied_only_where_used(clock):
    cfg = {"defaults": {"capacity": 5, "refill_rate": 1, "limit": 2, "window": 4, "max_keys": 1},
           "policies": {"tb": {"type": "token_bucket"}, "fw": {"type": "fixed_window", "limit": 1},
                        "pk": {"type": "fixed_window", "per_key": True}}}
    reg = Registry.from_config(cfg, clock=clock)
    assert reg.check("tb") == Decision(True, 4, 0.0)
    assert reg.check("fw") == Decision(True, 0, 0.0)
    assert reg.check("fw") == Decision(False, 0, 4.0)
    reg.check("pk", "a")
    reg.check("pk", "a")
    assert reg.check("pk", "a").allowed is False
    reg.check("pk", "b")
    assert reg.check("pk", "a") == Decision(True, 1, 0.0)
