class UnitError(Exception):
    pass


class ParseError(UnitError):
    def __init__(self, message, pos):
        super().__init__(f"{message} at {pos}")
        self.pos = pos


class UnknownUnitError(UnitError):
    def __init__(self, symbol):
        super().__init__(f"unknown unit {symbol!r}")
        self.symbol = symbol


class DimensionError(UnitError):
    pass
