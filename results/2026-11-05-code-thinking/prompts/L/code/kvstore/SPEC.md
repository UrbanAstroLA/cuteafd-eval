Build a Python package named `kvstore`: an in-memory key-value store with expiring keys, nested transactions, JSON persistence and a line-oriented command interpreter. Python 3.12, standard library only.

## Files

- `kvstore/__init__.py` — re-exports `Store`, `Interpreter`, `dump`, `load`, `KVError`, `TransactionError`.
- `kvstore/errors.py` — `KVError(Exception)` and `TransactionError(KVError)`.
- `kvstore/store.py` — `Store`.
- `kvstore/persistence.py` — `dump` and `load`.
- `kvstore/commands.py` — `Interpreter`.

## store.py

`Store(clock=time.monotonic)`. `clock` is a zero-argument callable returning the current time in seconds (a float). Every time-dependent decision calls `clock()`; tests pass a fake clock.

Keys and values are strings. A key with an expiry time `t` is live while `clock() < t` and behaves exactly as if absent once `clock() >= t`.

Methods:

- `set(key, value, ttl=None)` — store `value`. `ttl` is a number of seconds; the expiry time is `clock() + ttl`. `ttl=None` means no expiry. A `ttl` that is not greater than 0 raises `ValueError`. Setting a key replaces both its value and its expiry.
- `get(key)` — the value of a live key, or `None`.
- `delete(key)` — remove the key; return `True` if a live key was removed, else `False`.
- `count(value)` — the number of live keys whose value equals `value`.
- `keys(prefix="")` — sorted list of live keys starting with `prefix`.
- `ttl(key)` — remaining seconds (`expiry - clock()`) for a live key with an expiry, `None` for a live key without one, and `-1` for a missing or expired key.
- `begin()` — open a transaction. Transactions nest without limit.
- `rollback()` — discard every change (sets, deletes, expiries) made since the innermost open `begin()` and close that transaction. Raises `TransactionError` if no transaction is open.
- `commit()` — make all changes permanent and close **all** open transactions. Raises `TransactionError` if no transaction is open.
- `depth` — read-only property, the number of open transactions.
- `snapshot()` — a new dict `{key: {"value": str, "expires_at": float | None}}` of every live key as currently visible (including uncommitted changes).

Reads inside a transaction see that transaction's own writes. `rollback()` restores a key's previous value and its previous expiry time exactly.

## persistence.py

- `dump(store, path)` — write `{"version": 1, "items": store.snapshot()}` as JSON to `path` (a `str` or `pathlib.Path`). Raises `TransactionError` if the store has an open transaction (nothing is written).
- `load(path, clock=time.monotonic)` — return a new `Store(clock)` containing the file's items, skipping items whose `expires_at` is not `None` and is `<= clock()`. Expiry times are kept as absolute values. A file whose `version` is not `1` raises `KVError`.

## commands.py

`Interpreter(store=None)` wraps a `Store` (a new `Store()` if `None`); the wrapped store is available as attribute `store`. `execute(line: str) -> str` runs one command and returns its reply. The line is split on whitespace; the command word is case-insensitive; keys and values are case-sensitive and cannot contain spaces. A blank line returns `""`.

| Command | Reply |
|---|---|
| `SET key value` | `OK` |
| `SET key value EX seconds` | `OK`; seconds is a positive number (int or float text) |
| `GET key` | the value, or `NULL` |
| `DEL key` | `1` if removed, else `0` |
| `COUNT value` | the count as decimal text |
| `KEYS` / `KEYS prefix` | the matching keys joined by single spaces, or `(empty)` |
| `TTL key` | `-1` for missing; `none` for no expiry; otherwise the remaining seconds formatted with `format(x, ".3f")` |
| `BEGIN` | `OK` |
| `ROLLBACK` | `OK`, or `ERR no transaction` |
| `COMMIT` | `OK`, or `ERR no transaction` |

Any other command word, a wrong number of arguments, `EX` misspelled, or a seconds value that is not a positive number returns a reply starting with `ERR ` (and changes nothing). `execute` never raises for bad input.
