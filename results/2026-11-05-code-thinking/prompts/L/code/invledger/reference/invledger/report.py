from decimal import ROUND_HALF_UP, Decimal


def _fmt(x, places):
    q = x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    if q == 0:
        q = abs(q)
    return format(q, f",.{places}f")


def valuation_report(ledger):
    lines = [f"{'SKU':<12}{'QTY':>8}{'VALUE':>14}{'AVG COST':>12}"]
    total_qty, total_value = 0, Decimal(0)
    for sku in ledger.skus():
        qty, value = ledger.on_hand(sku), ledger.value(sku)
        total_qty += qty
        total_value += value
        avg = "-" if qty == 0 else _fmt(value / qty, 4)
        lines.append(f"{sku:<12}{qty:>8}{_fmt(value, 2):>14}{avg:>12}")
    lines.append(f"{'TOTAL':<12}{total_qty:>8}{_fmt(total_value, 2):>14}")
    return "".join(line + "\n" for line in lines)
