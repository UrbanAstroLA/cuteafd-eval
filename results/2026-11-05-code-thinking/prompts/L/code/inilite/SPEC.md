Build a Python package named `inilite`: a parser and writer for a typed INI dialect with dotted subsections, lists, append assignments and line-numbered errors. Python 3.12, standard library only.

## Files

- `inilite/__init__.py` — re-exports `loads`, `load`, `dumps`, `dump`, `IniError`, `ParseError`, `DuplicateKeyError`.
- `inilite/errors.py` — the exception classes.
- `inilite/values.py` — scanning and formatting of single values (internal helpers).
- `inilite/parser.py` — `loads` and `load`.
- `inilite/writer.py` — `dumps` and `dump`.

## errors.py

- `IniError(Exception)` — base class.
- `ParseError(IniError)` — `ParseError(message, line)` with attribute `line` (1-based). `str(err)` contains `line <n>`, e.g. `"line 3: invalid value"`.
- `DuplicateKeyError(ParseError)` — a name defined twice (rules below).

## parser.py

`loads(text) -> dict` splits `text` on `"\n"`, removes one trailing `"\r"` from each line, and handles lines in order; line numbers count from 1. Leading and trailing spaces and tabs of a line are ignored.

- Blank lines are ignored. A line whose first character is `#` or `;` is a comment.
- A *name* is one or more of `A-Z a-z 0-9 _ -`.
- Header: `[`, optional whitespace, one or more names joined by `.` (no whitespace inside the path), optional whitespace, `]`, then nothing or optional whitespace and a comment (`#` or `;` to end of line). `[a.b]` makes `result["a"]["b"]` the current section, creating missing dicts. Repeating a header reopens that section. Lines before the first header go into the top-level dict.
- Assignment: name, optional whitespace, `=` or `+=`, optional whitespace, a value, then optional whitespace and nothing or a comment.
- Any other line raises `ParseError`: e.g. a missing `=`, an empty value, `[a..b]`, `[]`, `[a b]`, `[a] x`, `a = 1 2`.

Values (all on one line):

- bool: `true` or `false` (lowercase only).
- int: optional `+`/`-`, then `0` or a digit 1-9 followed by digits (`007` is invalid).
- float: an int as above followed by a fraction (`.` and one or more digits), an exponent (`e` or `E`, optional sign, one or more digits), or both; converted with `float()`. `1.`, `.5`, `1e`, `inf` and `nan` are invalid.
- string: double-quoted. Escapes: `\\`, `\"`, `\n`, `\t`, `\r`, and `\u` followed by exactly four hex digits (either case). Other characters stand for themselves. Any other escape or a missing closing quote is invalid.
- list: `[`, items separated by `,`, `]`, with optional whitespace around items. Items are bools, ints, floats or strings; `[]` is empty. Nested lists, empty items (`[1,,2]`, `[,]`) and a trailing comma are invalid.
- An unquoted token ends at whitespace, `,`, `]`, `#`, `;` or end of line and must then be exactly a bool, int or float; anything else (e.g. `hello`, `True`, `1_000`) is invalid. So `a = 1#c` is `1` with a comment.

Definition rules:

- `key = value` when `key` already exists in the current section, as a value or as a subsection, raises `DuplicateKeyError`.
- A header whose path runs into an existing non-dict value (`a = 1` then `[a]` or `[a.b]`) raises `DuplicateKeyError`.
- `key += value` requires an existing list under `key` in the current section: a list value extends it, a scalar is appended. A missing key or a non-list raises `ParseError` (not `DuplicateKeyError`).

Every error is raised at the line where it is detected. The result is plain nested dicts with keys in first-definition order (a section is defined when a header first creates it, directly or as part of a longer path).

`load(path)` reads `path` (`str` or `pathlib.Path`) as UTF-8 and returns `loads` of it.

## writer.py

`dumps(data: dict) -> str`:

- Allowed values: `bool`, `int`, `float`, `str`, `list` of those scalars, and `dict` (a section). Anything else (`None`, tuples, nested lists, a dict in a list) raises `TypeError`. A key that is not a `str` matching the name rule (non-`str` keys included) raises `ValueError`, as does a NaN or infinite float.
- A dict at path P is written as: its non-dict entries as `key = value` lines in insertion order, then for each dict entry, in insertion order, a header `[P.key]` followed recursively by that dict. The top-level dict has no header; every nested dict gets one, even when empty.
- A blank line precedes every header except when it would be the first line of output. Every line ends with `"\n"`; `dumps({})` is `""`.
- Formatting: `true`/`false`; ints with `str()`; floats with `repr()`; lists as `[` + items joined by `", "` + `]`; strings in double quotes with `\` as `\\`, `"` as `\"`, newline as `\n`, tab as `\t`, carriage return as `\r`, any other character below U+0020 and U+007F as `\u` plus four lowercase hex digits, everything else verbatim.
- For every valid `data`, `loads(dumps(data)) == data`.

`dump(data, path)` writes `dumps(data)` to `path` as UTF-8.
