import csv
import io

from .errors import RowError, SchemaError
from .schema import parse_value


def read_rows(text, schema):
    rd = csv.reader(io.StringIO(text))
    try:
        header = [h.strip() for h in next(rd)]
    except StopIteration:
        header = []
    missing = [n for n in schema.names() if n not in header]
    if missing:
        raise SchemaError(missing)
    pos = {c.name: header.index(c.name) for c in schema.columns}
    out = []
    for rec in rd:
        if all(cell.strip() == "" for cell in rec):
            continue
        row = {}
        for c in schema.columns:
            i = pos[c.name]
            cell = rec[i] if i < len(rec) else ""
            try:
                row[c.name] = parse_value(c, cell)
            except ValueError as e:
                raise RowError(rd.line_num, c.name, str(e)) from None
        out.append(row)
    return out
