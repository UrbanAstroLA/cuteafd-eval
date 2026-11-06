import re

from .bytecode import MNEMONICS, N_LOCALS, OPCODES, Program
from .errors import AsmError

_LABEL = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*):\s*")
_MNEMONIC = re.compile(r"[A-Za-z]+")
_INT = re.compile(r"[+-]?(?:0x[0-9a-fA-F]+|[0-9]+)")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}


def _parse_int(text):
    neg = text.startswith("-")
    body = text.lstrip("+-")
    v = int(body[2:], 16) if body.startswith("0x") else int(body)
    return -v if neg else v


def _split_operand(rest, lineno):
    """rest: text after the mnemonic. Returns (kind, value) or None; kind is 'str' or 'word'."""
    i, n = 0, len(rest)
    while i < n and rest[i] in " \t\r":
        i += 1
    if i == n or rest[i] == ";":
        return None
    if i == 0:
        raise AsmError("expected whitespace before operand", lineno)
    if rest[i] == '"':
        out, i = [], i + 1
        while True:
            if i >= n:
                raise AsmError("unterminated string", lineno)
            c = rest[i]
            if c == '"':
                i += 1
                break
            if c == "\\":
                if i + 1 >= n or rest[i + 1] not in _ESCAPES:
                    raise AsmError("bad escape", lineno)
                out.append(_ESCAPES[rest[i + 1]])
                i += 2
                continue
            out.append(c)
            i += 1
        kind, value = "str", "".join(out)
    else:
        j = i
        while j < n and rest[j] not in " \t\r;":
            j += 1
        kind, value, i = "word", rest[i:j], j
    tail = rest[i:].lstrip(" \t\r")
    if tail and not tail.startswith(";"):
        raise AsmError("unexpected text after operand", lineno)
    return kind, value


def assemble(source):
    code, strings, labels, fixups = [], [], {}, []
    for lineno, line in enumerate(source.split("\n"), 1):
        pos = 0
        while True:
            m = _LABEL.match(line, pos)
            if not m:
                break
            name = m.group(1)
            if name in labels:
                raise AsmError(f"duplicate label {name!r}", lineno)
            labels[name] = len(code)
            pos = m.end()
        rest = line[pos:].lstrip(" \t\r")
        if not rest or rest.startswith(";"):
            continue
        m = _MNEMONIC.match(rest)
        if not m:
            raise AsmError("syntax error", lineno)
        mnemonic = m.group(0).upper()
        if mnemonic not in MNEMONICS:
            raise AsmError(f"unknown mnemonic {m.group(0)!r}", lineno)
        op = MNEMONICS[mnemonic]
        kind = OPCODES[op][1]
        after = rest[m.end():]
        if after and after[0] not in " \t\r;":
            raise AsmError("syntax error", lineno)
        operand = _split_operand(after, lineno)
        if kind is None:
            if operand is not None:
                raise AsmError(f"{mnemonic} takes no operand", lineno)
            code.append(op)
            continue
        if operand is None:
            raise AsmError(f"{mnemonic} needs an operand", lineno)
        okind, value = operand
        if kind == "int":  # PUSH
            if okind == "str":
                if value not in strings:
                    strings.append(value)
                code += [2, strings.index(value)]
            elif _INT.fullmatch(value):
                code += [1, _parse_int(value)]
            else:
                raise AsmError(f"bad literal {value!r}", lineno)
        elif kind == "addr":
            if okind != "word" or not _IDENT.fullmatch(value):
                raise AsmError("expected a label", lineno)
            code.append(op)
            fixups.append((len(code), value, lineno))
            code.append(0)
        else:  # local
            if okind != "word" or not _INT.fullmatch(value):
                raise AsmError("expected a local index", lineno)
            k = _parse_int(value)
            if not 0 <= k < N_LOCALS:
                raise AsmError(f"local {k} out of range", lineno)
            code += [op, k]
    for idx, name, lineno in fixups:
        if name not in labels:
            raise AsmError(f"undefined label {name!r}", lineno)
        code[idx] = labels[name]
    return Program(tuple(code), tuple(strings))
