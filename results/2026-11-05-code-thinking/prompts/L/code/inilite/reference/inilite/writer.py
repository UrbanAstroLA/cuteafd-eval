from .values import format_scalar, format_value, is_name


def _check_value(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, (list, dict)):
                raise TypeError("lists may only hold scalars")
            format_scalar(x)
        return
    format_scalar(v)


def _emit(d, path, lines):
    subs = []
    for k, v in d.items():
        if not is_name(k):
            raise ValueError(f"invalid key {k!r}")
        if isinstance(v, dict):
            subs.append((k, v))
        else:
            _check_value(v)
            lines.append(f"{k} = {format_value(v)}")
    for k, v in subs:
        if lines:
            lines.append("")
        lines.append("[" + ".".join(path + [k]) + "]")
        _emit(v, path + [k], lines)


def dumps(data):
    if not isinstance(data, dict):
        raise TypeError("data must be a dict")
    lines = []
    _emit(data, [], lines)
    return "".join(line + "\n" for line in lines)


def dump(data, path):
    text = dumps(data)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
