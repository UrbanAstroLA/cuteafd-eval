import random

import pytest

from textdiff import (DiffError, Hunk, PatchConflict, PatchFormatError, apply_patch, diff_lines, parse_patch,
                      split_lines, unified_diff)

TEN = "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"
NO_NL = "\\ No newline at end of file\n"


def test_split_lines():
    assert split_lines("a\nb") == ["a\n", "b"]
    assert split_lines("a\n") == ["a\n"]
    assert split_lines("") == []
    assert split_lines("\n\n") == ["\n", "\n"]
    assert split_lines("x\r\ny\rz") == ["x\r\n", "y\rz"]


def test_diff_lines_basic():
    a = ["a\n", "b\n", "c\n"]
    b = ["a\n", "c\n", "d\n"]
    assert diff_lines(a, b) == [(" ", "a\n"), ("-", "b\n"), (" ", "c\n"), ("+", "d\n")]
    assert diff_lines([], []) == []
    assert diff_lines([], ["q"]) == [("+", "q")]
    assert diff_lines(["q"], []) == [("-", "q")]


def test_diff_lines_tie_breaking():
    assert diff_lines(["x", "y"], ["y", "x"]) == [("-", "x"), (" ", "y"), ("+", "x")]
    assert diff_lines(["p", "q"], ["r", "q"]) == [("-", "p"), ("+", "r"), (" ", "q")]
    assert diff_lines(["1", "2"], ["3", "4"]) == [("-", "1"), ("-", "2"), ("+", "3"), ("+", "4")]
    assert diff_lines(["x", "a"], ["a", "x", "a"]) == [("+", "a"), (" ", "x"), (" ", "a")]


def test_diff_lines_terminator_matters():
    assert diff_lines(["x"], ["x\n"]) == [("-", "x"), ("+", "x\n")]


def test_unified_identical_is_empty():
    assert unified_diff("same\n", "same\n") == ""
    assert unified_diff("", "") == ""


def test_unified_basic_with_names():
    out = unified_diff("one\ntwo\nthree\nfour\n", "one\n2\nthree\nfour\nfive\n", "old.txt", "new.txt")
    assert out == ("--- old.txt\n+++ new.txt\n@@ -1,4 +1,5 @@\n one\n-two\n+2\n three\n four\n+five\n")


def test_unified_hunks_split_when_gap_exceeds_twice_context():
    b = TEN.replace("b\n", "B\n").replace("i\n", "I\n")
    assert unified_diff(TEN, b, context=1) == (
        "--- a\n+++ b\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n@@ -8,3 +8,3 @@\n h\n-i\n+I\n j\n")


def test_unified_hunks_merge_when_gap_is_twice_context():
    b = TEN.replace("b\n", "B\n").replace("e\n", "E\n")
    assert unified_diff(TEN, b, context=1) == (
        "--- a\n+++ b\n@@ -1,6 +1,6 @@\n a\n-b\n+B\n c\n d\n-e\n+E\n f\n")


def test_unified_context_zero_ranges():
    out = unified_diff("1\n2\n3\n", "0\n1\n3\n4\n", context=0)
    assert out == "--- a\n+++ b\n@@ -0,0 +1 @@\n+0\n@@ -2 +2,0 @@\n-2\n@@ -3,0 +4 @@\n+4\n"


def test_unified_empty_sides():
    assert unified_diff("", "one\ntwo\n") == "--- a\n+++ b\n@@ -0,0 +1,2 @@\n+one\n+two\n"
    assert unified_diff("gone\n", "") == "--- a\n+++ b\n@@ -1 +0,0 @@\n-gone\n"


def test_unified_missing_final_newline():
    assert unified_diff("x\ny", "x\ny\n") == "--- a\n+++ b\n@@ -1,2 +1,2 @@\n x\n-y\n" + NO_NL + "+y\n"
    out = unified_diff("a\nb\nc", "A\nb\nc")
    assert out == "--- a\n+++ b\n@@ -1,3 +1,3 @@\n-a\n+A\n b\n c\n" + NO_NL


def test_unified_negative_context():
    with pytest.raises(ValueError):
        unified_diff("a\n", "b\n", context=-1)


def test_parse_patch_structure():
    patch = "--- x\n+++ y\n@@ -1,2 +1 @@ def f():\n a\n-b\n@@ -5 +4,2 @@\n-e\n+E\n+F\n"
    hunks = parse_patch(patch)
    assert hunks == [Hunk(1, 2, 1, 1, [(" ", "a\n"), ("-", "b\n")]),
                     Hunk(5, 1, 4, 2, [("-", "e\n"), ("+", "E\n"), ("+", "F\n")])]
    assert parse_patch("") == []


def test_parse_patch_no_newline_marker():
    hunks = parse_patch("--- a\n+++ b\n@@ -1 +1 @@\n-y\n" + NO_NL + "+y\n")
    assert hunks[0].lines == [("-", "y"), ("+", "y\n")]


