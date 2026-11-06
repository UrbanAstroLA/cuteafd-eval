Build a Python package named `textdiff`: a line-based diff that writes unified-diff text, a parser for that format, and a strict patch applier. Python 3.12, standard library only.

## Files

- `textdiff/__init__.py` — re-exports `split_lines`, `diff_lines`, `unified_diff`, `Hunk`, `parse_patch`, `apply_patch`, `DiffError`, `PatchFormatError`, `PatchConflict`.
- `textdiff/errors.py` — the exception classes.
- `textdiff/lcs.py` — `split_lines` and `diff_lines`.
- `textdiff/unified.py` — `unified_diff`.
- `textdiff/patch.py` — `Hunk`, `parse_patch`, `apply_patch`.

## errors.py

- `DiffError(Exception)` — base class.
- `PatchFormatError(DiffError)` — `PatchFormatError(message, line)`; attribute `line` is a 1-based line number in the patch text.
- `PatchConflict(DiffError)` — `PatchConflict(hunk, line)`; attributes `hunk` (1-based index of the failing hunk) and `line` (1-based line number in the text being patched of the first mismatch). `str(err)` contains both numbers.

## lcs.py

- `split_lines(text) -> list[str]` — split on `"\n"` only, keeping it: `"a\nb"` → `["a\n", "b"]`, `"a\n"` → `["a\n"]`, `""` → `[]`. `"\r"` is ordinary content. Lines are always compared with their terminator, so `"x"` and `"x\n"` differ.
- `diff_lines(a, b) -> list[tuple[str, str]]` — `a`, `b` are lists of strings. Returns `(tag, line)` pairs: `" "` (in both), `"-"` (only in `a`), `"+"` (only in `b`), exactly as produced by: let `L[i][j]` be the length of a longest common subsequence of `a[i:]` and `b[j:]`; from `i = j = 0`, while both have lines left: if `a[i] == b[j]` emit `(" ", a[i])` and advance both; elif `L[i+1][j] >= L[i][j+1]` emit `("-", a[i])` and advance `i`; else emit `("+", b[j])` and advance `j`. Then emit the rest of `a` as `"-"` and the rest of `b` as `"+"`.

## unified.py

`unified_diff(old, new, from_name="a", to_name="b", context=3) -> str` compares two texts split with `split_lines`. Negative `context` raises `ValueError`. Equal texts give `""`. Otherwise: the line `--- <from_name>`, the line `+++ <to_name>`, then the hunks.

Hunks come from the `diff_lines` script. A *change* is a `"-"` or `"+"` entry. Consecutive changes share a hunk when the run of `" "` entries between them is at most `2 * context` long; a longer run starts a new hunk. A hunk holds its changes, the entries between them, and up to `context` `" "` entries before its first and after its last change.

Each hunk starts with `@@ -<old range> +<new range> @@`. For a side whose hunk lines (context and `-` for old; context and `+` for new) start at 0-based index `s` of that file and number `n`, the range is `str(s + 1)` if `n == 1`, `f"{s},0"` if `n == 0` (`s` = that file's lines before the hunk), else `f"{s + 1},{n}"`. Then one line per entry: tag character plus line. Every output line ends with `"\n"`; a line without terminator is followed by the line `\ No newline at end of file`.

## patch.py

`Hunk` is a dataclass: `old_start`, `old_count`, `new_start`, `new_count` (ints), `lines` (list of `(tag, line)`, tags `" "`/`"-"`/`"+"`, each line with its `"\n"` unless it has none).

`parse_patch(patch) -> list[Hunk]`. `""` gives `[]`. Otherwise split on `"\n"`, dropping the empty piece after a trailing `"\n"`; line numbers refer to these pieces.

- Line 1 must start with `"--- "`, line 2 with `"+++ "`; names are ignored.
- Then one or more hunks. A header matches `@@ -A[,B] +C[,D] @@`, optionally followed by a space and any text; an omitted count is 1. Body lines follow until exactly `B` lines tagged `" "`/`"-"` and `D` tagged `" "`/`"+"` are read. A body line's first character is its tag; its content is the rest plus `"\n"`. A line starting with `\` directly after a body line removes that line's `"\n"`. After a body only a header or the end may follow.
- A side with count 0 is an insertion point after line `A` (or `C`); otherwise it starts at line `A` (or `C`), which must be at least 1. On each side, each hunk must start at or after the end of the previous hunk.

Violations raise `PatchFormatError` with the offending line's number: missing/malformed header lines, an unknown tag, a `\` line not directly after a body line, a body line beyond either count, a start of 0 with a non-zero count, out-of-order or overlapping hunks (the header's line). A body cut short by the end, or a patch with no hunks, reports the number of lines plus one.

`apply_patch(text, patch, reverse=False) -> str` applies every hunk of `parse_patch(patch)` to `split_lines(text)` and returns the joined result. A hunk's old lines (`" "` and `"-"`, in order) must equal the text's lines at its old position exactly; no offset search, no fuzz. Positions refer to the original text. The first mismatch raises `PatchConflict`; when the text ends first (including an insertion point past the end), `line` is its line count plus one. With `reverse=True` the new side (`C`, `D`, `" "` and `"+"`) must match and is replaced by the old side. Applying `""` returns `text`.

For any texts `a`, `b` and `context >= 0`: `apply_patch(a, unified_diff(a, b, context=context)) == b` and `apply_patch(b, unified_diff(a, b, context=context), reverse=True) == a`.
