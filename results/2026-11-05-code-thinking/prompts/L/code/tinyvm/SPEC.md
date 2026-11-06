Build a Python package named `tinyvm`: a stack virtual machine with an assembler, an interpreter and a disassembler. Python 3.12, standard library only.

## Files

- `tinyvm/__init__.py` — re-exports `Program`, `assemble`, `run`, `Result`, `disassemble`, `VMError`, `AsmError`, `ExecError`, `StackUnderflow`, `DivisionByZero`, `VMTypeError`, `StepLimitExceeded`.
- `tinyvm/errors.py` — the exception classes.
- `tinyvm/bytecode.py` — `Program`, opcode table.
- `tinyvm/assembler.py` — `assemble`.
- `tinyvm/vm.py` — `run` and `Result`.
- `tinyvm/disasm.py` — `disassemble`.

## errors.py

- `VMError(Exception)` — base class.
- `AsmError(VMError)` — `AsmError(message, line)`; attribute `line` (1-based). `str(err)` is `f"line {line}: {message}"`.
- `ExecError(VMError)` — `ExecError(message, pc)`; attribute `pc` (the failing instruction's address). Subclasses `StackUnderflow`, `DivisionByZero`, `VMTypeError`, `StepLimitExceeded` are raised only for the conditions named below; every other runtime error is a plain `ExecError`.

## bytecode.py

`Program` is a frozen dataclass with fields `code: tuple[int, ...]` and `strings: tuple[str, ...] = ()`. An instruction is an opcode followed by its operand (if any); an instruction's *address* is the index of its opcode in `code`.

| code | mnemonic | operand | effect |
|---|---|---|---|
| 0 | HALT | | stop |
| 1 | PUSH | int | push the integer |
| 2 | PUSH | string | push `strings[operand]` |
| 3-5 | POP DUP SWAP | | discard top / copy top / exchange top two |
| 6-10 | ADD SUB MUL DIV MOD | | pop `b`, pop `a`, push `a op b` |
| 11 | NEG | | negate top |
| 12-14 | EQ LT GT | | pop `b`, pop `a`, push 1 or 0 |
| 15 | NOT | | pop `a`, push 1 if `a == 0`, else 0 |
| 16 | JMP | address | jump to address |
| 17 / 18 | JZ / JNZ | address | pop `a`; jump if `a == 0` / `a != 0` |
| 19 / 20 | CALL / RET | address / none | call / return |
| 21 / 22 | LOAD / STORE | local | push local / pop into local |
| 23 | PRINT | | pop `v`, append `str(v)` to `output` |

## assembler.py

`assemble(source: str) -> Program`. Lines are split on `"\n"`. On each line, `;` outside a string literal starts a comment. A line consists of zero or more label definitions (an identifier `[A-Za-z_][A-Za-z0-9_]*` directly followed by `:`, optional whitespace around), then optionally one instruction: a mnemonic (case-insensitive) and, separated by whitespace, at most one operand. Labels are case-sensitive and denote the address of the next instruction in the source, or `len(code)` if none follows.

Operands:
- integer literal: `[+-]?[0-9]+` or `[+-]?0x[0-9a-fA-F]+`;
- string literal: double-quoted; escapes `\\`, `\"`, `\n`, `\t`; strings are interned in `strings` in order of first use, without duplicates;
- `PUSH` takes an integer (code 1) or a string (code 2); `JMP`, `JZ`, `JNZ`, `CALL` take a label name; `LOAD`, `STORE` take an integer from 0 to 255; all other mnemonics take none.

Raise `AsmError` with the offending line number for an unknown mnemonic, a missing, extra or wrongly-typed operand, a malformed literal (bad escape, unterminated string), a local out of range, a duplicate label (at its second definition), or any other text not fitting the line syntax. The first error in line order is raised; undefined labels are checked only after all lines are accepted, and reported at the first referencing line.

## vm.py

`run(program, max_steps=100_000) -> Result`. `Result` is a dataclass with `output: list[str]`, `stack: list` (bottom first) and `steps: int` (instructions run).

- Values are `int` and `str`. Execution starts at pc 0 with an empty stack and one top-level frame (256 empty locals).
- Each cycle: if pc equals `len(code)`, stop normally; else if `steps == max_steps`, raise `StepLimitExceeded`; else execute the instruction at pc and add 1 to `steps` (`HALT` counts, then stops). A pc outside `0..len(code)`, an unknown opcode, or an operand past the end of `code` raises `ExecError`.
- `ADD`, `LT`, `GT` accept two ints or two strings (`ADD` concatenates strings). `SUB`, `MUL`, `DIV`, `MOD`, `NEG`, `NOT`, `JZ`, `JNZ` need ints. `EQ` accepts anything: 1 iff both have the same type and are equal. Wrong types raise `VMTypeError`.
- `DIV` truncates toward zero; `MOD` satisfies `a == b * (a DIV b) + (a MOD b)`. A zero divisor raises `DivisionByZero`.
- Too few values on the stack for an instruction raises `StackUnderflow`.
- `CALL` pushes a frame holding the return address (the next instruction) and 256 empty locals, then jumps. `RET` pops it and jumps to its return address (raises `ExecError` in the top-level frame). A `CALL` when 1,000 frames already exist raises `ExecError`. The operand stack is shared by all frames.
- `LOAD k` of a local never stored in the current frame raises `ExecError`.

## disasm.py

`disassemble(program) -> str` returns assembly such that `assemble(disassemble(p)) == p` for every `p` produced by `assemble`.

- Every jump or call target gets a line `L<address>:` (decimal) just before the instruction at that address, or at the end for `len(code)`.
- Each instruction is one line: four spaces, the uppercase mnemonic, then a space and any operand: integers in decimal, strings quoted with `\`, `"`, newline and tab escaped as above, jump targets as `L<address>`.
- Every line ends with `"\n"` (`""` for empty code).
- Raise `ValueError` for an unknown opcode, a missing operand, a bad string index, or a jump target that is neither an instruction address nor `len(code)`.
