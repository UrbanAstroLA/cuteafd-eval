import json
from decimal import Decimal

import pytest

from invledger import (InsufficientStock, Ledger, LedgerError, Movement, UnknownSKU, load, save,
                       valuation_report)


def test_receive_creates_layers_and_movement():
    L = Ledger()
    m = L.receive("WID-1", 10, "2.50", ref="PO-1")
    assert m == Movement(1, "receipt", "WID-1", 10, Decimal("2.50"), Decimal("25.00"), "PO-1")
    L.receive("WID-1", 5, 3)
    L.receive("WID-1", 5, 3)
    assert L.layers("WID-1") == [(10, Decimal("2.50")), (5, Decimal(3)), (5, Decimal(3))]
    assert L.on_hand("WID-1") == 20
    assert L.value("WID-1") == Decimal("55.00")
    assert L.last_cost("WID-1") == Decimal(3)
    assert L.variance("WID-1") == 0 and L.backorders("WID-1") == []
    assert str(L.layers("WID-1")[0][1]) == "2.50"


def test_issue_fifo_across_layers():
    L = Ledger()
    L.receive("A", 4, "1.00")
    L.receive("A", 6, "2.00")
    L.receive("A", 5, Decimal("3.10"))
    m = L.issue("A", 7, ref="SO-9")
    assert (m.seq, m.kind, m.qty, m.unit_cost, m.amount, m.ref) == (4, "issue", -7, None, Decimal("-10.00"), "SO-9")
    assert L.layers("A") == [(3, Decimal("2.00")), (5, Decimal("3.10"))]
    m = L.issue("A", 8)
    assert m.amount == Decimal("-21.50")
    assert L.layers("A") == [] and L.on_hand("A") == 0 and L.value("A") == 0


def test_insufficient_stock_changes_nothing():
    L = Ledger()
    L.receive("A", 5, 1)
    with pytest.raises(InsufficientStock) as ei:
        L.issue("A", 6)
    assert (ei.value.sku, ei.value.requested, ei.value.available) == ("A", 6, 5)
    assert isinstance(ei.value, LedgerError)
    assert L.on_hand("A") == 5 and len(L.movements()) == 1
    assert L.receive("A", 1, 1).seq == 2


def test_unknown_sku():
    L = Ledger()
    L.receive("A", 1, 1)
    for call in (lambda: L.issue("B", 1), lambda: L.adjust("B", 1, 1), lambda: L.on_hand("B"),
                 lambda: L.value("B"), lambda: L.layers("B"), lambda: L.variance("B"),
                 lambda: L.movements("B"), lambda: L.issue("bad sku", 1)):
        with pytest.raises(UnknownSKU) as ei:
            call()
        assert isinstance(ei.value, LedgerError)
    assert ei.value.sku == "bad sku"


def test_quantity_and_sku_validation():
    L = Ledger()
    for sku in ["", "abc", "A B", "X" * 33, 12]:
        with pytest.raises(ValueError):
            L.receive(sku, 1, 1)
    assert L.receive("X" * 32, 1, 1).sku == "X" * 32
    L.receive("A", 5, 1)
    for bad in (True, 1.0, "2"):
        with pytest.raises(TypeError):
            L.receive("A", bad, 1)
        with pytest.raises(TypeError):
            L.issue("A", bad)
    for bad in (0, -3):
        with pytest.raises(ValueError):
            L.receive("A", bad, 1)
        with pytest.raises(ValueError):
            L.issue("A", bad)
    assert L.skus() == ["A", "X" * 32] and len(L.movements()) == 2


def test_cost_validation():
    L = Ledger()
    for bad in (1.5, True, None, [1]):
        with pytest.raises(TypeError):
            L.receive("A", 1, bad)
    for bad in ("abc", "NaN", "Infinity", "-1", Decimal("-0.01"), -2, ""):
        with pytest.raises(ValueError):
            L.receive("A", 1, bad)
    assert L.skus() == []
    assert L.receive("A", 3, 0).amount == 0


def test_negative_stock_creates_backorder_at_last_cost():
    L = Ledger(allow_negative=True)
    L.receive("A", 2, "1.00")
    L.receive("A", 2, "3.00")
    m = L.issue("A", 10)
    assert m.amount == Decimal("-26.00")
    assert L.layers("A") == [] and L.backorders("A") == [(6, Decimal("3.00"))]
    assert L.on_hand("A") == -6 and L.value("A") == Decimal("-18.00")
    L.issue("A", 1)
    assert L.backorders("A") == [(6, Decimal("3.00")), (1, Decimal("3.00"))]


