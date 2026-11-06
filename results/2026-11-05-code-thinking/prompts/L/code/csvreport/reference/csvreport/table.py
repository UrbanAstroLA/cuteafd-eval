import datetime


def _cell(x, digits):
    if x is None:
        return ""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    if isinstance(x, datetime.date):
        return x.isoformat()
    return str(x)


def _numeric(vals):
    present = [v for v in vals if v is not None]
    return bool(present) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present)


def render_table(rows, columns, float_digits=2):
    cols = []
    for name in columns:
        vals = [r.get(name) for r in rows]
        texts = [_cell(v, float_digits) for v in vals]
        width = max([len(name)] + [len(t) for t in texts])
        cols.append((name, texts, width, _numeric(vals)))

    def fmt(t, w, right):
        return t.rjust(w) if right else t.ljust(w)

    lines = [" | ".join(fmt(n, w, r) for n, _, w, r in cols),
             "-+-".join("-" * w for _, _, w, _ in cols)]
    for i in range(len(rows)):
        lines.append(" | ".join(fmt(t[i], w, r) for _, t, w, r in cols))
    return "\n".join(line.rstrip() for line in lines)
