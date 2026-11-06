Build a Python package named `mdtable`: Markdown pipe tables — parsing, operations, formatting and CSV conversion. Python 3.12, standard library only.

## Files

- `mdtable/__init__.py` — re-exports `Table`, `TableError`, `parse`, `split_row`, `format_table`, `to_csv`, `from_csv`, `display_width`.
- `mdtable/errors.py` — `TableError(Exception)`: `TableError(message, line)` stores the 1-based line number as `line`; `str(err)` contains the message and the line number.
- `mdtable/width.py` — `display_width`.
- `mdtable/parser.py` — `split_row` and `parse`.
- `mdtable/table.py` — `Table`.
- `mdtable/render.py` — `format_table`, `to_csv`, `from_csv`.

## width.py

`display_width(text) -> int` sums per character: 0 if `unicodedata.combining(ch)` is non-zero; otherwise 2 if `unicodedata.east_asian_width(ch)` is `"W"` or `"F"`; otherwise 1.

## parser.py

`split_row(line) -> list[str]` strips surrounding whitespace from `line`, then scans it left to right:

- A backslash immediately followed by `|` is an escaped pipe: the pair becomes a literal `|` in the cell. Every other backslash is kept as is.
- A run of N backticks opens a code span if a later run of exactly N backticks exists on the line; the span ends after that closing run. The span's text (backticks included) is copied into the cell verbatim, except that escaped pipes become `|`; a `|` inside a span never separates cells. A backtick run with no matching closing run is literal text.
- Any other `|` is a separator.

Separators split the line into pieces. If the stripped line begins with a separator, the first piece is dropped; then, if it ends with a separator and more than one piece remains, the last piece is dropped. Remaining pieces are stripped of surrounding whitespace.

`parse(text) -> Table` splits `text` with `str.splitlines()`. Leading and trailing blank (whitespace-only) lines are ignored. The first remaining line is the header row, the second the delimiter row, the rest are body rows. Errors raise `TableError` with `line` counted over all lines of `text`, checked in this order:

1. no non-blank line: `line` 1;
2. a blank line between the first and last non-blank lines: that line;
3. duplicate header names: the header line;
4. no delimiter row: the header line number + 1;
5. a delimiter cell not matching `:?-+:?`: the delimiter line;
6. delimiter cell count different from header cell count: the delimiter line.

A delimiter cell gives the column alignment: starting and ending with `:` is `"center"`, only starting with `:` is `"left"`, only ending with `:` is `"right"`, no colon is `None`. Body rows with fewer cells than the header are padded with `""`; extra cells are dropped.

## table.py

`Table(headers, rows, aligns=None)` — `headers`: list of strings; `rows`: list of lists of strings; `aligns`: list of `None`/`"left"`/`"right"`/`"center"` (default all `None`). Copies are stored as attributes `headers`, `rows`, `aligns`. Raises `ValueError` for duplicate headers, a row whose length differs from `len(headers)`, or `aligns` of the wrong length or with another value. Tables compare equal (`==`) when headers, rows and aligns are all equal.

Methods (new tables are returned, `self` is never modified; an unknown column name raises `KeyError`):

- `column(name) -> list[str]`; `records() -> list[dict]` mapping header to cell, one per row.
- `select(names)` — those columns in the given order, with their aligns; repeated names raise `ValueError`.
- `filter(predicate)` — rows whose record dict makes `predicate` truthy, order kept.
- `sort(by, descending=False)` — `by` is a column name or a list of names (first name is the primary key). The sort is stable. Per key: a cell matching `[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?` is a number and compares by `float(cell)`; numbers sort before other non-empty text; other text compares by `(cell.casefold(), cell)`. `descending=True` reverses this order (text before numbers) but keeps equal cells in their original order. Empty cells sort after all others in both directions.

## render.py

`format_table(table) -> str`:

- Each header and cell is escaped: every `|` outside a code span (as defined for `split_row`, applied to that text alone) becomes `\|`. Nothing else is escaped.
- Column width is the largest `display_width` of the escaped header and cells, and at least 3.
- Text is padded with `gap` spaces (column width minus its display width): `"right"` pads on the left; `"center"` puts `gap // 2` on the left and the rest on the right; `"left"` and `None` pad on the right. Headers use their column's alignment.
- Delimiter cells have exactly the column width: `None` → all `-`; `"left"` → `:` then `-`; `"right"` → `-` then `:`; `"center"` → `:`, `-`, `:`.
- Every line is `"| " + " | ".join(cells) + " |"`: header line, delimiter line, one line per row. Each line ends with `"\n"`.

For tables whose cells contain no backslash, no leading/trailing whitespace or line break, and whose backticks all form code spans within their cell, `parse(format_table(t)) == t`.

`to_csv(table) -> str` writes headers then rows with `csv.writer` (default dialect, `lineterminator="\n"`).

`from_csv(text) -> Table` reads with `csv.reader`, skipping records with no fields (blank lines). The first record is the headers; rows are padded or truncated to the header length as in `parse`; all aligns are `None`. No records, or duplicate headers, raise `TableError` with `line` 1.
