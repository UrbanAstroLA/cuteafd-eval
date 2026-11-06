Build a Python package named `ratelimit`: token-bucket, fixed-window and sliding-log rate limiters with an injectable clock, per-key limiting, and a policy registry configured from a dict. Python 3.12, standard library only.

## Files

- `ratelimit/__init__.py` — re-exports `Decision`, `TokenBucket`, `FixedWindow`, `SlidingLog`, `KeyedLimiter`, `Registry`, `RateLimitError`, `ConfigError`, `RateLimited`.
- `ratelimit/errors.py` — the exception classes.
- `ratelimit/limiters.py` — `Decision` and the three limiters.
- `ratelimit/keyed.py` — `KeyedLimiter`.
- `ratelimit/registry.py` — `Registry`.

## errors.py

- `RateLimitError(Exception)` — base class.
- `ConfigError(RateLimitError)` — bad configuration; the message names the policy and the field or top-level key at fault, when there is one.
- `RateLimited(RateLimitError)` — `RateLimited(policy, retry_after)`; both stored as attributes.

## limiters.py

`Decision` is a frozen dataclass with fields `allowed: bool`, `remaining: int`, `retry_after: float`.

Each limiter's last argument is `clock=time.monotonic`, a zero-argument callable returning seconds. It reads `clock()` at construction and on every `acquire`, `peek`, `reset` and `tokens` access, using `now = max(reading, latest reading so far)`: a clock that steps back stands still.

Sizes (`capacity`, `limit`) must be `int` `>= 1`; `refill_rate` and `window` finite `int`/`float` `> 0`; never `bool`; else `ValueError`.

- `acquire(cost=1) -> Decision` — if `cost` permits are available, consume them (`allowed=True`, `retry_after=0.0`); otherwise consume nothing (`allowed=False`).
- `peek(cost=1)` — what `acquire(cost)` would return now, without consuming.
- `reset()` — back to the initial state, as if constructed now.
- `cost` must be an `int` (not `bool`) from 1 to the limiter's size, else `ValueError`.
- `remaining` is the whole permits available after the call. If denied, `retry_after` is the seconds until the same request would be allowed if nothing else happens.

`TokenBucket(capacity, refill_rate, clock=...)` starts full. On each call, with `last` the previous `now`: `tokens = min(capacity, tokens + (now - last) * refill_rate)`, `last = now`. Allowed when `tokens >= cost`, then `tokens -= cost`. `remaining = math.floor(tokens)`. Denied: `retry_after = (cost - tokens) / refill_rate`. Property `tokens` is the refilled count as a float.

`FixedWindow(limit, window, clock=...)` — the window index is `math.floor(now / window)`; the count resets to 0 when the index changes. Allowed when `count + cost <= limit`, then `count += cost`. `remaining = limit - count`. Denied: `retry_after = (index + 1) * window - now`.

`SlidingLog(limit, window, clock=...)` records the timestamp `now` once per permit acquired. A timestamp `t` is live while `now - t < window`. Allowed when `live + cost <= limit`; `remaining = limit - live`, counting what was just recorded. Denied: with the live timestamps sorted ascending as `ts` and `k = live + cost - limit`, `retry_after = ts[k - 1] + window - now`.

## keyed.py

`KeyedLimiter(factory, max_keys=None)` — `factory()` returns a new limiter; each key gets its own. `max_keys` is `None` or an `int >= 1` (not `bool`), else `ValueError`.

- `acquire(key, cost=1)` — creates the key's limiter if absent, marks the key most recently used (even if denied), delegates. Creating a key while `max_keys` keys are tracked first drops the least recently used one.
- `peek(key, cost=1)` — delegates without changing recency; an untracked key is answered by a fresh `factory()` limiter that is not kept.
- `keys()` — tracked keys, least recently used first. `len(k)` and `key in k` work.
- `reset(key)` — drop the key; return `True` if it was tracked.

## registry.py

`Registry(clock=time.monotonic)` — named policies whose limiters use `clock`.

- `add(name, spec)` — validate and create a policy. `name` must be a non-empty `str` not already present, else `ConfigError`.
- `Registry.from_config(config, clock=time.monotonic)` — classmethod. `config` is `{"policies": {name: spec}, "defaults": {...}}`, `"defaults"` optional. A non-dict config, missing or non-dict `"policies"`, non-dict `"defaults"`, or other top-level key is a `ConfigError`. Policies are added in dict order; `config` is not modified.
- `check(name, key=None, cost=1)` — `acquire` on the policy, returning its `Decision`; `peek(...)` likewise, without consuming.
- `enforce(name, key=None, cost=1)` — `check`; returns `None` if allowed, else raises `RateLimited(name, retry_after)`.
- `names()` — sorted names. `name in registry` works.
- An unknown name raises `KeyError`. A per-key policy needs a `str` key, a global one `key=None`; otherwise `ValueError`. A bad `cost` raises `ValueError`.

A spec is a dict with `type`: `"token_bucket"` requires `capacity` and `refill_rate`; `"fixed_window"` and `"sliding_log"` require `limit` and `window`. Optional: `per_key` (`bool`, default `False`) and `max_keys` (only if `per_key` is true). Values follow the constructor rules. A non-dict spec, missing or unknown `type`, missing required field, unused field or bad value raises `ConfigError` (never `ValueError` or `TypeError`).

In `from_config` a policy's effective spec is the `defaults` fields its type uses, overridden by its own fields. `defaults` may hold any field but `type`; a field no type uses raises `ConfigError`. A `max_keys` coming only from `defaults` is ignored for a policy that is not per-key.
