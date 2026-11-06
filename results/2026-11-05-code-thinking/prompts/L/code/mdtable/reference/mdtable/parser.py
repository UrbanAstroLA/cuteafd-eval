import re

from .errors import TableError
from .table import Table

_DELIM = re.compile(r":?-+:?")


def _code_span_end(s, i):
    """If a backtick run starts at i, return (run_len, index just past the closing run) or (run_len, None)."""
    j = i
    while j < len(s) and s[j] == "`":
        j += 1
    n = j - i
    k = j
    while k < len(s):
        if s[k] == "`":
            m = k
            while m < len(s) and s[m] == "`":
                m += 1
            if m - k == n:
                return n, m
            k = m
        else:
            k += 1
    return n, None


def scan(s):
    """Return (pieces, separator_positions) for a stripped line."""
    pieces, seps, cur, i = [], [], [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
        elif c == "`":
            n, end = _code_span_end(s, i)
            if end is None:
                cur.append(s[i:i + n])
                i += n
            else:
                cur.append(s[i:end].replace("\\|", "|"))
                i = end
        elif c == "|":
            seps.append(i)
            pieces.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(c)
            i += 1
    pieces.append("".join(cur))
    return pieces, seps


def split_row(line):
    s = line.strip()
    pieces, seps = scan(s)
    if seps and seps[0] == 0:
        pieces = pieces[1:]
    if seps and seps[-1] == len(s) - 1 and len(pieces) > 1:
        pieces = pieces[:-1]
    return [p.strip() for p in pieces]


def _align(cell, lineno):
    if not _DELIM.fullmatch(cell):
        raise TableError(f"invalid delimiter cell {cell!r}", lineno)
    left, right = cell.startswith(":"), cell.endswith(":")
    if left and right:
        return "center"
    if left:
        return "left"
    if right:
        return "right"
    return None


def parse(text):
    lines = text.splitlines()
    numbered = [(i + 1, ln) for i, ln in enumerate(lines)]
    while numbered and not numbered[0][1].strip():
        numbered.pop(0)
    while numbered and not numbered[-1][1].strip():
        numbered.pop()
    if not numbered:
        raise TableError("no table", 1)
    for no, ln in numbered:
        if not ln.strip():
            raise TableError("blank line inside table", no)
    hno, hline = numbered[0]
    headers = split_row(hline)
    if len(set(headers)) != len(headers):
        raise TableError("duplicate header", hno)
    if len(numbered) < 2:
        raise TableError("missing delimiter row", hno + 1)
    dno, dline = numbered[1]
    dcells = split_row(dline)
    aligns = [_align(c, dno) for c in dcells]
    if len(dcells) != len(headers):
        raise TableError("delimiter row does not match header", dno)
    rows = []
    for _, ln in numbered[2:]:
        cells = split_row(ln)[:len(headers)]
        cells += [""] * (len(headers) - len(cells))
        rows.append(cells)
    return Table(headers, rows, aligns)
