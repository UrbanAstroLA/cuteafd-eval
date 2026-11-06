"""Pattern string -> tree of tuples:
("char", predicate) ("bol",) ("eol",) ("seq", [nodes]) ("alt", [nodes])
("group", index | None, node) ("rep", node, lo, hi | None, greedy)
"""
from .errors import RegexError

_DIGITS = frozenset("0123456789")
_WORD = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_SPACE = frozenset(" \t\n\r\f\v")
_CLASS_ESC = {"d": (_DIGITS, False), "D": (_DIGITS, True), "w": (_WORD, False), "W": (_WORD, True),
              "s": (_SPACE, False), "S": (_SPACE, True)}
_CHAR_ESC = {"n": "\n", "t": "\t"}


def _in_class(cls, c):
    chars, neg = cls
    return (c in chars) != neg


class _Parser:
    def __init__(self, pattern):
        self.p = pattern
        self.n = len(pattern)
        self.i = 0
        self.ngroups = 0

    def peek(self):
        return self.p[self.i] if self.i < self.n else None

    def parse(self):
        node = self.alternation()
        if self.i < self.n:  # only a stray ')' can stop the top level early
            raise RegexError("unmatched ')'", self.i)
        return node

    def alternation(self):
        branches = [self.sequence()]
        while self.peek() == "|":
            self.i += 1
            branches.append(self.sequence())
        return branches[0] if len(branches) == 1 else ("alt", branches)

    def sequence(self):
        items = []
        can_repeat = False
        while self.i < self.n and self.p[self.i] not in "|)":
            c = self.p[self.i]
            if c in "*+?{":
                qpos = self.i
                if not can_repeat:
                    raise RegexError("nothing to repeat", qpos)
                lo, hi = self.quantifier()
                greedy = True
                if self.peek() == "?":
                    greedy = False
                    self.i += 1
                items[-1] = ("rep", items[-1], lo, hi, greedy)
                can_repeat = False
                continue
            if c == "^" or c == "$":
                items.append(("bol",) if c == "^" else ("eol",))
                self.i += 1
                can_repeat = False
                continue
            items.append(self.atom())
            can_repeat = True
        return items[0] if len(items) == 1 else ("seq", items)

    def quantifier(self):
        c = self.p[self.i]
        if c != "{":
            self.i += 1
            return {"*": (0, None), "+": (1, None), "?": (0, 1)}[c]
        start = self.i
        j = start + 1
        k = j
        while k < self.n and self.p[k] in _DIGITS:
            k += 1
        if k == j:
            raise RegexError("invalid quantifier", start)
        lo = int(self.p[j:k])
        if k < self.n and self.p[k] == "}":
            self.i = k + 1
            return lo, lo
        if k >= self.n or self.p[k] != ",":
            raise RegexError("invalid quantifier", start)
        k += 1
        m = k
        while m < self.n and self.p[m] in _DIGITS:
            m += 1
        if m >= self.n or self.p[m] != "}":
            raise RegexError("invalid quantifier", start)
        hi = int(self.p[k:m]) if m > k else None
        if hi is not None and hi < lo:
            raise RegexError("invalid quantifier range", start)
        self.i = m + 1
        return lo, hi

    def escape(self, i):
        """Read an escape at self.p[i] == '\\'. Return (kind, value, next_index)."""
        if i + 1 >= self.n:
            raise RegexError("trailing backslash", i)
        d = self.p[i + 1]
        if d in _CLASS_ESC:
            return "cls", _CLASS_ESC[d], i + 2
        if d in _CHAR_ESC:
            return "char", _CHAR_ESC[d], i + 2
        if d.isascii() and d.isalnum():
            raise RegexError(f"bad escape \\{d}", i)
        return "char", d, i + 2

    def atom(self):
        c = self.p[self.i]
        if c == ".":
            self.i += 1
            return ("char", lambda ch: ch != "\n")
        if c == "\\":
            kind, val, self.i = self.escape(self.i)
            if kind == "cls":
                return ("char", lambda ch, cls=val: _in_class(cls, ch))
            return ("char", lambda ch, v=val: ch == v)
        if c == "[":
            return self.char_class()
        if c == "(":
            return self.group()
        self.i += 1
        return ("char", lambda ch, v=c: ch == v)

    def group(self):
        start = self.i
        if self.p[start + 1:start + 2] == "?":
            if self.p[start + 2:start + 3] != ":":
                raise RegexError("unknown group extension", start)
            self.i = start + 3
            index = None
        else:
            self.ngroups += 1
            index = self.ngroups
            self.i = start + 1
        inner = self.alternation()
        if self.i >= self.n:
            raise RegexError("missing ')'", start)
        self.i += 1
        return ("group", index, inner)

    def class_item(self, i):
        if self.p[i] == "\\":
            return self.escape(i)
        return "char", self.p[i], i + 1

    def char_class(self):
        start = self.i
        i = start + 1
        neg = False
        if i < self.n and self.p[i] == "^":
            neg = True
            i += 1
        chars, ranges, classes = set(), [], []
        first = True
        while True:
            if i >= self.n:
                raise RegexError("unterminated character class", start)
            if self.p[i] == "]" and not first:
                i += 1
                break
            first = False
            item_pos = i
            kind, val, i = self.class_item(i)
            if kind == "char" and i + 1 < self.n and self.p[i] == "-" and self.p[i + 1] != "]":
                end_pos = i + 1
                kind2, val2, i = self.class_item(end_pos)
                if kind2 == "cls":
                    raise RegexError("bad range end", end_pos)
                if val > val2:
                    raise RegexError("bad range", item_pos)
                ranges.append((val, val2))
            elif kind == "char":
                chars.add(val)
            else:
                classes.append(val)
        self.i = i
        chars = frozenset(chars)

        def pred(ch):
            hit = ch in chars or any(lo <= ch <= hi for lo, hi in ranges) or any(_in_class(c, ch) for c in classes)
            return hit != neg

        return ("char", pred)


def parse(pattern):
    """Return (tree, number_of_groups)."""
    p = _Parser(pattern)
    tree = p.parse()
    return tree, p.ngroups