PARSE_ERRORS = [
    ("+++ b\n--- a\n@@ -1 +1 @@\n-a\n+b\n", 1),
    ("--- a\n*** b\n@@ -1 +1 @@\n-a\n+b\n", 2),
    ("--- a\n+++ b\n", 3),
    ("--- a\n+++ b\n@@ -1 +1@@\n-a\n+b\n", 3),
    ("--- a\n+++ b\n@@ -1 +1 @@\n-a\n*b\n", 5),
    ("--- a\n+++ b\n@@ -1 +1 @@\n" + NO_NL + "-a\n+b\n", 4),
    ("--- a\n+++ b\n@@ -1,2 +1 @@\n-a\n", 5),
    ("--- a\n+++ b\n@@ -1 +1 @@\n-a\n-b\n+c\n", 5),
    ("--- a\n+++ b\n@@ -1 +1 @@\n-a\n+b\n c\n", 6),
    ("--- a\n+++ b\n@@ -0 +1 @@\n-a\n+b\n", 3),
    ("--- a\n+++ b\n@@ -3 +3 @@\n-c\n+C\n@@ -2 +2 @@\n-b\n+B\n", 6),
    ("--- a\n+++ b\n@@ -1,2 +1,2 @@\n-a\n-b\n+A\n+B\n@@ -2 +3 @@\n-b\n+B\n", 8),
]


def test_parse_patch_errors():
    for patch, line in PARSE_ERRORS:
        with pytest.raises(PatchFormatError) as ei:
            parse_patch(patch)
        assert ei.value.line == line, patch
        assert isinstance(ei.value, DiffError)


def test_apply_basic_and_empty_patch():
    old = "one\ntwo\nthree\nfour\n"
    new = "one\n2\nthree\nfour\nfive\n"
    assert apply_patch(old, unified_diff(old, new)) == new
    assert apply_patch(old, "") == old


def test_apply_hand_written_multi_hunk_uses_original_positions():
    patch = "--- a\n+++ b\n@@ -1,0 +2,2 @@\n+x\n+y\n@@ -3 +4,0 @@\n-c\n@@ -5,2 +6 @@\n-e\n-f\n+F\n"
    assert apply_patch("a\nb\nc\nd\ne\nf\n", patch) == "a\nx\ny\nb\nd\nF\n"


def test_apply_conflict_reports_hunk_and_line():
    patch = "--- a\n+++ b\n@@ -1 +1 @@\n-a\n+A\n@@ -3,2 +3,2 @@\n c\n-d\n+D\n"
    with pytest.raises(PatchConflict) as ei:
        apply_patch("a\nb\nc\nX\n", patch)
    assert ei.value.hunk == 2 and ei.value.line == 4
    assert "2" in str(ei.value) and "4" in str(ei.value)


def test_apply_conflict_past_end_and_terminator():
    with pytest.raises(PatchConflict) as ei:
        apply_patch("a\nb\n", "--- a\n+++ b\n@@ -2,2 +2,2 @@\n b\n-c\n+C\n")
    assert ei.value.hunk == 1 and ei.value.line == 3
    with pytest.raises(PatchConflict) as ei:
        apply_patch("a\n", "--- a\n+++ b\n@@ -4,0 +5 @@\n+z\n")
    assert ei.value.line == 2
    with pytest.raises(PatchConflict) as ei:
        apply_patch("x\ny\n", unified_diff("x\ny", "x\nz"))
    assert ei.value.line == 2


def test_apply_reverse():
    old, new = "a\nb\nc\nd\n", "a\nc\nd\ne"
    patch = unified_diff(old, new, context=1)
    assert apply_patch(new, patch, reverse=True) == old
    with pytest.raises(PatchConflict):
        apply_patch(old, patch, reverse=True)


def test_apply_newline_changes():
    assert apply_patch("x\ny", unified_diff("x\ny", "x\ny\n")) == "x\ny\n"
    assert apply_patch("x\ny\n", unified_diff("x\ny", "x\ny\n"), reverse=True) == "x\ny"
    assert apply_patch("p\r\nq\r\n", unified_diff("p\r\nq\r\n", "p\r\nQ\r\n")) == "p\r\nQ\r\n"


def test_round_trip_random():
    rng = random.Random(20261105)
    alphabet = ["a\n", "b\n", "c\n", "d\n", "\n", "e\r\n"]
    for _ in range(300):
        def text():
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
            if s and rng.random() < 0.3:
                s = s[:-1]
            return s
        a, b = text(), text()
        for ctx in (0, 1, 3):
            p = unified_diff(a, b, context=ctx)
            assert apply_patch(a, p) == b, (a, b, ctx)
            assert apply_patch(b, p, reverse=True) == a, (a, b, ctx)
            for h in parse_patch(p):
                assert sum(t != "+" for t, _ in h.lines) == h.old_count
                assert sum(t != "-" for t, _ in h.lines) == h.new_count
