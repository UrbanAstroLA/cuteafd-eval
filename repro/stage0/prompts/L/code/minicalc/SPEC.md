Build a Python package named `minicalc`: a small expression language with a lexer, a parser that produces an AST, and an evaluator. Python 3.12, standard library only.

## Files

- `minicalc/__init__.py` — re-exports `tokenize`, `parse`, `evaluate`, `Token`, `CalcError`, `LexError`, `ParseError`, `EvalError`, and the AST node classes.
- `minicalc/errors.py` — the exception classes.
- `minicalc/lexer.py` — `Token` and `tokenize`.
- `minicalc/ast.py` — the AST node classes.
- `minicalc/parser.py` — `parse`.
- `minicalc/evaluator.py` — `evaluate`.

## errors.py

- `CalcError(Exception)` is the base class of all errors raised by the package.
- `LexError(CalcError)` and `ParseError(CalcError)` take `(message: str, pos: int)` and store the 0-based character offset as attribute `pos`. `str(err)` must contain the message.
- `EvalError(CalcError)` takes `(message: str)`.

## lexer.py

`Token` is a frozen dataclass with fields `kind: str`, `value`, `pos: int` (0-based offset of the token's first character).

`tokenize(src: str) -> list[Token]` returns all tokens followed by exactly one `Token("EOF", None, len(src))`. Whitespace (spaces, tabs, newlines) is skipped. Token kinds:

- `"NUM"`: matches `[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?`. The value is an `int` when the text has neither a fraction nor an exponent, otherwise a `float`. A number cannot start with `.`.
- `"NAME"`: matches `[A-Za-z_][A-Za-z0-9_]*`. The value is the text. The words `true` and `false` are not special in the lexer; they are names.
- `"OP"`: the value is the operator text. Two-character operators `==`, `!=`, `<=`, `>=`, `&&`, `||` take precedence over one-character operators. One-character operators: `+ - * / % ^ ( ) , = < > ! ;`.
- Any other character raises `LexError` with `pos` at that character.

## ast.py

All nodes are dataclasses with `eq=True` (the default), so trees compare by value:

- `Num(value)` — int or float
- `Bool(value)` — bool
- `Var(name)`
- `Unary(op, operand)` — op is `"-"`, `"+"` or `"!"`
- `Binary(op, left, right)` — op is one of `+ - * / % ^ == != < <= > >= && ||`
- `Call(name, args)` — args is a `list` of nodes
- `Assign(name, value)`
- `Program(statements)` — statements is a `list` of nodes

## parser.py

`parse(src: str) -> Program` tokenizes `src` and parses it. Grammar, from lowest to highest precedence:

1. A program is one or more statements separated by `;`. A trailing `;` is allowed. An empty program (only whitespace, or only `;`) is a `ParseError`.
2. Assignment: `NAME = expr`, right-associative (`a = b = 2` is `Assign("a", Assign("b", Num(2)))`). The left side must be a bare name; anything else before `=` is a `ParseError`.
3. `||` (left-associative)
4. `&&` (left-associative)
5. Comparison: `== != < <= > >=`, non-associative: `a < b < c` is a `ParseError`.
6. Additive: `+ -` (left-associative)
7. Multiplicative: `* / %` (left-associative)
8. Unary prefix: `- + !` (may repeat: `--x` is `Unary("-", Unary("-", Var("x")))`)
9. Power: `^`, right-associative, and it binds tighter than unary minus on its left: `-2^2` is `Unary("-", Binary("^", Num(2), Num(2)))`. The right operand of `^` may itself be a unary expression: `2^-1` is valid.
10. Primary: number, name, function call `NAME(arg, ...)` with zero or more comma-separated arguments, or a parenthesized expression. The names `true` and `false` parse to `Bool(True)` and `Bool(False)`.

Any unexpected token raises `ParseError` whose `pos` is that token's `pos` (for unexpected end of input, `pos == len(src)`).

## evaluator.py

`evaluate(src: str, env: dict | None = None)` parses and evaluates the program and returns the value of the last statement. `env` maps variable names to values; assignments store into it (so the caller sees them), and an assignment's value is the assigned value. When `env` is None a fresh dict is used.

Semantics:

- `+ - *` follow Python on int/float. `/` is always true division (returns float). `%` is Python's modulo. Division or modulo by zero raises `EvalError`.
- `^` is power (Python `**`). If the result would be complex (negative base, non-integer exponent) raise `EvalError`.
- Comparisons return `bool`. `&&` and `||` short-circuit and return `bool` of the deciding operand's truth value (`0 || 5` is `True`).
- `!x` is `not x` (a `bool`). Unary `-` and `+` on a bool raise `EvalError`; arithmetic on bools raises `EvalError` as well (`true + 1` is an error).
- An undefined variable raises `EvalError` whose message contains the variable's name.
- Built-in functions: `abs(x)`, `min(x, ...)` and `max(x, ...)` with at least one argument, `sqrt(x)` (float; negative argument raises `EvalError`), `round(x)` and `round(x, n)` (Python's `round`), `if(cond, a, b)` which evaluates only the chosen branch. Wrong argument count raises `EvalError`. An unknown function raises `EvalError` whose message contains its name. Variables and functions live in separate namespaces.
- Errors from lexing and parsing propagate unchanged (`LexError`, `ParseError`).
