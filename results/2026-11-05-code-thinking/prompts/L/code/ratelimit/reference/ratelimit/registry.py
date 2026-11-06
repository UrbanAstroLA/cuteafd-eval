import time

from .errors import ConfigError, RateLimited
from .keyed import KeyedLimiter
from .limiters import FixedWindow, SlidingLog, TokenBucket, check_positive, check_size

_TYPES = {
    "token_bucket": (TokenBucket, ("capacity", "refill_rate")),
    "fixed_window": (FixedWindow, ("limit", "window")),
    "sliding_log": (SlidingLog, ("limit", "window")),
}
_SIZE_FIELDS = ("capacity", "limit", "max_keys")
_COMMON = ("per_key", "max_keys")
_ALL_FIELDS = {"capacity", "refill_rate", "limit", "window", "per_key", "max_keys"}


def _used_fields(t):
    return _TYPES[t][1] + _COMMON


def _validate(name, spec):
    if not isinstance(spec, dict):
        raise ConfigError(f"policy {name!r}: spec must be a dict")
    if "type" not in spec:
        raise ConfigError(f"policy {name!r}: missing field 'type'")
    t = spec["type"]
    if not isinstance(t, str) or t not in _TYPES:
        raise ConfigError(f"policy {name!r}: unknown value {t!r} for field 'type'")
    used = _used_fields(t)
    for f in spec:
        if f != "type" and f not in used:
            raise ConfigError(f"policy {name!r}: field {f!r} is not used by type {t!r}")
    for f in _TYPES[t][1]:
        if f not in spec:
            raise ConfigError(f"policy {name!r}: missing field {f!r}")
    for f in used:
        if f not in spec:
            continue
        v = spec[f]
        try:
            if f == "per_key":
                if not isinstance(v, bool):
                    raise ValueError("must be a bool")
            elif f in _SIZE_FIELDS:
                check_size(f, v)
            else:
                check_positive(f, v)
        except ValueError as e:
            raise ConfigError(f"policy {name!r}: field {f!r}: {e}") from None
    per_key = spec.get("per_key", False)
    if "max_keys" in spec and not per_key:
        raise ConfigError(f"policy {name!r}: field 'max_keys' requires per_key")
    return t, per_key


class _Policy:
    def __init__(self, limiter, per_key):
        self.limiter = limiter
        self.per_key = per_key


class Registry:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._policies = {}

    def add(self, name, spec):
        if not isinstance(name, str) or not name:
            raise ConfigError(f"invalid policy name {name!r}")
        if name in self._policies:
            raise ConfigError(f"policy {name!r} already exists")
        t, per_key = _validate(name, spec)
        cls, req = _TYPES[t]
        args = tuple(spec[f] for f in req)
        clock = self._clock
        if per_key:
            limiter = KeyedLimiter(lambda: cls(*args, clock=clock), spec.get("max_keys"))
        else:
            limiter = cls(*args, clock=clock)
        self._policies[name] = _Policy(limiter, per_key)

    @classmethod
    def from_config(cls, config, clock=time.monotonic):
        if not isinstance(config, dict):
            raise ConfigError("config must be a dict")
        for k in config:
            if k not in ("policies", "defaults"):
                raise ConfigError(f"unknown top-level key {k!r}")
        policies = config.get("policies")
        if not isinstance(policies, dict):
            raise ConfigError("'policies' must be a dict")
        defaults = config.get("defaults", {})
        if not isinstance(defaults, dict):
            raise ConfigError("'defaults' must be a dict")
        for f in defaults:
            if f not in _ALL_FIELDS:
                raise ConfigError(f"defaults: field {f!r} is not allowed")
        reg = cls(clock)
        for name, spec in policies.items():
            if isinstance(spec, dict) and spec.get("type") in _TYPES:
                used = _used_fields(spec["type"])
                eff = {f: v for f, v in defaults.items() if f in used}
                eff.update(spec)
                if eff.get("per_key") is not True and "max_keys" in eff and "max_keys" not in spec:
                    del eff["max_keys"]
            else:
                eff = spec
            reg.add(name, eff)
        return reg

    def _get(self, name, key):
        if name not in self._policies:
            raise KeyError(name)
        p = self._policies[name]
        if p.per_key and not isinstance(key, str):
            raise ValueError(f"policy {name!r} needs a str key")
        if not p.per_key and key is not None:
            raise ValueError(f"policy {name!r} takes no key")
        return p

    def check(self, name, key=None, cost=1):
        p = self._get(name, key)
        return p.limiter.acquire(key, cost) if p.per_key else p.limiter.acquire(cost)

    def peek(self, name, key=None, cost=1):
        p = self._get(name, key)
        return p.limiter.peek(key, cost) if p.per_key else p.limiter.peek(cost)

    def enforce(self, name, key=None, cost=1):
        d = self.check(name, key, cost)
        if not d.allowed:
            raise RateLimited(name, d.retry_after)
        return None

    def names(self):
        return sorted(self._policies)

    def __contains__(self, name):
        return name in self._policies
