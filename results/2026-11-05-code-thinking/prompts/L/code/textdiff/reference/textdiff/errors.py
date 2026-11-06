class DiffError(Exception):
    pass


class PatchFormatError(DiffError):
    def __init__(self, message, line):
        self.message, self.line = message, line
        super().__init__(f"line {line}: {message}")


class PatchConflict(DiffError):
    def __init__(self, hunk, line):
        self.hunk, self.line = hunk, line
        super().__init__(f"hunk {hunk} does not apply at line {line}")
