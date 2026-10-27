from .ast import Assign, Binary, Bool, Call, Num, Program, Unary, Var
from .errors import ParseError
from .lexer import tokenize

_CMP = ("==", "!=", "<", "<=", ">", ">=")


class _Parser:
    def __init__(self, src):
        self.toks = tokenize(src)
        self.i = 0

    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def is_op(self, *ops, k=0):
        t = self.peek(k)
        return t.kind == "OP" and t.value in ops

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def expect_op(self, op):
        t = self.peek()
        if not (t.kind == "OP" and t.value == op):
            raise ParseError(f"expected {op!r}", t.pos)
        return self.next()

    def program(self):
        stmts = []
        while True:
            while self.is_op(";"):
                self.next()
            if self.peek().kind == "EOF":
                break
            stmts.append(self.statement())
            if self.peek().kind == "EOF":
                break
            self.expect_op(";")
        if not stmts:
            raise ParseError("empty program", self.peek().pos)
        return Program(stmts)

    def statement(self):
        return self.assignment()

    def assignment(self):
        if self.peek().kind == "NAME" and self.is_op("=", k=1):
            name = self.next().value
            self.next()
            return Assign(name, self.assignment())
        node = self.or_expr()
        if self.is_op("="):
            raise ParseError("invalid assignment target", self.peek().pos)
        return node

    def or_expr(self):
        node = self.and_expr()
        while self.is_op("||"):
            self.next()
            node = Binary("||", node, self.and_expr())
        return node

    def and_expr(self):
        node = self.comparison()
        while self.is_op("&&"):
            self.next()
            node = Binary("&&", node, self.comparison())
        return node

    def comparison(self):
        node = self.additive()
        if self.is_op(*_CMP):
            op = self.next().value
            node = Binary(op, node, self.additive())
            if self.is_op(*_CMP):
                raise ParseError("comparison operators are non-associative", self.peek().pos)
        return node

    def additive(self):
        node = self.multiplicative()
        while self.is_op("+", "-"):
            op = self.next().value
            node = Binary(op, node, self.multiplicative())
        return node

    def multiplicative(self):
        node = self.unary()
        while self.is_op("*", "/", "%"):
            op = self.next().value
            node = Binary(op, node, self.unary())
        return node

    def unary(self):
        if self.is_op("-", "+", "!"):
            op = self.next().value
            return Unary(op, self.unary())
        return self.power()

    def power(self):
        base = self.primary()
        if self.is_op("^"):
            self.next()
            return Binary("^", base, self.unary())
        return base

    def primary(self):
        t = self.peek()
        if t.kind == "NUM":
            self.next()
            return Num(t.value)
        if t.kind == "NAME":
            self.next()
            if self.is_op("("):
                self.next()
                args = []
                if not self.is_op(")"):
                    args.append(self.or_expr())
                    while self.is_op(","):
                        self.next()
                        args.append(self.or_expr())
                self.expect_op(")")
                return Call(t.value, args)
            if t.value == "true":
                return Bool(True)
            if t.value == "false":
                return Bool(False)
            return Var(t.value)
        if self.is_op("("):
            self.next()
            node = self.or_expr()
            self.expect_op(")")
            return node
        raise ParseError("unexpected token" if t.kind != "EOF" else "unexpected end of input", t.pos)


def parse(src):
    return _Parser(src).program()
