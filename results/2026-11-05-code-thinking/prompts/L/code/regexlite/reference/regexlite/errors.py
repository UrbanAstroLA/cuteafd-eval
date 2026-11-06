class RegexError(Exception):
    def __init__(self, message, pos):
        super().__init__(f"{message} at position {pos}")
        self.message = message
        self.pos = pos
