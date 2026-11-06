import datetime

import pytest

from csvreport import (Column, ReportError, RowError, Schema, SchemaError, group_by, read_rows, render_table)
from csvreport.schema import parse_value

SCHEMA = Schema([Column("region", "str"), Column("units", "int"), Column("price", "float", required=False),
                 Column("paid", "bool", required=False), Column("day", "date", required=False)])

CSV = """region, units ,price,paid,day,ignored
north,3,2.50,yes,2026-01-05,x
south,5,,no,2026-01-06,y
north,2,4.00,TRUE,,z

,,,,,
south,1,1.25,0,2026-01-07,w
"""


def test_column_validation():
    with pytest.raises(ValueError):
        Column("x", "decimal")
    with pytest.raises(ValueError):
        Schema([Column("a", "int"), Column("a", "str")])
    assert SCHEMA.names() == ["region", "units", "price", "paid", "day"]
    c = Column("a", "int")
    with pytest.raises(Exception):
        c.name = "b"


@pytest.mark.parametrize("typ,text,expected", [
    ("int", " +3 ", 3), ("int", "-0", 0), ("float", "1e3", 1000.0), ("str", "  hi there ", "hi there"),
    ("bool", "Yes", True), ("bool", "0", False), ("bool", "FALSE", False),
    ("date", "2024-02-29", datetime.date(2024, 2, 29)),
])
def test_parse_value_ok(typ, text, expected):
    v = parse_value(Column("c", typ), text)
    assert v == expected and type(v) is type(expected)


@pytest.mark.parametrize("typ,text", [
    ("int", "3.0"), ("int", "abc"), ("float", "nan"), ("float", "-Infinity"), ("bool", "maybe"),
    ("date", "2023-02-29"), ("date", "2024-2-9"), ("date", "20240101"), ("int", "   "),
])
def test_parse_value_invalid(typ, text):
    with pytest.raises(ValueError):
        parse_value(Column("c", typ), text)


def test_parse_value_optional_empty():
    assert parse_value(Column("c", "int", required=False), "  ") is None


def test_read_rows():
    rows = read_rows(CSV, SCHEMA)
    assert len(rows) == 4
    assert rows[0] == {"region": "north", "units": 3, "price": 2.5, "paid": True,
                       "day": datetime.date(2026, 1, 5)}
    assert rows[1]["price"] is None and rows[1]["paid"] is False
    assert rows[2]["day"] is None
    assert list(rows[0]) == SCHEMA.names()


def test_read_rows_column_order_independent():
    text = "units,region\n4,east\n"
    rows = read_rows(text, Schema([Column("region", "str"), Column("units", "int")]))
    assert rows == [{"region": "east", "units": 4}]


def test_read_rows_short_record_padded():
    rows = read_rows("region,units,price\nwest,7\n", Schema([Column("region", "str"), Column("units", "int"),
                                                             Column("price", "float", required=False)]))
    assert rows == [{"region": "west", "units": 7, "price": None}]


def test_read_rows_missing_columns():
    with pytest.raises(SchemaError) as ei:
        read_rows("units,foo,day,paid\n1,2,,\n", SCHEMA)
    assert ei.value.missing == ["price", "region"]
    with pytest.raises(SchemaError) as ei:
        read_rows("foo\n", SCHEMA)
    assert ei.value.missing == ["day", "paid", "price", "region", "units"]
    assert isinstance(ei.value, ReportError)


def test_read_rows_row_error_line_and_column():
    text = "region,units\nnorth,1\n\nsouth,x\n"
    with pytest.raises(RowError) as ei:
        read_rows(text, Schema([Column("region", "str"), Column("units", "int")]))
    assert ei.value.line == 4 and ei.value.column == "units"
    assert "4" in str(ei.value) and "units" in str(ei.value)


