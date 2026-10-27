Build a Python package named `csvreport`: typed CSV reading, grouping with aggregates, and fixed-width table rendering. Python 3.12, standard library only.

## Files

- `csvreport/__init__.py` — re-exports `Column`, `Schema`, `read_rows`, `group_by`, `render_table`, `ReportError`, `SchemaError`, `RowError`.
- `csvreport/errors.py` — the exception classes.
- `csvreport/schema.py` — `Column`, `Schema`, and value parsing.
- `csvreport/reader.py` — `read_rows`.
- `csvreport/aggregate.py` — `group_by`.
- `csvreport/table.py` — `render_table`.

## errors.py

- `ReportError(Exception)` — base class.
- `SchemaError(ReportError)` — for header problems. Attribute `missing`: sorted list of missing column names.
- `RowError(ReportError)` — `RowError(line, column, message)` with attributes `line` (int), `column` (str) and `message` (str). `str(err)` contains the line number and the column name.

## schema.py

- `Column(name, type, required=True)` — a frozen dataclass. `type` is one of `"int"`, `"float"`, `"str"`, `"bool"`, `"date"`; any other value raises `ValueError` at construction.
- `Schema(columns)` — holds a list of `Column`; duplicate names raise `ValueError`. Attribute `columns` (list) and method `names()` (list of names in order).
- `parse_value(column, text)` — convert one cell, after stripping surrounding whitespace:
  - empty text: `None` if the column is not required, otherwise raise `ValueError("required")`;
  - `int`: Python `int(text)` (so `"+3"` and `"-0"` are accepted, `"3.0"` is not);
  - `float`: Python `float(text)`, but `nan` and `inf` in any spelling are rejected;
  - `str`: the stripped text;
  - `bool`: case-insensitive `true`/`yes`/`1` → `True`, `false`/`no`/`0` → `False`, anything else invalid;
  - `date`: exactly `YYYY-MM-DD` → `datetime.date` (`date.fromisoformat` on a 10-character string matching that shape).
  - Invalid input raises `ValueError`.

## reader.py

`read_rows(text, schema) -> list[dict]` parses `text` with the `csv` module (default dialect). The first record is the header; header names are stripped of surrounding whitespace. If any schema column is absent from the header, raise `SchemaError` with the sorted missing names. Columns not in the schema are ignored; schema columns may appear in any order. Each data record becomes a dict whose keys are the schema names in schema order and whose values come from `parse_value`. Records that are completely empty (every cell blank, or a blank line) are skipped. A record with fewer cells than the header treats the missing cells as empty. A conversion failure raises `RowError(line, column_name, message)` where `line` is the `csv.reader`'s `line_num` after reading that record (the header is line 1).

## aggregate.py

`group_by(rows, keys, aggregations) -> list[dict]`.

- `keys` is a list of column names; `aggregations` is a dict mapping an output name to a `(function, column)` pair, function one of `"count"`, `"sum"`, `"mean"`, `"min"`, `"max"`. Any other function raises `ValueError`.
- Rows are grouped by the tuple of their key values. The output has one dict per group, containing the key columns followed by the aggregation outputs in `aggregations` order.
- Groups are sorted by their key tuple, where within each position `None` sorts before every other value.
- `("count", None)` counts rows in the group; `("count", col)` counts rows where `col` is not `None`.
- `sum`, `mean`, `min`, `max` ignore `None`; if every value is `None` (or the group has none) the result is `None`. `mean` returns a `float`. `sum` of ints is an int.
- `keys=[]` produces exactly one group holding all rows (even when `rows` is empty, with `count` 0).

## table.py

`render_table(rows, columns, float_digits=2) -> str` renders a list of dicts as a text table showing `columns` (a list of names) in that order.

- Cell text: `None` → `""`; `bool` → `"true"`/`"false"`; `float` → `f"{x:.{float_digits}f}"`; `datetime.date` → ISO format; anything else → `str(x)`. A missing key counts as `None`.
- A column is numeric when it has at least one non-`None` value and all its non-`None` values are `int` or `float` (not `bool`). Numeric columns are right-aligned, all others left-aligned, and the header follows its column's alignment.
- Column width is the longest of the header and its cells.
- Output lines: the header line, a separator line, then one line per row. Cells are joined with `" | "`; the separator line is, for each column, `"-"` repeated to its width, joined with `"-+-"`. Every line has trailing whitespace removed. Lines are joined with `"\n"`, with no trailing newline.
