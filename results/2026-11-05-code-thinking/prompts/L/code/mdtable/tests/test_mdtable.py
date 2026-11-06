import pytest

from mdtable import Table, TableError, display_width, format_table, from_csv, parse, split_row, to_csv


# ---- width ----

def test_display_width_rules():
    assert display_width("abc") == 3
    assert display_width("") == 0
    assert display_width("日本語") == 6
    assert display_width("Ａｂ") == 4          # fullwidth (F)
    assert display_width("ｱ") == 1             # halfwidth katakana (H)
    assert display_width("±é") == 2            # ambiguous and neutral count 1
    assert display_width("é") == 1       # combining mark counts 0
    assert display_width("😀x") == 3


# ---- split_row ----

def test_split_row_outer_pipes_optional_and_stripped():
    assert split_row("| a |  b c |") == ["a", "b c"]
    assert split_row("a | b") == ["a", "b"]
    assert split_row("  |a|b  ") == ["a", "b"]
    assert split_row("| a | |") == ["a", ""]
    assert split_row("a|") == ["a"]
    assert split_row("|") == [""]
    assert split_row("||") == [""]


def test_split_row_escaped_pipes_and_other_backslashes():
    assert split_row(r"| a \| b | c |") == ["a | b", "c"]
    assert split_row(r"| x \\| y |") == [r"x \| y"]
    assert split_row(r"| a\nb | \t |") == [r"a\nb", r"\t"]
    assert split_row(r"| a | b \|") == ["a", "b |"]


def test_split_row_code_spans():
    assert split_row("| `x|y` | z |") == ["`x|y`", "z"]
    assert split_row("| ``a`|b`` | `c | d |") == ["``a`|b``", "`c", "d"]
    assert split_row(r"| `a\|b` |") == ["`a|b`"]
    assert split_row("| `a``b|c` |") == ["`a``b|c`"]


# ---- parse ----

DOC = """
| Name | Qty | Note |
|:-----|----:|:----:|
| apple | 3 | `a|b` |
| kiwi | 12 |
| fig | 1 | x | extra |
"""


def test_parse_basic_aligns_and_ragged_rows():
    t = parse(DOC)
    assert t.headers == ["Name", "Qty", "Note"]
    assert t.aligns == ["left", "right", "center"]
    assert t.rows == [["apple", "3", "`a|b`"], ["kiwi", "12", ""], ["fig", "1", "x"]]


def test_parse_default_alignment_and_single_dash():
    t = parse("a | b\n- | ---\n1 | 2\r\n")
    assert t.aligns == [None, None]
    assert t.rows == [["1", "2"]]
    assert parse("| h |\n| --- |\n").rows == []


def test_parse_error_empty_and_missing_delimiter():
    with pytest.raises(TableError) as ei:
        parse("  \n\n")
    assert ei.value.line == 1
    with pytest.raises(TableError) as ei:
        parse("\n\n| a | b |\n")
    assert ei.value.line == 4


def test_parse_error_bad_delimiter_cell():
    for bad in ("| :--x | --- |", "| : | --- |", "| --- |  |", "| -- - | --- |"):
        with pytest.raises(TableError) as ei:
            parse("\n| a | b |\n" + bad + "\n| 1 | 2 |\n")
        assert ei.value.line == 3, bad


def test_parse_error_delimiter_count_and_duplicates():
    with pytest.raises(TableError) as ei:
        parse("| a | b | c |\n| --- | --- |\n")
    assert ei.value.line == 2
    with pytest.raises(TableError) as ei:
        parse("\n| a | a |\n| --- | --- |\n")
    assert ei.value.line == 2


def test_parse_error_blank_line_inside():
    with pytest.raises(TableError) as ei:
        parse("| a |\n| - |\n| 1 |\n   \n| 2 |\n\n")
    assert ei.value.line == 4
    assert "4" in str(ei.value)


# ---- Table ----

def test_table_validation_and_copies():
    with pytest.raises(ValueError):
        Table(["a", "b"], [["1"]])
    with pytest.raises(ValueError):
        Table(["a", "a"], [])
    with pytest.raises(ValueError):
        Table(["a"], [], ["middle"])
    with pytest.raises(ValueError):
        Table(["a"], [], [None, None])
    rows = [["1"]]
    t = Table(["a"], rows)
    rows[0][0] = "changed"
    assert t.rows == [["1"]] and t.aligns == [None]
    assert t == Table(["a"], [["1"]], [None])
    assert t != Table(["a"], [["1"]], ["left"])


