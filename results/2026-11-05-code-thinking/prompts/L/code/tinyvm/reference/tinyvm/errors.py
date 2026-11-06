class VMError(Exception):
    pass


class AsmError(VMError):
    def __init__(self, message, line):
        super().__init__(f"line {line}: {message}")
        self.message = message
        self.line = line


class ExecError(VMError):
    def __init__(self, message, pc):
        super().__init__(f"{message} at pc {pc}")
        self.message = message
        self.pc = pc


class StackUnderflow(ExecError):
    pass


class DivisionByZero(ExecError):
    pass


class VMTypeError(ExecError):
    pass


class StepLimitExceeded(ExecError):
    pass
