import json

from .errors import LedgerError
from .ledger import Ledger


def save(ledger, path):
    doc = {
        "version": 1,
        "allow_negative": ledger.allow_negative,
        "movements": [{"kind": m.kind, "sku": m.sku, "qty": m.qty,
                       "unit_cost": None if m.unit_cost is None else str(m.unit_cost), "ref": m.ref}
                      for m in ledger.movements()],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def load(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("version") != 1:
        raise LedgerError("unsupported version")
    led = Ledger(allow_negative=doc.get("allow_negative", False))
    for m in doc.get("movements", []):
        kind = m.get("kind")
        if kind == "receipt":
            led.receive(m["sku"], m["qty"], m["unit_cost"], m.get("ref"))
        elif kind == "issue":
            led.issue(m["sku"], -m["qty"], m.get("ref"))
        elif kind == "adjust":
            led.adjust(m["sku"], m["qty"], m["unit_cost"] if m["qty"] > 0 else None, m.get("ref"))
        else:
            raise LedgerError(f"unknown movement kind {kind!r}")
    return led
