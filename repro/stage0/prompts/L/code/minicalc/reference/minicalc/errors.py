class CalcError(Exception):
    pass


class LexError(CalcError):
    def __init__(self, message, pos):
        super().__init__(f"{message} at {pos}")
        self.pos = pos


class ParseError(CalcError):
    def __init__(self, message, pos):
        super().__init__(f"{message} at {pos}")
        self.pos = pos


class EvalError(CalcError):
    def __init__(self, message):
        super().__init__(message)
