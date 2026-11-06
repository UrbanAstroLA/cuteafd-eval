class LedgerError(Exception):
    pass


class UnknownSKU(LedgerError):
    def __init__(self, sku):
        self.sku = sku
        super().__init__(f"unknown SKU {sku!r}")


class InsufficientStock(LedgerError):
    def __init__(self, sku, requested, available):
        self.sku, self.requested, self.available = sku, requested, available
        super().__init__(f"{sku}: requested {requested}, available {available}")