def test_receipt_covers_backorders_with_variance():
    L = Ledger(allow_negative=True)
    L.receive("A", 1, "2.00")
    L.issue("A", 4)                      # backorder 3 @ 2.00
    L.receive("A", 1, "5.00")            # covers 1 -> variance +3
    assert L.backorders("A") == [(2, Decimal("2.00"))] and L.layers("A") == []
    L.issue("A", 2)                      # backorder 2 @ 5.00 (new last cost)
    assert L.backorders("A") == [(2, Decimal("2.00")), (2, Decimal("5.00"))]
    L.receive("A", 7, "4.00")            # covers 2 @2 (+4) and 2 @5 (-2), 3 left
    assert L.backorders("A") == []
    assert L.layers("A") == [(3, Decimal("4.00"))]
    assert L.variance("A") == Decimal("5.00")
    assert L.on_hand("A") == 3 and L.value("A") == Decimal("12.00")


def test_value_invariant():
    L = Ledger(allow_negative=True)
    L.receive("A", 3, "1.10")
    L.issue("A", 5)
    L.adjust("A", 1, "0.90")
    L.receive("A", 4, "1.25")
    L.issue("A", 1)
    L.adjust("A", -1)
    L.receive("B", 2, "7")
    for sku in L.skus():
        assert L.value(sku) == sum(m.amount for m in L.movements(sku)) - L.variance(sku)
    assert L.value("A") == Decimal("1.25") and L.on_hand("A") == 1


def test_adjust_positive():
    L = Ledger()
    L.receive("A", 2, "4.00")
    m = L.adjust("A", 3, ref="count")
    assert (m.kind, m.qty, m.unit_cost, m.amount, m.ref) == ("adjust", 3, Decimal("4.00"), Decimal("12.00"), "count")
    L.adjust("A", 1, "6")
    assert L.layers("A") == [(2, Decimal("4.00")), (3, Decimal("4.00")), (1, Decimal(6))]
    assert L.last_cost("A") == Decimal(6)


def test_adjust_negative_rules():
    L = Ledger(allow_negative=True)
    L.receive("A", 3, "1.00")
    L.receive("A", 3, "2.00")
    m = L.adjust("A", -4)
    assert (m.kind, m.qty, m.unit_cost, m.amount) == ("adjust", -4, None, Decimal("-5.00"))
    with pytest.raises(InsufficientStock) as ei:
        L.adjust("A", -3)
    assert ei.value.available == 2 and ei.value.requested == 3
    with pytest.raises(ValueError):
        L.adjust("A", -1, "1.00")
    with pytest.raises(ValueError):
        L.adjust("A", 0)
    with pytest.raises(TypeError):
        L.adjust("A", 1.0)
    assert L.layers("A") == [(2, Decimal("2.00"))] and len(L.movements()) == 3


def test_adjust_positive_covers_backorder():
    L = Ledger(allow_negative=True)
    L.receive("A", 1, "3.00")
    L.issue("A", 3)
    L.adjust("A", 1)
    assert L.backorders("A") == [(1, Decimal("3.00"))] and L.variance("A") == 0
    L.adjust("A", 2, "1.00")
    assert L.backorders("A") == [] and L.layers("A") == [(1, Decimal("1.00"))]
    assert L.variance("A") == Decimal("-2.00")


def test_movements_filter_and_skus_sorted():
    L = Ledger()
    L.receive("Z", 1, 1)
    L.receive("B-2", 1, 1)
    L.issue("Z", 1)
    L.receive("B-10", 1, 1)
    assert L.skus() == ["B-10", "B-2", "Z"]
    assert [m.seq for m in L.movements("Z")] == [1, 3]
    assert [m.seq for m in L.movements()] == [1, 2, 3, 4]


def test_report_format():
    L = Ledger()
    L.receive("WID-1", 10, "2.50")
    L.receive("WID-1", 5, 3)
    L.receive("BOLT", 1000, "1.2345")
    L.issue("WID-1", 12)
    L.receive("NUT", 3, "0.40")
    L.issue("NUT", 3)
    assert valuation_report(L) == (
        "SKU              QTY         VALUE    AVG COST\n"
        "BOLT            1000      1,234.50      1.2345\n"
        "NUT                0          0.00           -\n"
        "WID-1              3          9.00      3.0000\n"
        "TOTAL           1003      1,243.50\n")


