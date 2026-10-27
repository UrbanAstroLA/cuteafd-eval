class ReportError(Exception):
    pass


class SchemaError(ReportError):
    def __init__(self, missing):
        self.missing = sorted(missing)
        super().__init__(f"missing columns: {', '.join(self.missing)}")


class RowError(ReportError):
    def __init__(self, line, column, message):
        self.line, self.column, self.message = line, column, message
        super().__init__(f"line {line}, column {column}: {message}")
