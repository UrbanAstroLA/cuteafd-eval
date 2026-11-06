from .errors import DuplicateKeyError, IniError, ParseError
from .parser import load, loads
from .writer import dump, dumps

__all__ = ["loads", "load", "dumps", "dump", "IniError", "ParseError", "DuplicateKeyError"]
