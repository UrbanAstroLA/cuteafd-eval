import datetime
import math
import re
from dataclasses import dataclass

TYPES = ("int", "float", "str", "bool", "date")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    required: bool = True

    def __post_init__(self):
        if self.type not in TYPES:
            raise ValueError(f"unknown type {self.type!r}")


class Schema:
    def __init__(self, columns):
        self.columns = list(columns)
        names = [c.name for c in self.columns]
        if len(set(names)) != len(names):
            raise ValueError("duplicate column names")

    def names(self):
        return [c.name for c in self.columns]


def parse_value(column, text):
    t = text.strip()
    if t == "":
        if column.required:
            raise ValueError("required")
        return None
    if column.type == "int":
        return int(t)
    if column.type == "float":
        x = float(t)
        if math.isnan(x) or math.isinf(x):
            raise ValueError("non-finite float")
        return x
    if column.type == "str":
        return t
    if column.type == "bool":
        low = t.lower()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
        raise ValueError(f"invalid bool {t!r}")
    if column.type == "date":
        if not _DATE.fullmatch(t):
            raise ValueError(f"invalid date {t!r}")
        return datetime.date.fromisoformat(t)
    raise ValueError("unknown type")