def test_report_half_up_rounding():
    L = Ledger()
    L.receive("A", 1, "2.345")
    L.receive("B", 2, "1.00005")
    L.receive("C", 3, "0.125")
    lines = valuation_report(L).splitlines()
    assert lines[1] == "A                  1          2.35      2.3450"
    assert lines[2] == "B                  2          2.00      1.0001"
    assert lines[3] == "C                  3          0.38      0.1250"
    assert lines[4] == "TOTAL              6          4.72"


def test_report_total_rounds_exact_sum():
    L = Ledger()
    for sku in ("A", "B", "C"):
        L.receive(sku, 1, "0.004")
    lines = valuation_report(L).splitlines()
    assert [ln.split()[2] for ln in lines[1:4]] == ["0.00", "0.00", "0.00"]
    assert lines[4] == "TOTAL              3          0.01"


def test_report_negative_values_and_negative_zero():
    L = Ledger(allow_negative=True)
    L.receive("NEG", 1, "1500")
    L.issue("NEG", 3)
    L.receive("TINY", 1, "0.004")
    L.issue("TINY", 2)
    out = valuation_report(L)
    assert "NEG               -2     -3,000.00  1,500.0000\n" in out
    assert "TINY              -1          0.00      0.0040\n" in out
    assert out.endswith("TOTAL             -3     -3,000.00\n")


def test_report_empty_ledger():
    assert valuation_report(Ledger()) == (
        "SKU              QTY         VALUE    AVG COST\n"
        "TOTAL              0          0.00\n")


def _sample(path):
    L = Ledger(allow_negative=True)
    L.receive("A", 5, "2.50", ref="PO-1")
    L.issue("A", 7)
    L.receive("A", 4, "3.00")
    L.adjust("A", 2)
    L.adjust("A", -1, ref="damaged")
    L.receive("B", 1, 10)
    save(L, path)
    return L


def test_save_document_shape(tmp_path):
    p = tmp_path / "ledger.json"
    _sample(p)
    doc = json.loads(p.read_text())
    assert doc["version"] == 1 and doc["allow_negative"] is True
    assert doc["movements"][0] == {"kind": "receipt", "sku": "A", "qty": 5, "unit_cost": "2.50", "ref": "PO-1"}
    assert doc["movements"][1] == {"kind": "issue", "sku": "A", "qty": -7, "unit_cost": None, "ref": None}
    assert doc["movements"][3] == {"kind": "adjust", "sku": "A", "qty": 2, "unit_cost": "3.00", "ref": None}
    assert doc["movements"][4]["unit_cost"] is None and doc["movements"][4]["qty"] == -1
    assert doc["movements"][5]["unit_cost"] == "10"


def test_save_load_round_trip(tmp_path):
    p = tmp_path / "ledger.json"
    L = _sample(str(p))
    M = load(p)
    assert M.allow_negative is True
    assert M.movements() == L.movements()
    for sku in L.skus():
        assert M.layers(sku) == L.layers(sku)
        assert M.backorders(sku) == L.backorders(sku)
        assert M.variance(sku) == L.variance(sku)
        assert M.last_cost(sku) == L.last_cost(sku)
    assert valuation_report(M) == valuation_report(L)


def test_load_errors(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"version": 2, "allow_negative": False, "movements": []}))
    with pytest.raises(LedgerError):
        load(p)
    p.write_text(json.dumps({"version": 1, "allow_negative": False, "movements": [
        {"kind": "receipt", "sku": "A", "qty": 1, "unit_cost": "1", "ref": None},
        {"kind": "transfer", "sku": "A", "qty": -1, "unit_cost": None, "ref": None}]}))
    with pytest.raises(LedgerError):
        load(p)
    p.write_text(json.dumps({"version": 1, "allow_negative": False, "movements": [
        {"kind": "receipt", "sku": "A", "qty": 1, "unit_cost": "1", "ref": None},
        {"kind": "issue", "sku": "A", "qty": -2, "unit_cost": None, "ref": None}]}))
    with pytest.raises(InsufficientStock):
        load(p)
