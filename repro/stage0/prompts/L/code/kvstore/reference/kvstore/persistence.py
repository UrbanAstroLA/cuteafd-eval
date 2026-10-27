import json
import time

from .errors import KVError, TransactionError
from .store import Store


def dump(store, path):
    if store.depth:
        raise TransactionError("cannot dump with an open transaction")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "items": store.snapshot()}, f)


def load(path, clock=time.monotonic):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("version") != 1:
        raise KVError("unsupported version")
    s = Store(clock)
    now = clock()
    for k, item in doc["items"].items():
        exp = item["expires_at"]
        if exp is not None and exp <= now:
            continue
        s._data[k] = (item["value"], exp)
    return s
