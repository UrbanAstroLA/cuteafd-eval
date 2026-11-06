from .bytecode import OPCODES


def _quote(s):
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return '"' + s + '"'


def disassemble(program):
    code, strings = program.code, program.strings
    instrs, pc = [], 0
    while pc < len(code):
        op = code[pc]
        if op not in OPCODES:
            raise ValueError(f"unknown opcode {op} at {pc}")
        name, kind = OPCODES[op]
        if kind is None:
            instrs.append((pc, name, kind, None))
            pc += 1
            continue
        if pc + 1 >= len(code):
            raise ValueError(f"missing operand at {pc}")
        arg = code[pc + 1]
        if kind == "str" and not 0 <= arg < len(strings):
            raise ValueError(f"string index {arg} out of range at {pc}")
        instrs.append((pc, name, kind, arg))
        pc += 2
    addrs = {a for a, *_ in instrs} | {len(code)}
    targets = set()
    for a, _, kind, arg in instrs:
        if kind == "addr":
            if arg not in addrs:
                raise ValueError(f"bad jump target {arg} at {a}")
            targets.add(arg)
    lines = []
    for a, name, kind, arg in instrs:
        if a in targets:
            lines.append(f"L{a}:")
        if kind is None:
            lines.append(f"    {name}")
        elif kind == "str":
            lines.append(f"    {name} {_quote(strings[arg])}")
        elif kind == "addr":
            lines.append(f"    {name} L{arg}")
        else:
            lines.append(f"    {name} {arg}")
    if len(code) in targets:
        lines.append(f"L{len(code)}:")
    return "".join(line + "\n" for line in lines)
