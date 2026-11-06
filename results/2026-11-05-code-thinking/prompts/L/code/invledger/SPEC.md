Build a Python package named `invledger`: a per-SKU inventory ledger with FIFO cost layers, optional negative stock, a valuation report and JSON persistence. Python 3.12, standard library only.

## Files

- `invledger/__init__.py` — re-exports `Ledger`, `Movement`, `valuation_report`, `save`, `load`, `LedgerError`, `UnknownSKU`, `InsufficientStock`.
- `invledger/errors.py` — the exception classes.
- `invledger/ledger.py` — `Movement` and `Ledger`.
- `invledger/report.py` — `valuation_report`.
- `invledger/storage.py` — `save` and `load`.

## errors.py

- `LedgerError(Exception)` — base class.
- `UnknownSKU(LedgerError)` — attribute `sku`.
- `InsufficientStock(LedgerError)` — `InsufficientStock(sku, requested, available)` with those attributes; `available` is the on-hand quantity at the time.

## ledger.py

Quantities are `int` (a `bool` or any non-`int` raises `TypeError`). Costs are `decimal.Decimal`; a cost argument may be an `int` (not `bool`), a `str` or a `Decimal` and is converted with `Decimal(value)` without rounding. A `float` or other type raises `TypeError`; text that is not a number, NaN, infinities and negative costs raise `ValueError`. All arithmetic is exact `Decimal` arithmetic.

`Movement` is a frozen dataclass: `seq` (1, 2, 3, … across the whole ledger), `kind` (`"receipt"`, `"issue"` or `"adjust"`), `sku`, `qty` (signed: positive in, negative out), `unit_cost` (the cost for an inbound movement, `None` for an outbound one), `amount` (signed `Decimal`: the value added or removed), `ref` (a string or `None`).

`Ledger(allow_negative=False)`; attribute `allow_negative`. Each SKU has a FIFO list of *layers* `(qty, unit_cost)` with positive quantities, a FIFO list of *backorders* `(qty, unit_cost)` with positive quantities (stock issued that the ledger did not have), its *last cost* and its *variance* (`Decimal`, starting at `0`). A SKU never has both layers and backorders. A SKU exists once it has been received; every method other than `receive` raises `UnknownSKU` for any other SKU. Operations that raise change nothing and record no movement.

- `receive(sku, qty, unit_cost, ref=None) -> Movement` — `sku` must be a `str` of 1 to 32 characters from `A-Z`, `0-9` and `-`, else `ValueError`; `qty` must be at least 1 (`ValueError`). Set the last cost to `unit_cost`. Inbound stock first covers backorders, oldest first: covering `c` units of a backorder costed `b` adds `c * (unit_cost - b)` to the variance. Any remaining quantity is appended as a new layer (layers are never merged). Amount: `qty * unit_cost`.
- `issue(sku, qty, ref=None) -> Movement` — `qty` at least 1. If `qty` exceeds the on-hand quantity and negative stock is not allowed, raise `InsufficientStock`. Consume layers oldest first (splitting one if needed); if allowed, any shortfall is appended as a new backorder at the last cost. Amount: minus the cost of the consumed layers and the new backorder.
- `adjust(sku, delta, unit_cost=None, ref=None) -> Movement` — `delta` is a non-zero `int` (`ValueError` for 0). A positive delta is inbound exactly like `receive`, at `unit_cost` or, if that is `None`, at the current last cost. A negative delta takes `-delta` units out of the layers like `issue`, but never creates backorders: if `-delta` exceeds the on-hand quantity, raise `InsufficientStock` even when negative stock is allowed; a `unit_cost` with a negative delta raises `ValueError`. Movement kind `"adjust"`.
- `skus()` — sorted list of SKUs.
- `on_hand(sku) -> int` — layer quantities minus backorder quantities.
- `value(sku) -> Decimal` — sum of `qty * unit_cost` over layers minus the same over backorders.
- `layers(sku)`, `backorders(sku)` — lists of `(qty, unit_cost)` tuples, oldest first.
- `last_cost(sku)`, `variance(sku)` — `Decimal`.
- `movements(sku=None)` — list of movements in `seq` order, optionally only those of one SKU.

For every SKU, `value(sku) == sum(m.amount for m in movements(sku)) - variance(sku)`.

## report.py

`valuation_report(ledger) -> str`. Lines, each followed by `"\n"`:

- header: `f"{'SKU':<12}{'QTY':>8}{'VALUE':>14}{'AVG COST':>12}"`;
- one line per SKU in sorted order: `f"{sku:<12}{qty:>8}{value_text:>14}{avg_text:>12}"`;
- total: `f"{'TOTAL':<12}{total_qty:>8}{total_text:>14}"`.

`value_text` is the value rounded to 2 decimal places with `ROUND_HALF_UP` and formatted with `format(x, ",.2f")`. `avg_text` is `value / qty` rounded to 4 places with `ROUND_HALF_UP` and formatted with `",.4f"`, or `"-"` when `qty` is 0. `total_qty` is the sum of quantities; `total_text` is the exact sum of all values, rounded and formatted like `value_text`. A figure that rounds to zero is shown without a minus sign. Every SKU is listed, including those with zero quantity.

## storage.py

- `save(ledger, path)` — write JSON `{"version": 1, "allow_negative": bool, "movements": [...]}` to `path` (`str` or `pathlib.Path`). Each movement, in `seq` order, is `{"kind", "sku", "qty", "unit_cost", "ref"}` with `qty` signed as in `Movement` and `unit_cost` as `str(unit_cost)` of the Decimal held, or `null` for outbound movements.
- `load(path) -> Ledger` — build a new `Ledger(allow_negative)` and replay the movements in order through `receive`, `issue` and `adjust`. A `version` other than 1, or an unknown `kind`, raises `LedgerError`. Errors raised by the replay propagate unchanged. The loaded ledger equals the saved one in movements, layers, backorders, last costs and variances.
