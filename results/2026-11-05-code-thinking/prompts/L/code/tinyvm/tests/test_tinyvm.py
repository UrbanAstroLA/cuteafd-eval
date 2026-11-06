import pytest

from tinyvm import (AsmError, DivisionByZero, ExecError, Program, Result, StackUnderflow, StepLimitExceeded,
                    VMError, VMTypeError, assemble, disassemble, run)


def out(src, **kw):
    return run(assemble(src), **kw).output


# ---- assembler ----

def test_assemble_basic_encoding():
    p = assemble("PUSH 2\nPUSH -3\nADD\nPRINT\nHALT\n")
    assert p == Program((1, 2, 1, -3, 6, 23, 0), ())


def test_assemble_labels_comments_case():
    src = "; header\nstart: push 0x1F ; hex\n  loop:JMP loop\nend:\n"
    p = assemble(src)
    assert p.code == (1, 31, 16, 2)


def test_assemble_label_at_end_and_multiple_labels():
    p = assemble("a: b: JZ c\nc:")
    assert p.code == (17, 2)
    p = assemble("JMP done\nPUSH 1\ndone:\n")
    assert p.code == (16, 4, 1, 1)


def test_assemble_strings_interned_with_escapes():
    p = assemble('PUSH "hi; there"\nPUSH "a\\"b\\\\c\\n\\t"\nPUSH "hi; there" ; again\n')
    assert p.strings == ("hi; there", 'a"b\\c\n\t')
    assert p.code == (2, 0, 2, 1, 2, 0)


def test_assemble_load_store_range():
    assert assemble("STORE 0\nLOAD 255").code == (22, 0, 21, 255)
    with pytest.raises(AsmError) as ei:
        assemble("PUSH 1\nSTORE 256")
    assert ei.value.line == 2


def test_assemble_errors_line_numbers():
    cases = [
        ("PUSH 1\nFROB\n", 2),
        ("PUSH\n", 1),
        ("HALT 3\n", 1),
        ("PUSH 1 2\n", 1),
        ("PUSH 12abc\n", 1),
        ("PUSH \"abc\n", 1),
        ("PUSH \"a\\qb\"\n", 1),
        ("\n\nJMP 5\n", 3),
        ("LOAD x\n", 1),
        ("x: PUSH 1\nx: PUSH 2\n", 2),
        ("PUSH 1\n9lives: HALT\n", 2),
    ]
    for src, line in cases:
        with pytest.raises(AsmError) as ei:
            assemble(src)
        assert ei.value.line == line, src
        assert str(ei.value).startswith(f"line {line}: ")
        assert isinstance(ei.value, VMError)


def test_undefined_label_reported_after_syntax_errors():
    with pytest.raises(AsmError) as ei:
        assemble("JMP nowhere\nPUSH 1\nJZ alsonot\n")
    assert ei.value.line == 1
    with pytest.raises(AsmError) as ei:
        assemble("JMP nowhere\nPUSH 1\nBOGUS\n")
    assert ei.value.line == 3


def test_labels_are_case_sensitive():
    with pytest.raises(AsmError):
        assemble("Loop: JMP loop")


# ---- interpreter ----

def test_run_arithmetic_and_result():
    r = run(assemble("PUSH 7\nPUSH 2\nSUB\nPUSH 3\nMUL\nPRINT\nPUSH 9\nHALT\nPUSH 1"))
    assert isinstance(r, Result)
    assert r.output == ["15"]
    assert r.stack == [9]
    assert r.steps == 8


def test_div_mod_truncate_toward_zero():
    src = ("PUSH -7\nPUSH 2\nDIV\nPRINT\nPUSH -7\nPUSH 2\nMOD\nPRINT\n"
           "PUSH 7\nPUSH -2\nDIV\nPRINT\nPUSH 7\nPUSH -2\nMOD\nPRINT\n")
    assert out(src) == ["-3", "-1", "-3", "1"]


def test_comparisons_and_strings():
    src = ('PUSH "ab"\nPUSH "c"\nADD\nDUP\nPRINT\nPUSH "abd"\nLT\nPRINT\n'
           'PUSH 1\nPUSH "1"\nEQ\nPRINT\nPUSH 3\nPUSH 3\nEQ\nNOT\nPRINT\nPUSH 5\nPUSH 2\nGT\nPRINT\n')
    assert out(src) == ["abc", "1", "0", "0", "1"]


def test_swap_neg_jnz_loop():
    src = """
        PUSH 3
        STORE 0
    loop:
        LOAD 0
        PRINT
        LOAD 0
        PUSH 1
        SUB
        DUP
        STORE 0
        JNZ loop
        PUSH 1
        PUSH 2
        SWAP
        NEG
    """
    r = run(assemble(src))
    assert r.output == ["3", "2", "1"]
    assert r.stack == [2, -1]


