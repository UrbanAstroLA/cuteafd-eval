import re
from dataclasses import dataclass, field

from .errors import PatchConflict, PatchFormatError
from .lcs import split_lines

_HEADER = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?")


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list = field(default_factory=list)


def _span(start, count):
    """0-based [begin, end) of a side of a hunk."""
    b = start if count == 0 else start - 1
    return b, b + count


def parse_patch(patch):
    if patch == "":
        return []
    pieces = patch.split("\n")
    if pieces and pieces[-1] == "" and patch.endswith("\n"):
        pieces.pop()
    n = len(pieces)
    if n < 1 or not pieces[0].startswith("--- "):
        raise PatchFormatError("expected '--- ' header", 1)
    if n < 2 or not pieces[1].startswith("+++ "):
        raise PatchFormatError("expected '+++ ' header", 2)
    hunks, k = [], 2
    prev_end = [0, 0]
    while k < n:
        lineno = k + 1
        m = _HEADER.fullmatch(pieces[k])
        if not m:
            raise PatchFormatError("expected hunk header", lineno)
        a, b, c, d = (int(x) if x is not None else 1 for x in m.groups())
        for start, count in ((a, b), (c, d)):
            if count > 0 and start == 0:
                raise PatchFormatError("start 0 with non-zero count", lineno)
        spans = (_span(a, b), _span(c, d))
        for side in (0, 1):
            if spans[side][0] < prev_end[side]:
                raise PatchFormatError("hunks out of order or overlapping", lineno)
        h = Hunk(a, b, c, d, [])
        k += 1
        seen_old = seen_new = 0
        last_body = False
        while seen_old < b or seen_new < d or (k < n and pieces[k].startswith("\\") and last_body):
            if k >= n:
                raise PatchFormatError("hunk body cut short", n + 1)
            s = pieces[k]
            tag = s[:1]
            if tag == "\\":
                if not last_body:
                    raise PatchFormatError("'\\' line does not follow a body line", k + 1)
                t, text = h.lines[-1]
                h.lines[-1] = (t, text[:-1])
                last_body = False
            elif tag in (" ", "-", "+"):
                if tag != "+":
                    seen_old += 1
                if tag != "-":
                    seen_new += 1
                if seen_old > b or seen_new > d:
                    raise PatchFormatError("body line beyond hunk counts", k + 1)
                h.lines.append((tag, s[1:] + "\n"))
                last_body = True
            else:
                raise PatchFormatError(f"unknown body tag {tag!r}", k + 1)
            k += 1
        prev_end = [spans[0][1], spans[1][1]]
        hunks.append(h)
    if not hunks:
        raise PatchFormatError("patch has no hunks", n + 1)
    return hunks


def apply_patch(text, patch, reverse=False):
    hunks = parse_patch(patch)
    src = split_lines(text)
    out, cur = [], 0
    for idx, h in enumerate(hunks, 1):
        if reverse:
            start, count = h.new_start, h.new_count
            want = [x for t, x in h.lines if t != "-"]
            give = [x for t, x in h.lines if t != "+"]
        else:
            start, count = h.old_start, h.old_count
            want = [x for t, x in h.lines if t != "+"]
            give = [x for t, x in h.lines if t != "-"]
        begin, end = _span(start, count)
        if begin > len(src):
            raise PatchConflict(idx, len(src) + 1)
        for i, w in enumerate(want):
            p = begin + i
            if p >= len(src):
                raise PatchConflict(idx, len(src) + 1)
            if src[p] != w:
                raise PatchConflict(idx, p + 1)
        out.extend(src[cur:begin])
        out.extend(give)
        cur = end
    out.extend(src[cur:])
    return "".join(out)
