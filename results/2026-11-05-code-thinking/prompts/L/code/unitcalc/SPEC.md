Build a Python package named `unitcalc`: physical quantities with SI units, unit parsing, dimension-checked arithmetic, conversion and formatting. Python 3.12, standard library only.

## Files

- `unitcalc/__init__.py` — re-exports `Unit`, `Quantity`, `parse_unit`, `parse_quantity`, `BASE`, `UnitError`, `ParseError`, `UnknownUnitError`, `DimensionError`.
- `unitcalc/errors.py` — `UnitError(Exception)` is the base class; `ParseError(UnitError)` takes `(message, pos)` and stores the 0-based offset as `pos`; `UnknownUnitError(UnitError)` takes the unknown atom text and stores it as `symbol`; `DimensionError(UnitError)`.
- `unitcalc/units.py` — `BASE`, the unit tables and `Unit`.
- `unitcalc/parser.py` — `parse_unit`, `parse_quantity`.
- `unitcalc/quantity.py` — `Quantity`.

## units.py

`BASE = ("kg", "m", "s", "A", "K", "mol", "cd")`. A dimension is a tuple of 7 integer exponents in this order.

A `Unit` has `factor` (a `fractions.Fraction`: the exact SI value of one unit), `dims`, ordered *terms* `(atom, exponent)` with non-zero exponents, and a `symbol` property built from the terms. `Unit * Unit`, `Unit / Unit` and `Unit ** n` combine factors and dimensions exactly. For `*`, the result's terms are the left terms in order, then right terms not already present; exponents of equal atoms are added and terms whose exponent becomes 0 are removed at once. `a / b` is `a * b ** -1`. `** n` multiplies every exponent by `n` (zero terms are removed); `n` must be an `int` (else `TypeError`). Units are equal (and hash equal) when `factor` and `dims` are equal.

`symbol`: terms with positive exponents form the numerator, joined by `*`; negative ones form the denominator, written with the absolute exponent. A term is `atom` if its exponent is 1, else `atom^e`. Result: numerator alone if there is no denominator; otherwise numerator (or `1` if empty), `/`, then the denominator — wrapped in parentheses if it has more than one term. No terms gives `""`.

Prefixes: `T` 10^12, `G` 10^9, `M` 10^6, `k` 10^3, `h` 10^2, `da` 10, `d` 10^-1, `c` 10^-2, `m` 10^-3, `u` 10^-6, `n` 10^-9, `p` 10^-12.

Named units (factor, dimension); all accept prefixes except `min` and `h`:

- `m`, `s`, `A`, `K`, `mol`, `cd` — 1, their base dimension; `g` — 1/1000, kg
- `N` = kg·m·s^-2, `J` = kg·m^2·s^-2, `W` = kg·m^2·s^-3, `Pa` = kg·m^-1·s^-2, `Hz` = s^-1, `C` = s·A, `V` = kg·m^2·s^-3·A^-1 — all factor 1
- `L` — 1/1000, m^3; `min` — 60, s; `h` — 3600, s

An atom (a run of ASCII letters) resolves as: the named unit with exactly that text if there is one; otherwise a prefix (longest first) followed by a non-empty remainder that is a named unit accepting prefixes; otherwise `UnknownUnitError`. The atom's term is `(text, 1)`, so `km` stays `km` in symbols.

## parser.py

`parse_unit(text) -> Unit`. Whitespace between tokens is ignored; text that is empty or only whitespace gives the dimensionless unit (factor 1, no terms). Grammar:

```
expr   := term (("*" | "/") term)*      left-associative
term   := factor ("^" integer)?         integer: optional "-" then digits
factor := atom | "1" | "(" expr ")"
```

`1` is the dimensionless unit. Any other unexpected character or token, including leftover input, raises `ParseError` whose `pos` is the offset of that character or token (`len(text)` at the end of input).

`parse_quantity(text) -> Quantity`: after optional leading whitespace, a number matching `[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?` — an `int` if its text has no `.`, `e` or `E`, else a `float` — followed by the rest of the text parsed with `parse_unit` (so no unit means dimensionless). No number raises `ParseError` at the first non-space character; a `ParseError` in the unit has `pos` relative to the whole text.

## quantity.py

`Quantity(value, unit="")` — `value` must be an `int` or `float` (not `bool`), else `TypeError`; `unit` is a `str` (parsed with `parse_unit`) or a `Unit`, else `TypeError`. Attributes `value`, `unit`. Plain numbers used as operands below act as dimensionless quantities.

- `to(unit)` — same dimension required, else `DimensionError`. The new value is `float(Fraction(value) * old.factor / new.factor)`, computed exactly.
- `to_base()` — converts to the unit whose terms are the base symbols in `BASE` order (e.g. `kg*m/s^2`).
- `simplify()` — converts to the first of `N`, `J`, `W`, `Pa`, `Hz`, `C`, `V` with the same dimension; otherwise `to_base()`.
- `float(q)` — `float(Fraction(value) * factor)` for a dimensionless quantity, else `DimensionError`.
- `+`, `-` — the right operand is converted with `to(left unit)` (so `DimensionError` on mismatch) and the result keeps the left unit.
- `*`, `/` — values combine with Python's `*` and `/`, units with `Unit` arithmetic (no conversion, so `km/m` stays `km/m`). Division by zero raises `ZeroDivisionError`.
- `q ** n` (`n` an `int`, else `TypeError`), unary `-`, `abs()`.
- `==` — `False` when dimensions differ; otherwise `math.isclose` of the two SI magnitudes (`float(Fraction(value) * factor)`) with `rel_tol=1e-9`. `<`, `<=`, `>`, `>=` raise `DimensionError` when dimensions differ; `a < b` is `not a == b and` the SI magnitude of `a` is less than that of `b`; `a <= b` is `a == b or a < b` (likewise for `>`/`>=`). Quantities are unhashable.
- `format(q, spec)` — `format(value, spec)` (an empty spec means `"g"`), then a space and `unit.symbol` unless the symbol is empty. `str(q)` is `format(q, "")`.