def test_call_ret_with_fresh_locals():
    src = """
        PUSH 10
        STORE 0
        PUSH 5
        CALL double
        PRINT
        LOAD 0
        PRINT
        HALT
    double:
        STORE 0
        LOAD 0
        LOAD 0
        ADD
        RET
    """
    assert out(src) == ["10", "10"]


def test_recursive_factorial():
    src = """
        PUSH 10
        CALL fact
        PRINT
        HALT
    fact:               ; n -> n!
        DUP
        JZ base
        DUP
        PUSH 1
        SUB
        CALL fact
        MUL
        RET
    base:
        POP
        PUSH 1
        RET
    """
    assert out(src) == ["3628800"]


def test_runtime_error_classes_and_pc():
    with pytest.raises(DivisionByZero) as ei:
        run(assemble("PUSH 1\nPUSH 0\nMOD"))
    assert ei.value.pc == 4
    with pytest.raises(StackUnderflow) as ei:
        run(assemble("PUSH 1\nSWAP"))
    assert ei.value.pc == 2
    with pytest.raises(VMTypeError):
        run(assemble('PUSH "a"\nPUSH 1\nADD'))
    with pytest.raises(VMTypeError):
        run(assemble('PUSH "a"\nPUSH 1\nLT'))
    with pytest.raises(VMTypeError):
        run(assemble('PUSH "a"\nJZ x\nx:'))
    for cls in (StackUnderflow, DivisionByZero, VMTypeError, StepLimitExceeded):
        assert issubclass(cls, ExecError)


def test_plain_exec_errors():
    with pytest.raises(ExecError) as ei:
        run(assemble("PUSH 1\nRET"))
    assert type(ei.value) is ExecError and ei.value.pc == 2
    with pytest.raises(ExecError) as ei:
        run(assemble("LOAD 3"))
    assert type(ei.value) is ExecError
    with pytest.raises(ExecError) as ei:
        run(assemble("PUSH 1\nSTORE 3\nCALL f\nf: LOAD 3\nRET"))
    assert type(ei.value) is ExecError and ei.value.pc == 6
    with pytest.raises(ExecError):
        run(Program((1, 1, 99)))
    with pytest.raises(ExecError):
        run(Program((1,)))


def test_call_depth_limit():
    with pytest.raises(ExecError) as ei:
        run(assemble("f: CALL f"))
    assert type(ei.value) is ExecError
    # n = 998 makes 999 nested calls: 1,000 frames including the top-level one
    src = "PUSH 998\nCALL f\nHALT\nf: DUP\nJZ done\nPUSH 1\nSUB\nCALL f\nRET\ndone: RET"
    run(assemble(src))
    with pytest.raises(ExecError):
        run(assemble(src.replace("998", "999", 1)))


def test_step_limit_exact_boundary():
    src = "PUSH 1\nPUSH 2\nADD\nHALT"
    assert run(assemble(src), max_steps=4).steps == 4
    with pytest.raises(StepLimitExceeded) as ei:
        run(assemble(src), max_steps=3)
    assert ei.value.pc == 5
    r = run(assemble("PUSH 1\nPUSH 2"), max_steps=2)
    assert r.steps == 2 and r.stack == [1, 2]


def test_infinite_loop_hits_limit():
    with pytest.raises(StepLimitExceeded) as ei:
        run(assemble("top: JMP top"), max_steps=50)
    assert ei.value.pc == 0


def test_jump_to_end_stops_normally():
    r = run(assemble("PUSH 0\nJZ end\nPUSH 99\nPRINT\nend:"))
    assert r.output == [] and r.stack == [] and r.steps == 2


# ---- disassembler ----

def test_disassemble_format():
    p = assemble('top: PUSH "a\\"b\\n"\nPRINT\nPUSH -4\nJNZ top\nCALL fin\nfin:')
    assert disassemble(p) == ('L0:\n    PUSH "a\\"b\\n"\n    PRINT\n    PUSH -4\n    JNZ L0\n'
                              '    CALL L9\nL9:\n')


def test_disassemble_empty_and_locals():
    assert disassemble(Program(())) == ""
    assert disassemble(assemble("load 7\nstore 0x0a")) == "    LOAD 7\n    STORE 10\n"


def test_round_trip():
    src = """
        PUSH "x\\ty"
        STORE 1
        PUSH 0x10
    again:
        DUP
        JZ out
        PUSH 1
        SUB
        LOAD 1
        PRINT
        JMP again
    out:
        PUSH "x\\ty"
        PUSH "\\\\"
        CALL sub
        HALT
    sub: RET
    """
    p = assemble(src)
    q = assemble(disassemble(p))
    assert q == p
    assert run(q).output == run(p).output


def test_disassemble_invalid():
    for prog in (Program((42,)), Program((1,)), Program((2, 0)), Program((16, 1, 0)), Program((16, 9))):
        with pytest.raises(ValueError):
            disassemble(prog)
