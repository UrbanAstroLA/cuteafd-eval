import datetime

from .errors import CronError, CronSyntaxError
from .fields import FIELD_ORDER, parse_field

MACROS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
HORIZON = datetime.timedelta(days=3660)


class CronExpr:
    def __init__(self, text):
        self.text = text
        body = text.strip()
        if body.startswith("@"):
            exp = MACROS.get(body.lower())
            if exp is None:
                raise CronSyntaxError(f"unknown macro {body!r}")
            body = exp
        parts = body.split()
        if len(parts) != 5:
            raise CronSyntaxError(f"expected 5 fields, got {len(parts)}")
        values = [parse_field(p, f) for p, f in zip(parts, FIELD_ORDER)]
        self.minutes, self.hours, self.days, self.months, self.weekdays = values
        self._sets = [frozenset(v) for v in values]
        self._day_star = parts[2].startswith("*")
        self._dow_star = parts[4].startswith("*")

    def __repr__(self):
        return f"CronExpr({self.text!r})"

    def _day_ok(self, d):
        dom = d.day in self._sets[2]
        dow = (d.weekday() + 1) % 7 in self._sets[4]
        if self._day_star or self._dow_star:
            return dom and dow
        return dom or dow

    def matches(self, dt):
        return (dt.minute in self._sets[0] and dt.hour in self._sets[1] and dt.month in self._sets[3]
                and self._day_ok(dt))

    def next_run(self, after):
        if after.tzinfo is not None:
            raise ValueError("after must be a naive datetime")
        limit = after + HORIZON
        t = after.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
        mins, hours, months = self._sets[0], self._sets[1], self._sets[3]
        while t <= limit:
            if t.month not in months:
                y, m = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
                t = datetime.datetime(y, m, 1)
                continue
            if not self._day_ok(t):
                t = datetime.datetime(t.year, t.month, t.day) + datetime.timedelta(days=1)
                continue
            if t.hour not in hours:
                t = t.replace(minute=0) + datetime.timedelta(hours=1)
                continue
            if t.minute not in mins:
                later = [m for m in self.minutes if m > t.minute]
                if later:
                    t = t.replace(minute=later[0])
                else:
                    t = t.replace(minute=0) + datetime.timedelta(hours=1)
                continue
            return t
        raise CronError(f"no run time within {HORIZON.days} days after {after}")

    def next_n(self, after, n):
        if n < 0:
            raise ValueError("n must be >= 0")
        out, t = [], after
        for _ in range(n):
            t = self.next_run(t)
            out.append(t)
        return out
