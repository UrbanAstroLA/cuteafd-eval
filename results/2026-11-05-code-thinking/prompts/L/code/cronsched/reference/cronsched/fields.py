import re

from .errors import CronSyntaxError

# name -> (min, max, star_max)
FIELDS = {
    "minute": (0, 59, 59),
    "hour": (0, 23, 23),
    "day": (1, 31, 31),
    "month": (1, 12, 12),
    "weekday": (0, 7, 6),
}
FIELD_ORDER = ("minute", "hour", "day", "month", "weekday")
NAMES = {
    "month": {n: i + 1 for i, n in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())},
    "weekday": {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())},
}
_DIGITS = re.compile(r"[0-9]+")


def _value(tok, field):
    lo, hi, _ = FIELDS[field]
    if _DIGITS.fullmatch(tok):
        v = int(tok)
    else:
        v = NAMES.get(field, {}).get(tok.upper())
        if v is None:
            raise CronSyntaxError(f"invalid value {tok!r}", field)
    if not lo <= v <= hi:
        raise CronSyntaxError(f"value {v} out of range {lo}-{hi}", field)
    return v


def parse_field(text, field):
    lo, hi, star_hi = FIELDS[field]
    out = set()
    for item in text.split(","):
        if item == "":
            raise CronSyntaxError("empty item", field)
        base, sep, step_txt = item.partition("/")
        step = 1
        if sep:
            if not _DIGITS.fullmatch(step_txt):
                raise CronSyntaxError(f"invalid step {step_txt!r}", field)
            step = int(step_txt)
            if step < 1:
                raise CronSyntaxError("step must be at least 1", field)
        if base == "*":
            start, end = lo, star_hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start, end = _value(a, field), _value(b, field)
            if start > end:
                raise CronSyntaxError(f"reversed range {base!r}", field)
        else:
            start = _value(base, field)
            end = star_hi if sep else start
            if start > end:
                raise CronSyntaxError(f"empty range {item!r}", field)
        for v in range(start, end + 1, step):
            out.add(0 if field == "weekday" and v == 7 else v)
    return tuple(sorted(out))
