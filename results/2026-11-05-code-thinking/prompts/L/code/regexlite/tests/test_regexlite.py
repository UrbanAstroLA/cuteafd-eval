import ast
import pathlib

import pytest

import regexlite
from regexlite import Match, Pattern, RegexError, compile, findall, fullmatch, match, search, sub


def test_literal_match_search_fullmatch():
    assert match("ab", "abc").group() == "ab"
    assert match("bc", "abc") is None
    m = search("bc", "abc")
    assert m.span() == (1, 3) and m.start() == 1 and m.end() == 3
    assert fullmatch("ab", "abc") is None
    assert fullmatch("abc", "abc").group() == "abc"
    assert isinstance(m, Match) and m.string == "abc"


def test_pattern_attributes_and_pos():
    p = compile("(a)(?:b)(c(d))")
    assert isinstance(p, Pattern)
    assert p.pattern == "(a)(?:b)(c(d))"
    assert p.groups == 3
    q = compile("b")
    assert q.match("abab", 1).span() == (1, 2)
    assert q.match("abab", 0) is None
    assert q.search("abab", 2).span() == (3, 4)


def test_dot_and_newline():
    assert search("a.c", "xa\ncabc").span() == (4, 7)
    assert fullmatch("a.c", "a\nc") is None
    assert fullmatch(r"a\Sc", "a\nc") is None
    assert fullmatch(r"a\Dc", "a\nc") is not None
    assert fullmatch("a[^x]c", "a\nc") is not None


def test_escapes():
    assert findall(r"\d+", "a12b345") == ["12", "345"]
    assert findall(r"\w+", "hi_1 there!") == ["hi_1", "there"]
    assert findall(r"\s", "a b\tc\nd") == [" ", "\t", "\n"]
    assert fullmatch(r"\W\D\S", "!x!") is not None
    assert fullmatch(r"a\.b\*\\", "a.b*\\") is not None
    assert fullmatch(r"\n\t", "\n\t") is not None
    assert fullmatch(r"a]}", "a]}") is not None


def test_character_classes():
    assert findall("[a-cx]", "abcdxyz") == ["a", "b", "c", "x"]
    assert findall("[^a-c]", "abcde") == ["d", "e"]
    assert findall("[]a]", "a]b") == ["a", "]"]
    assert findall("[^]a]", "a]b") == ["b"]
    assert findall("[-a]", "-ab") == ["-", "a"]
    assert findall("[a-]", "-ab") == ["-", "a"]
    assert findall(r"[\d-z]", "5-zy") == ["5", "-", "z"]
    assert findall(r"[\]\\]", "]\\a") == ["]", "\\"]
    assert findall(r"[\s,]+", "a , b c") == [" , ", " "]


def test_quantifiers_greedy_and_lazy():
    assert search("<.*>", "<a><b>").group() == "<a><b>"
    assert search("<.*?>", "<a><b>").group() == "<a>"
    assert match("a+?", "aaa").group() == "a"
    assert match("a??b", "ab").group() == "ab"
    assert match("a{2,3}", "aaaa").group() == "aaa"
    assert match("a{2,3}?", "aaaa").group() == "aa"
    assert match("a{2}", "aaaa").group() == "aa"
    assert match("a{2,}", "aaaaa").group() == "aaaaa"
    assert match("a{3}", "aa") is None
    assert match("(ab){0}c", "c").groups() == (None,)


def test_alternation_priority_and_fullmatch_backtracking():
    assert search("a|ab", "ab").group() == "a"
    assert fullmatch("a|ab", "ab").group() == "ab"
    assert match("x(a|ab)(c|bcd)(d*)", "xabcd").groups() == ("a", "bcd", "")
    assert match("a|", "b").span() == (0, 0)
    assert search("cat|dog", "hotdog").span() == (3, 6)


def test_groups_and_spans():
    m = match("(a)(x)?(b(c))", "abc")
    assert m.group(0, 1, 3, 4) == ("abc", "a", "bc", "c")
    assert m.groups() == ("a", None, "bc", "c")
    assert m.group(2) is None
    assert m.span(2) == (-1, -1) and m.start(2) == -1 and m.end(2) == -1
    assert m.span(4) == (2, 3)
    with pytest.raises(IndexError):
        m.group(5)
    with pytest.raises(IndexError):
        m.span(-1)


def test_captures_last_iteration_and_persistence():
    assert match(r"(\w)+", "abc").group(1) == "c"
    assert match("(a|(b))+", "ba").groups() == ("a", "b")
    assert match("(?:(a)|b)*", "ab").groups() == ("a",)


def test_backtracking_undoes_captures():
    m = match("(a)*ab", "aab")
    assert m.group() == "aab" and m.group(1) == "a" and m.span(1) == (0, 1)
    m = match("(?:(a)|(a)b)c", "abc")
    assert m.groups() == (None, "a")


