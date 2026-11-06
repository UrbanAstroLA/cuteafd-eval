from dataclasses import dataclass, field

from .bytecode import MAX_FRAMES, N_LOCALS, OPCODES
from .errors import DivisionByZero, ExecError, StackUnderflow, StepLimitExceeded, VMTypeError

_UNSET = object()


@dataclass
class Result:
    output: list = field(default_factory=list)
    stack: list = field(default_factory=list)
    steps: int = 0


def _is_int(v):
    return type(v) is int


def run(program, max_steps=100_000):
    code, strings = program.code, program.strings
    stack, output = [], []
    frames = [(None, [_UNSET] * N_LOCALS)]
    pc, steps = 0, 0

    while True:
        if pc == len(code):
            break
        if not 0 <= pc < len(code):
            raise ExecError("pc out of range", pc)
        if steps == max_steps:
            raise StepLimitExceeded("step limit exceeded", pc)
        op = code[pc]
        if op not in OPCODES:
            raise ExecError(f"unknown opcode {op}", pc)
        kind = OPCODES[op][1]
        if kind is not None:
            if pc + 1 >= len(code):
                raise ExecError("missing operand", pc)
            arg, nxt = code[pc + 1], pc + 2
        else:
            arg, nxt = None, pc + 1
        here = pc
        steps += 1

        def need(k):
            if len(stack) < k:
                raise StackUnderflow("stack underflow", here)

        def ints(*vals):
            if not all(_is_int(v) for v in vals):
                raise VMTypeError("expected integers", here)

        if op == 0:
            break
        elif op == 1:
            stack.append(arg)
        elif op == 2:
            if not 0 <= arg < len(strings):
                raise ExecError("bad string index", here)
            stack.append(strings[arg])
        elif op == 3:
            need(1)
            stack.pop()
        elif op == 4:
            need(1)
            stack.append(stack[-1])
        elif op == 5:
            need(2)
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif 6 <= op <= 10 or 12 <= op <= 14:
            need(2)
            b, a = stack[-1], stack[-2]
            if op == 6:
                if not ((_is_int(a) and _is_int(b)) or (type(a) is str and type(b) is str)):
                    raise VMTypeError("ADD needs two ints or two strings", here)
                r = a + b
            elif op in (7, 8, 9, 10):
                ints(a, b)
                if op == 7:
                    r = a - b
                elif op == 8:
                    r = a * b
                else:
                    if b == 0:
                        raise DivisionByZero("division by zero", here)
                    q = abs(a) // abs(b)
                    if (a < 0) != (b < 0):
                        q = -q
                    r = q if op == 9 else a - b * q
            elif op == 12:
                r = int(type(a) is type(b) and a == b)
            else:
                if not ((_is_int(a) and _is_int(b)) or (type(a) is str and type(b) is str)):
                    raise VMTypeError("comparison needs two ints or two strings", here)
                r = int(a < b) if op == 13 else int(a > b)
            del stack[-2:]
            stack.append(r)
        elif op == 11:
            need(1)
            ints(stack[-1])
            stack[-1] = -stack[-1]
        elif op == 15:
            need(1)
            ints(stack[-1])
            stack[-1] = int(stack[-1] == 0)
        elif op == 16:
            nxt = arg
        elif op in (17, 18):
            need(1)
            ints(stack[-1])
            v = stack.pop()
            if (v == 0) == (op == 17):
                nxt = arg
        elif op == 19:
            if len(frames) >= MAX_FRAMES:
                raise ExecError("call stack overflow", here)
            frames.append((nxt, [_UNSET] * N_LOCALS))
            nxt = arg
        elif op == 20:
            if len(frames) == 1:
                raise ExecError("return from top-level frame", here)
            nxt = frames.pop()[0]
        elif op == 21:
            if not 0 <= arg < N_LOCALS:
                raise ExecError("bad local", here)
            v = frames[-1][1][arg]
            if v is _UNSET:
                raise ExecError(f"local {arg} is not set", here)
            stack.append(v)
        elif op == 22:
            if not 0 <= arg < N_LOCALS:
                raise ExecError("bad local", here)
            need(1)
            frames[-1][1][arg] = stack.pop()
        elif op == 23:
            need(1)
            output.append(str(stack.pop()))
        pc = nxt
    return Result(output, stack, steps)
