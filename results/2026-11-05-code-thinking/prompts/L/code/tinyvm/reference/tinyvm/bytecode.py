from dataclasses import dataclass

# code -> (mnemonic, operand kind); operand kind is None, "int", "str", "addr" or "local"
OPCODES = {
    0: ("HALT", None), 1: ("PUSH", "int"), 2: ("PUSH", "str"), 3: ("POP", None), 4: ("DUP", None),
    5: ("SWAP", None), 6: ("ADD", None), 7: ("SUB", None), 8: ("MUL", None), 9: ("DIV", None),
    10: ("MOD", None), 11: ("NEG", None), 12: ("EQ", None), 13: ("LT", None), 14: ("GT", None),
    15: ("NOT", None), 16: ("JMP", "addr"), 17: ("JZ", "addr"), 18: ("JNZ", "addr"), 19: ("CALL", "addr"),
    20: ("RET", None), 21: ("LOAD", "local"), 22: ("STORE", "local"), 23: ("PRINT", None),
}

# mnemonic -> code (PUSH maps to 1; the assembler picks 2 for string operands)
MNEMONICS = {}
for _code, (_name, _kind) in OPCODES.items():
    MNEMONICS.setdefault(_name, _code)

N_LOCALS = 256
MAX_FRAMES = 1000


@dataclass(frozen=True)
class Program:
    code: tuple = ()
    strings: tuple = ()
