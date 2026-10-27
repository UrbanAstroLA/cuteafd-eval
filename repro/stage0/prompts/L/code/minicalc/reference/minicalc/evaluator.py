import math

from .ast import Assign, Binary, Bool, Call, Num, Unary, Var
from .errors import EvalError
from .parser import parse


def _num(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise EvalError(f"expected a number, got {x!r}")
    return x


def _call(name, args, ev):
    if name == "if":
        if len(args) != 3:
            raise EvalError("if() takes 3 arguments")
        return ev(args[1]) if ev(args[0]) else ev(args[2])
    vals = [ev(a) for a in args]
    if name == "abs":
        if len(vals) != 1:
            raise EvalError("abs() takes 1 argument")
        return abs(_num(vals[0]))
    if name in ("min", "max"):
        if not vals:
            raise EvalError(f"{name}() needs at least 1 argument")
        return (min if name == "min" else max)(_num(v) for v in vals)
    if name == "sqrt":
        if len(vals) != 1:
            raise EvalError("sqrt() takes 1 argument")
        x = _num(vals[0])
        if x < 0:
            raise EvalError("sqrt of negative number")
        return math.sqrt(x)
    if name == "round":
        if len(vals) == 1:
            return round(_num(vals[0]))
        if len(vals) == 2:
            return round(_num(vals[0]), _num(vals[1]))
        raise EvalError("round() takes 1 or 2 arguments")
    raise EvalError(f"unknown function {name}")


def evaluate(src, env=None):
    if env is None:
        env = {}
    prog = parse(src)

    def ev(n):
        if isinstance(n, Num):
            return n.value
        if isinstance(n, Bool):
            return n.value
        if isinstance(n, Var):
            if n.name not in env:
                raise EvalError(f"undefined variable {n.name}")
            return env[n.name]
        if isinstance(n, Assign):
            v = ev(n.value)
            env[n.name] = v
            return v
        if isinstance(n, Unary):
            v = ev(n.operand)
            if n.op == "!":
                return not v
            v = _num(v)
            return -v if n.op == "-" else +v
        if isinstance(n, Binary):
            op = n.op
            if op == "&&":
                return bool(ev(n.left)) and bool(ev(n.right))
            if op == "||":
                return bool(ev(n.left)) or bool(ev(n.right))
            a, b = ev(n.left), ev(n.right)
            if op in ("==", "!="):
                return (a == b) if op == "==" else (a != b)
            a, b = _num(a), _num(b)
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            if op == ">=":
                return a >= b
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    raise EvalError("division by zero")
                return a / b
            if op == "%":
                if b == 0:
                    raise EvalError("modulo by zero")
                return a % b
            if op == "^":
                try:
                    r = a ** b
                except ZeroDivisionError:
                    raise EvalError("zero to a negative power") from None
                if isinstance(r, complex):
                    raise EvalError("complex result")
                return r
        if isinstance(n, Call):
            return _call(n.name, n.args, ev)
        raise EvalError(f"cannot evaluate {n!r}")

    result = None
    for s in prog.statements:
        result = ev(s)
    return result
