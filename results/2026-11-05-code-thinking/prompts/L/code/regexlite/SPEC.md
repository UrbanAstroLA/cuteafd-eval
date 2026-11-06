Build a Python package named `regexlite`: a small backtracking regular-expression engine with match objects and search, findall and substitution helpers. Python 3.12, standard library only; no module of the package may import `re`.

## Files

- `regexlite/__init__.py` — re-exports `compile`, `match`, `search`, `fullmatch`, `findall`, `sub`, `Pattern`, `Match`, `RegexError`.
- `regexlite/errors.py` — `RegexError`.
- `regexlite/parser.py` — the pattern parser.
- `regexlite/engine.py` — the matcher.
- `regexlite/api.py` — `Pattern`, `Match` and the module-level functions.

## errors.py

`RegexError(Exception)` takes `(message: str, pos: int)` and stores the 0-based offset as attribute `pos`. `str(err)` must contain the message.

## Syntax

- Metacharacters are `\ . [ ( ) * + ? { | ^ $`. Every other character, including `]` and `}`, matches itself.
- `.` matches any character except `"\n"`. `^` matches only at index 0 of the subject; `$` only at its end, never before a trailing newline.
- Escapes: `\d` (`0-9`), `\w` (ASCII letters, digits, `_`), `\s` (space, `\t \n \r \f \v`), and complements `\D \W \S` (any character, `"\n"` included, not in the set). `\n` and `\t` are newline and tab. A backslash before a character that is not an ASCII letter or digit matches that character. Any other escape (e.g. `\q`, `\1`) and a trailing `\` are errors at the backslash.
- Class `[...]`, negated `[^...]` (any character, `"\n"` included, not listed). A `]` right after `[` or `[^` is literal. Items are read left to right; an item is a single character (literal or single-character escape) or a class escape (`\d` etc.; same escape rules). A single-character item followed by `-` and then a character other than `]` forms a range; its end must be a single-character item (a class escape there is an error at its backslash), and a start greater than the end is an error at the start item's first character. Any other `-` is literal: `[-a]`, `[a-]` and `[\d-z]` all contain `-`. An unterminated class (including `[]` and `[^]`) is an error at the `[`.
- Groups: `(...)` captures, numbered 1, 2, ... in the order of their `(`. `(?:...)` does not capture. `(?` followed by anything but `:` is an error at the `(`. An unmatched `)` is an error at it; an unclosed `(` is an error at the last unclosed `(`. Empty groups and empty alternatives are allowed.
- Alternation `|` has the lowest precedence.
- Quantifiers follow an atom: `*`, `+`, `?`, `{m}`, `{m,}`, `{m,n}` with m, n one or more decimal digits. A `{` not starting one of these forms, or with n < m, is an error at the `{`. A quantifier followed by `?` is lazy. A quantifier with nothing to repeat (at the start of the pattern, a group or an alternative, after `^` or `$`, or after another quantifier: `a**`, `a*??`) is an error at its first character.
- With several errors, the first reached reading left to right is reported (an unclosed `(` or `[` is reached at the end of the pattern).

## Matching

Alternatives are tried left to right, greedy quantifiers try more repetitions first, lazy ones fewer; the first successful path wins (`a|ab` searched in `"ab"` matches `"a"`). A group captures the text of its last successful iteration; an earlier iteration's capture persists if a later one does not enter that group (`(a|(b))+` on `"ba"` gives groups `("a", "b")`); backtracking undoes captures. Once a quantifier's minimum count is reached, an iteration matching the empty string is not allowed (the loop stops instead): `(a*)*` against `"b"` matches `""` with group 1 `None`.

## api.py

`compile(pattern) -> Pattern` raises `RegexError` for an invalid pattern. `Pattern` has attributes `pattern` (the source) and `groups` (number of capturing groups), and methods:

- `match(s, pos=0)` — a `Match` if the pattern matches starting exactly at `pos`, else `None`.
- `search(s, pos=0)` — the match with the lowest start `>= pos`, else `None`. `^` still means index 0.
- `fullmatch(s)` — a match from 0 to `len(s)`, found with backtracking (`a|ab` matches all of `"ab"`).
- `finditer(s)` — iterator of matches: search from 0; after a match ending at `e`, search next from `e`, or from `e + 1` if the match was empty (stop once past `len(s)`).
- `findall(s)` — for those matches: whole-match strings if the pattern has no groups, group-1 strings if one, else tuples of all groups; a non-participating group gives `""`.
- `sub(repl, s, count=0)` — replace the `finditer` matches (only the first `count` if `count > 0`); return the new string. `repl` is a callable taking a `Match` and returning a `str`, or a template where `\0`..`\9` insert that group's text (`\0` the whole match; `""` if not participating) and `\\` a backslash. Any other backslash use, a trailing backslash, or a group number above `groups` raises `RegexError` with `pos` at that backslash in `repl`, even when nothing matches.

`Match` has attribute `string` and methods:

- `group(*indices)` — no argument means group 0; one index gives that group's text (`None` if it did not participate); several give a tuple. An index outside `0..groups` raises `IndexError`.
- `groups()` — tuple of groups 1..n.
- `start(n=0)`, `end(n=0)`, `span(n=0)` — offsets in the subject; `-1` / `(-1, -1)` for a non-participating group; `IndexError` as for `group`.

Module-level `match(pattern, s)`, `search(pattern, s)`, `fullmatch(pattern, s)`, `findall(pattern, s)` and `sub(pattern, repl, s, count=0)` compile `pattern` and call the method.