def test_read_rows_required_missing_is_row_error():
    with pytest.raises(RowError) as ei:
        read_rows("region,units\n ,3\n", Schema([Column("region", "str"), Column("units", "int")]))
    assert ei.value.line == 2 and ei.value.column == "region"


def test_read_rows_quoted_multiline_line_num():
    text = 'region,units\n"multi\nline",1\nok,zz\n'
    with pytest.raises(RowError) as ei:
        read_rows(text, Schema([Column("region", "str"), Column("units", "int")]))
    assert ei.value.line == 4


def test_group_by_basic():
    rows = read_rows(CSV, SCHEMA)
    out = group_by(rows, ["region"], {"n": ("count", None), "units": ("sum", "units"),
                                      "avg_price": ("mean", "price"), "priced": ("count", "price"),
                                      "max_units": ("max", "units"), "first_day": ("min", "day")})
    assert out == [
        {"region": "north", "n": 2, "units": 5, "avg_price": 3.25, "priced": 2, "max_units": 3,
         "first_day": datetime.date(2026, 1, 5)},
        {"region": "south", "n": 2, "units": 6, "avg_price": 1.25, "priced": 1, "max_units": 5,
         "first_day": datetime.date(2026, 1, 6)},
    ]
    assert list(out[0]) == ["region", "n", "units", "avg_price", "priced", "max_units", "first_day"]
    assert type(out[0]["units"]) is int and type(out[0]["avg_price"]) is float


def test_group_by_none_sorts_first_and_multi_key():
    rows = [{"a": "x", "b": 2, "v": 1}, {"a": None, "b": 1, "v": 2}, {"a": "x", "b": None, "v": 3},
            {"a": "x", "b": 2, "v": 4}]
    out = group_by(rows, ["a", "b"], {"s": ("sum", "v")})
    assert out == [{"a": None, "b": 1, "s": 2}, {"a": "x", "b": None, "s": 3}, {"a": "x", "b": 2, "s": 5}]


def test_group_by_all_none_and_empty_keys():
    rows = [{"k": "a", "v": None}, {"k": "a", "v": None}]
    assert group_by(rows, ["k"], {"m": ("mean", "v"), "s": ("sum", "v"), "c": ("count", "v")}) == \
        [{"k": "a", "m": None, "s": None, "c": 0}]
    assert group_by([], [], {"n": ("count", None), "s": ("sum", "v")}) == [{"n": 0, "s": None}]
    assert group_by([{"v": 2}, {"v": 4}], [], {"m": ("mean", "v")}) == [{"m": 3.0}]


def test_group_by_unknown_function():
    with pytest.raises(ValueError):
        group_by([], ["a"], {"x": ("median", "v")})


def test_render_table_alignment_and_format():
    rows = [{"name": "apple", "qty": 3, "price": 1.5, "ok": True},
            {"name": "kiwi", "qty": 12, "price": None, "ok": False}]
    out = render_table(rows, ["name", "qty", "price", "ok"])
    assert out == ("name  | qty | price | ok\n"
                   "------+-----+-------+------\n"
                   "apple |   3 |  1.50 | true\n"
                   "kiwi  |  12 |       | false")


def test_render_table_digits_dates_missing_keys():
    rows = [{"d": datetime.date(2026, 3, 1), "x": 2.0}, {"x": 10.125}]
    out = render_table(rows, ["d", "x"], float_digits=1)
    assert out == ("d          |    x\n"
                   "-----------+-----\n"
                   "2026-03-01 |  2.0\n"
                   "           | 10.1")


def test_render_table_empty_rows_and_all_none_column():
    assert render_table([], ["alpha", "b"]) == "alpha | b\n------+--"
    out = render_table([{"n": None}, {"n": None}], ["n", "m"])
    assert out.split("\n")[0] == "n | m"


def test_render_bool_column_left_aligned():
    out = render_table([{"flag": True}, {"flag": False}], ["flag"])
    assert out == "flag\n-----\ntrue\nfalse"
