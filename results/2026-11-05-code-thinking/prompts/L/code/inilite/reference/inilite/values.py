"""Scanning one value from a line, and formatting one value. Scan errors raise ValueError (the parser adds
the line number)."""
import math

DIGITS = "0123456789"
HEX = "0123456789abcdefABCDEF"
NAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
_TOKEN_END = frozenset(" \t,]#;")
_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r"}


def is_name(s):
    return isinstance(s, str) and s != "" and all(c in NAME_CHARS for c in s)


def _int_body_ok(body):
    if body == "0":
        return True
    return body != "" and body[0] in "123456789" and all(c in DIGITS for c in body)


def _scalar(tok):
    if tok == "true":
        return True
    if tok == "false":
        return False
    body = tok[1:] if tok[:1] in ("+", "-") else tok
    i = 0
    while i < len(body) and body[i] in DIGITS:
        i += 1
    int_part, rest = body[:i], body[i:]
    if not _int_body_ok(int_part):
        raise ValueError(f"invalid value {tok!r}")
    if rest == "":
        return int(tok)
    j = 0
    has_frac = has_exp = False
    if rest[:1] == ".":
        j = 1
        while j < len(rest) and rest[j] in DIGITS:
            j += 1
        if j == 1:
            raise ValueError(f"invalid value {tok!r}")
        has_frac = True
    if j < len(rest) and rest[j] in "eE":
        j += 1
        if j < len(rest) and rest[j] in "+-":
            j += 1
        k = j
        while j < len(rest) and rest[j] in DIGITS:
            j += 1
        if j == k:
            raise ValueError(f"invalid value {tok!r}")
        has_exp = True
    if j != len(rest) or not (has_frac or has_exp):
        raise ValueError(f"invalid value {tok!r}")
    return float(tok)


def _string(s, i):
    out = []
    j = i + 1
    while j < len(s):
        c = s[j]
        if c == '"':
            return "".join(out), j + 1
        if c == "\\":
            d = s[j + 1:j + 2]
            if d in _ESCAPES and d:
                out.append(_ESCAPES[d])
                j += 2
                continue
            if d == "u":
                h = s[j + 2:j + 6]
                if len(h) == 4 and all(x in HEX for x in h):
                    out.append(chr(int(h, 16)))
                    j += 6
                    continue
            raise ValueError("invalid escape")
        out.append(c)
        j += 1
    raise ValueError("unterminated string")


def _skip_ws(s, j):
    while j < len(s) and s[j] in " \t":
        j += 1
    return j


def _list(s, i):
    items = []
    j = _skip_ws(s, i + 1)
    if s[j:j + 1] == "]":
        return items, j + 1
    while True:
        v, j = scan_value(s, j, in_list=True)
        items.append(v)
        j = _skip_ws(s, j)
        c = s[j:j + 1]
        if c == "]":
            return items, j + 1
        if c != ",":
            raise ValueError("expected ',' or ']' in list")
        j = _skip_ws(s, j + 1)


def scan_value(s, i, in_list=False):
    """Scan a value starting at s[i]; return (value, index after it)."""
    c = s[i:i + 1]
    if c == '"':
        return _string(s, i)
    if c == "[":
        if in_list:
            raise ValueError("nested list")
        return _list(s, i)
    j = i
    while j < len(s) and s[j] not in _TOKEN_END:
        j += 1
    if j == i:
        raise ValueError("missing value")
    return _scalar(s[i:j]), j


def _quote(text):
    out = ['"']
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def format_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError("non-finite float")
        return repr(v)
    if isinstance(v, str):
        return _quote(v)
    raise TypeError(f"unsupported value type {type(v).__name__}")


def format_value(v):
    if isinstance(v, list):
        return "[" + ", ".join(format_scalar(x) for x in v) + "]"
    return format_scalar(v)
