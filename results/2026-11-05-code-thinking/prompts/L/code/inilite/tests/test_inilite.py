import pytest

from inilite import DuplicateKeyError, IniError, ParseError, dump, dumps, load, loads


def test_basic_document():
    text = """
# top comment
name = "demo"
debug = false

[server]
host = "127.0.0.1"
port = 8080
ratio = 0.75
"""
    assert loads(text) == {"name": "demo", "debug": False,
                           "server": {"host": "127.0.0.1", "port": 8080, "ratio": 0.75}}


def test_whitespace_comments_and_crlf():
    text = "  ; semicolon comment\r\n\t# hash comment\r\n  a=1  \r\n\r\n b\t=\t2 # trailing\r\n[s]  ; c\r\nc = 3;x\r\n"
    assert loads(text) == {"a": 1, "b": 2, "s": {"c": 3}}


def test_ints():
    d = loads("a = 0\nb = -0\nc = +5\nd = -120\ne = 1#c")
    assert d == {"a": 0, "b": 0, "c": 5, "d": -120, "e": 1}
    assert all(type(v) is int for v in d.values())


def test_floats():
    d = loads("a = 1.5\nb = -2.0e3\nc = 1e5\nd = 0.25E-2\ne = +0.0")
    assert d == {"a": 1.5, "b": -2000.0, "c": 100000.0, "d": 0.0025, "e": 0.0}
    assert all(type(v) is float for v in d.values())


@pytest.mark.parametrize("value", ["007", "1.", ".5", "1e", "1e+", "inf", "nan", "1_000", "True", "hello",
                                   "0x10", "--1", "1.5.2", "00.5", "+", "1e5.0"])
def test_invalid_scalars(value):
    with pytest.raises(ParseError) as ei:
        loads(f"ok = 1\nx = {value}\n")
    assert ei.value.line == 2


def test_bools_and_strings():
    d = loads('t = true\nf = false\ns = "say \\"hi\\"\\n\\tback\\\\slash"\nu = "caf\\u00E9 \\u0041"\nh = "a # b ; c"')
    assert d == {"t": True, "f": False, "s": 'say "hi"\n\tback\\slash', "u": "café A", "h": "a # b ; c"}


@pytest.mark.parametrize("line", ['s = "abc', 's = "a\\qb"', 's = "\\u12g4"', 's = "\\u123"', 's = "x" "y"',
                                  's = "x"y', 's = "\\"'])
def test_invalid_strings(line):
    with pytest.raises(ParseError) as ei:
        loads("\n\n" + line)
    assert ei.value.line == 3


def test_lists():
    d = loads('a = []\nb = [ 1 , "x,]y", true, 2.5 ]\nc = [ ]  # empty\nd = ["only"]')
    assert d == {"a": [], "b": [1, "x,]y", True, 2.5], "c": [], "d": ["only"]}


@pytest.mark.parametrize("value", ["[1,]", "[,]", "[1,,2]", "[[1]]", "[1, 2", "[1 2]", "[1] 2", "[1, [2]]",
                                   "[ , 1]", "[1 # c]"])
def test_invalid_lists(value):
    with pytest.raises(ParseError) as ei:
        loads(f"x = {value}")
    assert ei.value.line == 1


def test_dotted_sections_and_reopen():
    text = "[a.b]\nx = 1\n[ a ]\ny = 2\n[a.b.c]\n[a.b]\nz = 3\n[d-1._e]\nk = 0"
    d = loads(text)
    assert d == {"a": {"b": {"x": 1, "c": {}, "z": 3}, "y": 2}, "d-1": {"_e": {"k": 0}}}
    assert list(d["a"]) == ["b", "y"]
    assert list(d["a"]["b"]) == ["x", "c", "z"]


@pytest.mark.parametrize("line", ["[a..b]", "[]", "[a b]", "[a. b]", "[.a]", "[a.]", "[a", "[a] x", "[a]]",
                                  "[a!]", "[ ]"])
def test_invalid_headers(line):
    with pytest.raises(ParseError) as ei:
        loads("a1 = 1\n" + line)
    assert ei.value.line == 2


@pytest.mark.parametrize("line", ["novalue", "k =", "k = # c", "k == 1", "a b = 1", "k: 1", "= 1", "k = 1 2",
                                  "k.x = 1", '"k" = 1'])
def test_invalid_assignments(line):
    with pytest.raises(ParseError) as ei:
        loads("[s]\n" + line)
    assert ei.value.line == 2


