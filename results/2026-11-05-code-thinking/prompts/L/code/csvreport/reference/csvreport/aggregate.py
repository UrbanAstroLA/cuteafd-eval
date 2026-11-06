FUNCS = ("count", "sum", "mean", "min", "max")


def _sort_key(key):
    return tuple((0,) if v is None else (1, v) for v in key)


def group_by(rows, keys, aggregations):
    for out_name, (fn, col) in aggregations.items():
        if fn not in FUNCS:
            raise ValueError(f"unknown function {fn!r}")
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r.get(k) for k in keys), []).append(r)
    if not keys and not groups:
        groups[()] = []
    result = []
    for key in sorted(groups, key=_sort_key):
        members = groups[key]
        d = dict(zip(keys, key))
        for out_name, (fn, col) in aggregations.items():
            if fn == "count":
                d[out_name] = len(members) if col is None else sum(1 for m in members if m.get(col) is not None)
                continue
            vals = [m.get(col) for m in members if m.get(col) is not None]
            if not vals:
                d[out_name] = None
            elif fn == "sum":
                d[out_name] = sum(vals)
            elif fn == "mean":
                d[out_name] = float(sum(vals)) / len(vals)
            elif fn == "min":
                d[out_name] = min(vals)
            else:
                d[out_name] = max(vals)
        result.append(d)
    return result
