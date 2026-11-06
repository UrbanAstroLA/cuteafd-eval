from .engine import match_at
from .errors import RegexError
from .parser import parse


class Match:
    def __init__(self, string, spans):
        self.string = string
        self._spans = spans

    def _span(self, n):
        if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n < len(self._spans):
            raise IndexError(f"no such group: {n!r}")
        return self._spans[n]

    def _text(self, n):
        sp = self._span(n)
        return None if sp is None else self.string[sp[0]:sp[1]]

    def group(self, *indices):
        if not indices:
            return self._text(0)
        if len(indices) == 1:
            return self._text(indices[0])
        return tuple(self._text(n) for n in indices)

    def groups(self):
        return tuple(self._text(n) for n in range(1, len(self._spans)))

    def span(self, n=0):
        sp = self._span(n)
        return (-1, -1) if sp is None else sp

    def start(self, n=0):
        return self.span(n)[0]

    def end(self, n=0):
        return self.span(n)[1]

    def __repr__(self):
        return f"<regexlite.Match span={self.span()} match={self.group()!r}>"


def _parse_template(repl, ngroups):
    parts, buf, i = [], [], 0
    while i < len(repl):
        c = repl[i]
        if c != "\\":
            buf.append(c)
            i += 1
            continue
        if i + 1 >= len(repl):
            raise RegexError("trailing backslash in template", i)
        d = repl[i + 1]
        if d == "\\":
            buf.append("\\")
        elif d in "0123456789":
            g = int(d)
            if g > ngroups:
                raise RegexError(f"invalid group reference {g}", i)
            if buf:
                parts.append("".join(buf))
                buf = []
            parts.append(g)
        else:
            raise RegexError(f"bad template escape \\{d}", i)
        i += 2
    if buf:
        parts.append("".join(buf))
    return parts


class Pattern:
    def __init__(self, pattern):
        self.pattern = pattern
        self._tree, self.groups = parse(pattern)

    def _at(self, s, i, require_end=False):
        spans = match_at(self._tree, self.groups, s, i, require_end)
        return None if spans is None else Match(s, spans)

    def match(self, s, pos=0):
        if pos < 0 or pos > len(s):
            return None
        return self._at(s, pos)

    def search(self, s, pos=0):
        for i in range(max(pos, 0), len(s) + 1):
            m = self._at(s, i)
            if m is not None:
                return m
        return None

    def fullmatch(self, s):
        return self._at(s, 0, require_end=True)

    def finditer(self, s):
        pos = 0
        while pos <= len(s):
            m = self.search(s, pos)
            if m is None:
                return
            yield m
            st, e = m.span()
            pos = e + 1 if st == e else e

    def findall(self, s):
        out = []
        for m in self.finditer(s):
            if self.groups == 0:
                out.append(m.group())
            elif self.groups == 1:
                out.append(m.group(1) or "")
            else:
                out.append(tuple(g or "" for g in m.groups()))
        return out

    def sub(self, repl, s, count=0):
        if callable(repl):
            render = repl
        else:
            parts = _parse_template(repl, self.groups)

            def render(m):
                return "".join(p if isinstance(p, str) else (m.group(p) or "") for p in parts)

        out, last, done = [], 0, 0
        for m in self.finditer(s):
            if count > 0 and done >= count:
                break
            st, e = m.span()
            out.append(s[last:st])
            out.append(render(m))
            last = e
            done += 1
        out.append(s[last:])
        return "".join(out)

    def __repr__(self):
        return f"regexlite.compile({self.pattern!r})"


def compile(pattern):  # noqa: A001 - mirrors the conventional name
    return Pattern(pattern)


def match(pattern, s):
    return compile(pattern).match(s)


def search(pattern, s):
    return compile(pattern).search(s)


def fullmatch(pattern, s):
    return compile(pattern).fullmatch(s)


def findall(pattern, s):
    return compile(pattern).findall(s)


def sub(pattern, repl, s, count=0):
    return compile(pattern).sub(repl, s, count)
