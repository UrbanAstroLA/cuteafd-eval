from .errors import DuplicateKeyError, ParseError
from .values import NAME_CHARS, is_name, scan_value


def _rest_ok(rest):
    rest = rest.lstrip(" \t")
    return rest == "" or rest[0] in "#;"


def loads(text):
    root = {}
    current = root
    for lineno, raw in enumerate(text.split("\n"), start=1):
        if raw.endswith("\r"):
            raw = raw[:-1]
        line = raw.strip(" \t")
        if not line or line[0] in "#;":
            continue
        if line[0] == "[":
            k = line.find("]")
            if k < 0:
                raise ParseError("unterminated section header", lineno)
            parts = line[1:k].strip(" \t").split(".")
            if not all(is_name(p) for p in parts):
                raise ParseError("invalid section name", lineno)
            if not _rest_ok(line[k + 1:]):
                raise ParseError("unexpected text after section header", lineno)
            node = root
            for p in parts:
                if p in node:
                    if not isinstance(node[p], dict):
                        raise DuplicateKeyError(f"{p!r} is already a value", lineno)
                else:
                    node[p] = {}
                node = node[p]
            current = node
            continue
        j = 0
        while j < len(line) and line[j] in NAME_CHARS:
            j += 1
        if j == 0:
            raise ParseError("expected a key", lineno)
        key = line[:j]
        while j < len(line) and line[j] in " \t":
            j += 1
        if line.startswith("+=", j):
            append, j = True, j + 2
        elif line.startswith("=", j):
            append, j = False, j + 1
        else:
            raise ParseError("expected '='", lineno)
        while j < len(line) and line[j] in " \t":
            j += 1
        try:
            value, j = scan_value(line, j)
        except ValueError as e:
            raise ParseError(str(e), lineno) from None
        if not _rest_ok(line[j:]):
            raise ParseError("unexpected text after value", lineno)
        if append:
            if not isinstance(current.get(key), list):
                raise ParseError(f"'+=' needs an existing list for {key!r}", lineno)
            if isinstance(value, list):
                current[key].extend(value)
            else:
                current[key].append(value)
        else:
            if key in current:
                raise DuplicateKeyError(f"duplicate key {key!r}", lineno)
            current[key] = value
    return root


def load(path):
    with open(path, encoding="utf-8") as f:
        return loads(f.read())
