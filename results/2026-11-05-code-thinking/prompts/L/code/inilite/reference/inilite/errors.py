class IniError(Exception):
    pass


class ParseError(IniError):
    def __init__(self, message, line):
        super().__init__(f"line {line}: {message}")
        self.message = message
        self.line = line


class DuplicateKeyError(ParseError):
    pass
