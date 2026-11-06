import csv
import io

from .errors import TableError
from .parser import _code_span_end
from .table import Table
from .width import display_width


def escape_cell(text):
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "`":
            n, end = _code_span_end(text, i)
            if end is None:
                out.append(text[i:i + n])
                i += n
            else:
                out.append(text[i:end])
                i = end
        elif c == "|":
            out.append("\\|")
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _pad(text, width, align):
    gap = width - display_width(text)
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def _delim(width, align):
    if align == "left":
        return ":" + "-" * (width - 1)
    if align == "right":
        return "-" * (width - 1) + ":"
    if align == "center":
        return ":" + "-" * (width - 2) + ":"
    return "-" * width


def format_table(table):
    head = [escape_cell(h) for h in table.headers]
    body = [[escape_cell(c) for c in r] for r in table.rows]
    widths = []
    for j in range(len(head)):
        widths.append(max([3, display_width(head[j])] + [display_width(r[j]) for r in body]))

    def line(cells):
        return "| " + " | ".join(cells) + " |"

    lines = [line([_pad(h, w, a) for h, w, a in zip(head, widths, table.aligns)]),
             line([_delim(w, a) for w, a in zip(widths, table.aligns)])]
    for r in body:
        lines.append(line([_pad(c, w, a) for c, w, a in zip(r, widths, table.aligns)]))
    return "\n".join(lines) + "\n"


def to_csv(table):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(table.headers)
    w.writerows(table.rows)
    return buf.getvalue()


def from_csv(text):
    records = [r for r in csv.reader(io.StringIO(text)) if r]
    if not records:
        raise TableError("empty CSV", 1)
    headers = records[0]
    if len(set(headers)) != len(headers):
        raise TableError("duplicate header", 1)
    n = len(headers)
    rows = [(r[:n] + [""] * (n - len(r))) for r in records[1:]]
    return Table(headers, rows)