def test_column_records_and_unknown():
    t = parse(DOC)
    assert t.column("Qty") == ["3", "12", "1"]
    assert t.records()[1] == {"Name": "kiwi", "Qty": "12", "Note": ""}
    with pytest.raises(KeyError):
        t.column("Price")


def test_select():
    t = parse(DOC)
    s = t.select(["Note", "Name"])
    assert s.headers == ["Note", "Name"] and s.aligns == ["center", "left"]
    assert s.rows[0] == ["`a|b`", "apple"]
    assert t.headers == ["Name", "Qty", "Note"]
    with pytest.raises(KeyError):
        t.select(["Name", "Nope"])
    with pytest.raises(ValueError):
        t.select(["Name", "Name"])


def test_filter():
    t = parse(DOC)
    f = t.filter(lambda r: r["Note"] != "")
    assert f.column("Name") == ["apple", "fig"]
    assert f.aligns == t.aligns and len(t.rows) == 3


def test_sort_numbers_text_empty():
    cells = ["10", "9", "apple", "Banana", "", "-2.5", "1e1", "banana", "nan", "1_000", ".5", "5."]
    t = Table(["v", "i"], [[c, str(i)] for i, c in enumerate(cells)])
    asc = t.sort("v").column("v")
    assert asc == ["-2.5", ".5", "5.", "9", "10", "1e1", "1_000", "apple", "Banana", "banana", "nan", ""]
    desc = t.sort("v", descending=True).column("v")
    assert desc == ["nan", "banana", "Banana", "apple", "1_000", "10", "1e1", "9", "5.", ".5", "-2.5", ""]
    assert t.column("v") == cells


def test_sort_multiple_keys_is_stable():
    t = Table(["team", "pts", "who"], [["b", "3", "p"], ["a", "10", "q"], ["b", "", "r"], ["a", "2", "s"],
                                       ["b", "3", "t"], ["", "1", "u"]])
    assert t.sort(["team", "pts"]).column("who") == ["s", "q", "p", "t", "r", "u"]
    assert t.sort(["team", "pts"], descending=True).column("who") == ["p", "t", "r", "q", "s", "u"]
    with pytest.raises(KeyError):
        t.sort(["team", "nope"])


# ---- format ----

def test_format_alignment_and_min_width():
    t = parse(DOC)
    assert format_table(t) == (
        "| Name  | Qty | Note  |\n"
        "| :---- | --: | :---: |\n"
        "| apple |   3 | `a|b` |\n"
        "| kiwi  |  12 |       |\n"
        "| fig   |   1 |   x   |\n")


def test_format_default_alignment_and_empty_body():
    t = Table(["a", "bb"], [], [None, "left"])
    assert format_table(t) == "| a   | bb  |\n| --- | :-- |\n"


def test_format_east_asian_width():
    t = Table(["名前", "n"], [["日本", "1"], ["abcde", "22"]], ["center", "right"])
    assert format_table(t) == (
        "| 名前  |   n |\n"
        "| :---: | --: |\n"
        "| 日本  |   1 |\n"
        "| abcde |  22 |\n")


def test_format_escapes_pipes_outside_code_spans():
    t = Table(["a|b", "c"], [["x|y", "`p|q`"], ["`open|", "ok"]])
    assert format_table(t) == (
        "| a\\|b    | c     |\n"
        "| ------- | ----- |\n"
        "| x\\|y    | `p|q` |\n"
        "| `open\\| | ok    |\n")


def test_round_trip():
    t = Table(["k", "名", "code"], [["a|b", "日本", "`x|y`"], ["", "z", "1"]], ["right", None, "center"])
    assert parse(format_table(t)) == t


# ---- CSV ----

def test_to_csv():
    t = Table(["a", "b"], [["1,5", 'say "hi"'], ["x|y", ""]])
    assert to_csv(t) == 'a,b\n"1,5","say ""hi"""\nx|y,\n'
    assert to_csv(Table(["h"], [])) == "h\n"


def test_from_csv():
    t = from_csv('a,b,c\n1,2\n\n3,4,5,6\n"x,y",,"q"\n')
    assert t.headers == ["a", "b", "c"] and t.aligns == [None, None, None]
    assert t.rows == [["1", "2", ""], ["3", "4", "5"], ["x,y", "", "q"]]
    assert from_csv(to_csv(parse(DOC))).rows == parse(DOC).rows


def test_from_csv_errors():
    with pytest.raises(TableError):
        from_csv("\n\n")
    with pytest.raises(TableError):
        from_csv("a,a\n1,2\n")
