import math

import pytest

from minicalc import (Assign, Binary, Bool, CalcError, Call, EvalError, LexError, Num, ParseError, Program,
                      Token, Unary, Var, evaluate, parse, tokenize)


# ---- lexer ----

def test_tokenize_kinds_values_positions():
    toks = tokenize("x1 = 3.5e2 + y")
    assert toks == [Token("NAME", "x1", 0), Token("OP", "=", 3), Token("NUM", 350.0, 5),
                    Token("OP", "+", 11), Token("NAME", "y", 13), Token("EOF", None, 14)]


def test_tokenize_int_vs_float():
    toks = tokenize("12 12.0 1e3")
    assert [type(t.value) for t in toks[:3]] == [int, float, float]
    assert toks[0].value == 12


def test_tokenize_two_char_ops_preferred():
    vals = [t.value for t in tokenize("a<=b==c!=d>=e&&f||g") if t.kind == "OP"]
    assert vals == ["<=", "==", "!=", ">=", "&&", "||"]


def test_tokenize_empty_gives_eof():
    assert tokenize("  \n\t ") == [Token("EOF", None, 5)]


def test_tokenize_bad_char_position():
    with pytest.raises(LexError) as ei:
        tokenize("1 + $")
    assert ei.value.pos == 4
    assert isinstance(ei.value, CalcError)


def test_token_is_frozen():
    t = tokenize("1")[0]
    with pytest.raises(Exception):
        t.kind = "X"


# ---- parser ----

def test_parse_precedence():
    assert parse("1 + 2 * 3") == Program([Binary("+", Num(1), Binary("*", Num(2), Num(3)))])


def test_parse_left_assoc():
    assert parse("8 - 3 - 1").statements[0] == Binary("-", Binary("-", Num(8), Num(3)), Num(1))


def test_parse_power_right_assoc():
    assert parse("2 ^ 3 ^ 2").statements[0] == Binary("^", Num(2), Binary("^", Num(3), Num(2)))


def test_parse_unary_minus_vs_power():
    assert parse("-2^2").statements[0] == Unary("-", Binary("^", Num(2), Num(2)))
    assert parse("2^-1").statements[0] == Binary("^", Num(2), Unary("-", Num(1)))


def test_parse_repeated_unary():
    assert parse("--x").statements[0] == Unary("-", Unary("-", Var("x")))
    assert parse("!true").statements[0] == Unary("!", Bool(True))


def test_parse_assignment_chain_and_program():
    p = parse("a = b = 2; a + b;")
    assert p == Program([Assign("a", Assign("b", Num(2))), Binary("+", Var("a"), Var("b"))])


def test_parse_call_args():
    assert parse("max(1, f(), g(2, 3))").statements[0] == Call("max", [Num(1), Call("f", []),
                                                                        Call("g", [Num(2), Num(3)])])


def test_parse_logic_precedence():
    assert parse("a || b && c").statements[0] == Binary("||", Var("a"), Binary("&&", Var("b"), Var("c")))
    assert parse("1 < 2 && 3 > 2").statements[0] == Binary("&&", Binary("<", Num(1), Num(2)),
                                                           Binary(">", Num(3), Num(2)))


def test_parse_comparison_non_associative():
    with pytest.raises(ParseError):
        parse("1 < 2 < 3")


def test_parse_errors_positions():
    with pytest.raises(ParseError) as ei:
        parse("1 + ")
    assert ei.value.pos == 4
    with pytest.raises(ParseError) as ei:
        parse("(1 + 2")
    assert ei.value.pos == 6
    with pytest.raises(ParseError) as ei:
        parse("1 2")
    assert ei.value.pos == 2


def test_parse_bad_assignment_target_and_empty():
    with pytest.raises(ParseError):
        parse("1 = 2")
    with pytest.raises(ParseError):
        parse("(a) = 2")
    with pytest.raises(ParseError):
        parse("  ;; ")


# ---- evaluator ----

def test_eval_arithmetic():
    assert evaluate("1 + 2 * 3 - 4") == 3
    assert evaluate("7 / 2") == 3.5
    assert isinstance(evaluate("4 / 2"), float)
    assert evaluate("-7 % 3") == 2
    assert evaluate("2 ^ 10") == 1024
    assert evaluate("-2 ^ 2") == -4


def test_eval_env_and_assignment_visible():
    env = {"x": 4}
    assert evaluate("y = x * 2; y + 1", env) == 9
    assert env["y"] == 8


def test_eval_assignment_value_returned():
    assert evaluate("a = b = 5") == 5


def test_eval_comparisons_and_logic():
    assert evaluate("1 < 2") is True
    assert evaluate("2 == 2.0") is True
    assert evaluate("0 || 5") is True
    assert evaluate("1 && 0") is False
    assert evaluate("!0") is True


def test_eval_short_circuit():
    assert evaluate("false && undefined_var") is False
    assert evaluate("true || 1 / 0") is True


def test_eval_builtins():
    assert evaluate("abs(-3)") == 3
    assert evaluate("min(4, 2, 8)") == 2
    assert evaluate("max(4, 2, 8)") == 8
    assert evaluate("sqrt(16)") == 4.0
    assert evaluate("round(2.675, 2)") == round(2.675, 2)
    assert evaluate("round(7.5)") == 8


def test_eval_if_is_lazy():
    assert evaluate("if(1 > 0, 10, 1 / 0)") == 10
    assert evaluate("if(0, nope, 3)") == 3


def test_eval_errors():
    for src in ("1 / 0", "5 % 0", "sqrt(-1)", "(-8) ^ 0.5", "min()", "abs(1, 2)", "true + 1", "-true"):
        with pytest.raises(EvalError):
            evaluate(src)


def test_eval_unknown_names_in_message():
    with pytest.raises(EvalError) as ei:
        evaluate("zeta + 1")
    assert "zeta" in str(ei.value)
    with pytest.raises(EvalError) as ei:
        evaluate("frobnicate(1)")
    assert "frobnicate" in str(ei.value)


def test_eval_separate_namespaces():
    assert evaluate("max = 3; max(max, 2)") == 3


def test_eval_float_math():
    assert math.isclose(evaluate("2 ^ 0.5"), math.sqrt(2))


def test_eval_propagates_lex_parse_errors():
    with pytest.raises(LexError):
        evaluate("1 # 2")
    with pytest.raises(ParseError):
        evaluate("1 +")