def test_duplicate_key():
    with pytest.raises(DuplicateKeyError) as ei:
        loads("[s]\na = 1\nb = 2\n[t]\n[s]\na = 3")
    assert ei.value.line == 6
    assert isinstance(ei.value, ParseError) and isinstance(ei.value, IniError)
    assert "line 6" in str(ei.value)
    assert loads("a = 1\n[s]\na = 2") == {"a": 1, "s": {"a": 2}}


def test_key_section_conflicts():
    with pytest.raises(DuplicateKeyError) as ei:
        loads("a = 1\n[a]")
    assert ei.value.line == 2
    with pytest.raises(DuplicateKeyError) as ei:
        loads("[s]\nb = 1\n\n[s.b.c]")
    assert ei.value.line == 4
    with pytest.raises(DuplicateKeyError) as ei:
        loads("[s.b]\n[s]\nb = 2")
    assert ei.value.line == 3


def test_append_assignment():
    d = loads("[s]\nxs = [1]\nxs += 2\nxs += [3, \"four\"]\nxs+=[]\n[t]\n[s]\nxs += true")
    assert d == {"s": {"xs": [1, 2, 3, "four", True]}, "t": {}}


def test_append_errors_are_not_duplicate_errors():
    for text, line in [("x += 1", 1), ("x = 1\nx += 2", 2), ("[s]\nxs = [1]\n[t]\nxs += 2", 4), ("[a.b]\n[a]\nb += 1", 3)]:
        with pytest.raises(ParseError) as ei:
            loads(text)
        assert not isinstance(ei.value, DuplicateKeyError)
        assert ei.value.line == line


def test_error_message_has_line():
    with pytest.raises(ParseError) as ei:
        loads("a = 1\n\n# c\nb = oops")
    assert ei.value.line == 4
    assert "line 4" in str(ei.value)


def test_dumps_layout():
    data = {"title": "x", "server": {"port": 80, "tls": {"on": True}, "name": "web"},
            "empty": {}, "n": 3}
    assert dumps(data) == ('title = "x"\nn = 3\n\n[server]\nport = 80\nname = "web"\n\n[server.tls]\non = true\n'
                           '\n[empty]\n')


def test_dumps_sections_only_and_empty():
    assert dumps({}) == ""
    assert dumps({"a": {"b": {}}}) == "[a]\n\n[a.b]\n"


def test_dumps_value_formatting():
    data = {"f": [1.0, 1e20, -0.0, 1.5e-07], "b": [True, False, 0, 1], "s": 'q"b\\n\nt\tr\r\x01\x7fé',
            "e": []}
    out = dumps(data)
    assert out == ('f = [1.0, 1e+20, -0.0, 1.5e-07]\nb = [true, false, 0, 1]\n'
                   's = "q\\"b\\\\n\\nt\\tr\\r\\u0001\\u007fé"\ne = []\n')


@pytest.mark.parametrize("data,exc", [
    ({"a": None}, TypeError), ({"a": (1, 2)}, TypeError), ({"a": [[1]]}, TypeError), ({"a": [{}]}, TypeError),
    ({"a": {"b": {1, 2}}}, TypeError), ({"a b": 1}, ValueError), ({"": 1}, ValueError), ({1: 1}, ValueError),
    ({"s": {"x.y": 1}}, ValueError), ({"a": float("nan")}, ValueError), ({"a": [float("-inf")]}, ValueError),
])
def test_dumps_errors(data, exc):
    with pytest.raises(exc):
        dumps(data)


def test_roundtrip():
    data = {"top": -7, "s": "tab\there \"q\" \\ \x00 ☃", "lst": ["a", 1, 2.5, False],
            "a": {"x": 0.1, "b": {"c": {"deep": [1e-300]}}, "y": ""}, "z": {}}
    assert loads(dumps(data)) == data
    text = dumps(data)
    assert dumps(loads(text)) == text


def test_normalization():
    text = "[b]\ny=[1,2]  # c\n[a]\nz = 1E3\n[b]\nx = +1\n"
    assert dumps(loads(text)) == "[b]\ny = [1, 2]\nx = 1\n\n[a]\nz = 1000.0\n"


def test_files(tmp_path):
    p = tmp_path / "conf.ini"
    data = {"name": "naïve", "s": {"v": [1, 2]}}
    dump(data, p)
    assert p.read_bytes() == 'name = "naïve"\n\n[s]\nv = [1, 2]\n'.encode("utf-8")
    assert load(p) == data
    assert load(str(p)) == data
    p.write_text("[s]\nx = 1\nx = 2\n", encoding="utf-8")
    with pytest.raises(DuplicateKeyError) as ei:
        load(p)
    assert ei.value.line == 3