def test_empty_iteration_rule():
    m = match("(a*)*", "b")
    assert m.group() == "" and m.group(1) is None
    m = match("(a*)+", "aa")
    assert m.group() == "aa" and m.group(1) == "aa"
    m = match("(a?){2}b", "b")
    assert m.group() == "b" and m.span(1) == (0, 0)
    assert match("(?:a|)*b", "aab").group() == "aab"


def test_anchors():
    assert search("^a", "ba") is None
    assert search("a$", "ab") is None
    assert search("a$", "a\n") is None
    assert search("a$", "ba").span() == (1, 2)
    assert compile("^b").search("ab", 1) is None
    assert fullmatch("^$", "") is not None
    assert findall("^a|b$", "aab") == ["a", "b"]


def test_findall_shapes():
    assert findall("a(b)?", "abaab") == ["b", "", "b"]
    assert findall("(a)(b)?", "abab a") == [("a", "b"), ("a", "b"), ("a", "")]
    assert findall("zz", "abc") == []


def test_findall_and_finditer_empty_matches():
    assert findall("a*", "baa") == ["", "aa", ""]
    assert findall("", "ab") == ["", "", ""]
    spans = [m.span() for m in compile(r"\d*").finditer("1a22")]
    assert spans == [(0, 1), (1, 1), (2, 4), (4, 4)]


def test_sub_templates():
    assert sub(r"(\w+)@(\w+)", r"\2 at \1", "joe@site, ann@web") == "site at joe, web at ann"
    assert sub("b+", r"[\0]", "abbcb") == "a[bb]c[b]"
    assert sub("a", r"\\", "aXa") == "\\X\\"
    assert sub("(x)|y", r"<\1>", "xy") == "<x><>"
    assert sub("a", "-", "aaaa", count=2) == "--aa"
    assert sub("q", "-", "abc") == "abc"


def test_sub_empty_matches_and_callable():
    assert sub("x*", "-", "abc") == "-a-b-c-"
    assert sub("a*", "-", "baac") == "-b--c-"
    assert compile(r"\d+").sub(lambda m: str(int(m.group()) * 2), "a1b25") == "a2b50"


@pytest.mark.parametrize("repl,pos", [("ab\\", 2), (r"x\q", 1), (r"\3", 0), (r"ok \1 \3", 6)])
def test_sub_template_errors(repl, pos):
    with pytest.raises(RegexError) as ei:
        sub("(a)(b)", repl, "zzz")
    assert ei.value.pos == pos


@pytest.mark.parametrize("pattern,pos", [
    ("ab\\", 2), (r"a\q", 1), (r"\1", 0), ("ab[cd", 2), ("[]", 0), ("[^]", 0), ("x[z-a]", 2),
    (r"[a-\d]", 3), ("(?P<n>a)", 0), ("a)", 1), ("(a", 0), ("(a)(b(c)", 3), ("((a)", 0),
    ("a(?:b", 1), ("a)(", 1), ("[a\\", 2),
])
def test_compile_errors_positions(pattern, pos):
    with pytest.raises(RegexError) as ei:
        compile(pattern)
    assert ei.value.pos == pos


@pytest.mark.parametrize("pattern,pos", [
    ("*a", 0), ("a**", 2), ("a*??", 3), ("(+a)", 1), ("a|?", 2), ("^*", 1), ("a$+", 2), ("{2}", 0),
])
def test_nothing_to_repeat(pattern, pos):
    with pytest.raises(RegexError) as ei:
        compile(pattern)
    assert ei.value.pos == pos


@pytest.mark.parametrize("pattern,pos", [
    ("a{2,1}", 1), ("ab{x}", 2), ("a{,3}", 1), ("a{2", 1), ("a{2,3", 1), ("a{}", 1),
])
def test_brace_errors(pattern, pos):
    with pytest.raises(RegexError) as ei:
        compile(pattern)
    assert ei.value.pos == pos


def test_error_class_and_message():
    with pytest.raises(RegexError) as ei:
        compile("(a")
    assert isinstance(ei.value, Exception)
    assert str(ei.value)
    with pytest.raises(RegexError):
        search("[", "x")


def test_ranges_with_escaped_endpoints():
    assert findall(r"[\--/]", "+-./0") == ["-", ".", "/"]
    with pytest.raises(RegexError) as ei:
        compile(r"[\z-a]")
    assert ei.value.pos == 1


def test_empty_group_and_alternatives():
    assert match("()a", "a").span(1) == (0, 0)
    assert match("(|b)", "bc").groups() == ("",)
    assert fullmatch("(|b)c", "bc").groups() == ("b",)


def test_does_not_import_re():
    pkg = pathlib.Path(regexlite.__file__).parent
    for path in pkg.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name.split(".")[0] != "re" for a in node.names), path
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] != "re", path
