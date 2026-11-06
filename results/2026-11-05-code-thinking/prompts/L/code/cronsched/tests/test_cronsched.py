import datetime as dt

import pytest

from cronsched import CronError, CronExpr, CronSyntaxError, Job, Scheduler, SchedulerError

D = dt.datetime


class FakeClock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += dt.timedelta(**kw)


def test_star_fields():
    e = CronExpr("* * * * *")
    assert e.minutes == tuple(range(60)) and e.hours == tuple(range(24))
    assert e.days == tuple(range(1, 32)) and e.months == tuple(range(1, 13))
    assert e.weekdays == (0, 1, 2, 3, 4, 5, 6)
    assert e.text == "* * * * *"


def test_lists_ranges_steps():
    e = CronExpr("0,15,30,45 9-17/4 1,15 */3 1-5")
    assert e.minutes == (0, 15, 30, 45)
    assert e.hours == (9, 13, 17)
    assert e.days == (1, 15)
    assert e.months == (1, 4, 7, 10)
    assert e.weekdays == (1, 2, 3, 4, 5)
    assert CronExpr("10/20 * * * *").minutes == (10, 30, 50)
    assert CronExpr("*/100 * * * *").minutes == (0,)
    assert CronExpr("5,1,5,3-4 * * * *").minutes == (1, 3, 4, 5)
    assert CronExpr("  07  */12\t* * *  ").hours == (0, 12)


def test_names_case_insensitive():
    e = CronExpr("0 0 * JAN,mar-May sun,Fri")
    assert e.months == (1, 3, 4, 5)
    assert e.weekdays == (0, 5)
    assert CronExpr("0 0 * * MON-FRI").weekdays == (1, 2, 3, 4, 5)


def test_weekday_seven_and_steps():
    assert CronExpr("* * * * 7").weekdays == (0,)
    assert CronExpr("* * * * 5-7").weekdays == (0, 5, 6)
    assert CronExpr("* * * * */2").weekdays == (0, 2, 4, 6)
    assert CronExpr("* * * * 1-7/2").weekdays == (0, 1, 3, 5)
    assert CronExpr("* * * * 4/1").weekdays == (4, 5, 6)


def test_macros():
    assert CronExpr("@hourly").minutes == (0,) and CronExpr("@hourly").hours == tuple(range(24))
    w = CronExpr("@weekly")
    assert (w.minutes, w.hours, w.weekdays) == ((0,), (0,), (0,))
    y = CronExpr(" @Annually ")
    assert (y.days, y.months) == ((1,), (1,))
    assert CronExpr("@MIDNIGHT").hours == (0,)
    assert CronExpr("@monthly").days == (1,)


SYNTAX_ERRORS = [
    ("", None), ("* * * *", None), ("* * * * * *", None), ("@reboot", None),
    ("60 * * * *", "minute"), ("* 24 * * *", "hour"), ("* * 0 * *", "day"), ("* * 32 * *", "day"),
    ("* * * 13 *", "month"), ("* * * * 8", "weekday"), ("5-1 * * * *", "minute"), ("*/0 * * * *", "minute"),
    ("1,,2 * * * *", "minute"), ("* * * JAN-FOO *", "month"), ("* * * * JAN", "weekday"),
    ("* * * MON *", "month"), ("a * * * *", "minute"), ("-5 * * * *", "minute"), ("1-2-3 * * * *", "minute"),
    ("* * * * 7/2", "weekday"), ("*/2/3 * * * *", "minute"), ("*-5 * * * *", "minute"), ("* 1/x * * *", "hour"),
    ("* * * * FRI-SUN", "weekday"), ("1, * * * *", "minute"),
]


def test_syntax_errors_name_the_field():
    for text, field in SYNTAX_ERRORS:
        with pytest.raises(CronSyntaxError) as ei:
            CronExpr(text)
        assert ei.value.field == field, text
        assert isinstance(ei.value, CronError)


def test_next_run_basic_and_strictly_after():
    e = CronExpr("*/15 * * * *")
    assert e.next_run(D(2026, 11, 5, 10, 7, 30)) == D(2026, 11, 5, 10, 15)
    assert e.next_run(D(2026, 11, 5, 10, 15)) == D(2026, 11, 5, 10, 30)
    assert e.next_run(D(2026, 11, 5, 10, 14, 59, 999999)) == D(2026, 11, 5, 10, 15)
    assert e.next_run(D(2026, 11, 5, 23, 50)) == D(2026, 11, 6, 0, 0)


def test_next_run_rollovers():
    assert CronExpr("0 0 1 1 *").next_run(D(2026, 12, 31, 23, 59)) == D(2027, 1, 1)
    assert CronExpr("30 23 31 * *").next_run(D(2026, 4, 1)) == D(2026, 5, 31, 23, 30)
    assert CronExpr("5 4 * * *").next_run(D(2026, 2, 28, 4, 5)) == D(2026, 3, 1, 4, 5)


def test_next_run_leap_day():
    e = CronExpr("0 12 29 2 *")
    assert e.next_run(D(2026, 3, 1)) == D(2028, 2, 29, 12)
    assert e.next_run(D(2096, 3, 1)) == D(2104, 2, 29, 12)


def test_weekday_numbering():
    # 2026-11-05 is a Thursday
    assert CronExpr("0 9 * * SUN").next_run(D(2026, 11, 5)) == D(2026, 11, 8, 9)
    assert CronExpr("0 9 * * 7").next_run(D(2026, 11, 5)) == D(2026, 11, 8, 9)
    assert CronExpr("0 9 * * 4").next_run(D(2026, 11, 5, 9)) == D(2026, 11, 12, 9)


def test_day_or_rule_when_both_restricted():
    e = CronExpr("0 0 13 * FRI")
    assert e.next_n(D(2026, 12, 1), 5) == [D(2026, 12, 4), D(2026, 12, 11), D(2026, 12, 13), D(2026, 12, 18),
                                            D(2026, 12, 25)]


def test_day_and_rule_when_field_starts_with_star():
    e = CronExpr("0 0 */2 * MON")
    assert e.next_n(D(2026, 11, 5, 12), 4) == [D(2026, 11, 9), D(2026, 11, 23), D(2026, 12, 7), D(2026, 12, 21)]
    assert CronExpr("0 0 1 * *").next_run(D(2026, 11, 5)) == D(2026, 12, 1)


def test_matches_ignores_seconds():
    e = CronExpr("30 8 * * MON-FRI")
    assert e.matches(D(2026, 11, 5, 8, 30, 45))
    assert not e.matches(D(2026, 11, 7, 8, 30))
    assert not e.matches(D(2026, 11, 5, 8, 31))


def test_never_matching_raises_cron_error():
    for text in ["0 0 30 2 *", "0 0 31 4,6,9,11 *", "* * 31 2 *"]:
        with pytest.raises(CronError) as ei:
            CronExpr(text).next_run(D(2026, 1, 1))
        assert not isinstance(ei.value, CronSyntaxError)


def test_next_n_and_argument_errors():
    e = CronExpr("0 */6 * * *")
    assert e.next_n(D(2026, 1, 1, 5), 3) == [D(2026, 1, 1, 6), D(2026, 1, 1, 12), D(2026, 1, 1, 18)]
    assert e.next_n(D(2026, 1, 1), 0) == []
    with pytest.raises(ValueError):
        e.next_n(D(2026, 1, 1), -1)
    with pytest.raises(ValueError):
        e.next_run(D(2026, 1, 1, tzinfo=dt.timezone.utc))


@pytest.fixture
def clock():
    return FakeClock(D(2026, 11, 5, 10, 7))


def test_scheduler_add_and_ordering(clock):
    s = Scheduler(clock)
    j = s.add("b", "*/10 * * * *")
    assert isinstance(j, Job)
    assert j.next_run == D(2026, 11, 5, 10, 10) and j.last_run is None and j.runs == 0 and not j.paused
    s.add("a", CronExpr("10 10 * * *"))
    s.add("c", "@hourly")
    assert [x.name for x in s.jobs()] == ["a", "b", "c"]
    assert s.next_wakeup() == D(2026, 11, 5, 10, 10)
    assert s.get("c").next_run == D(2026, 11, 5, 11, 0)


def test_scheduler_name_errors(clock):
    s = Scheduler(clock)
    s.add("x", "* * * * *")
    with pytest.raises(SchedulerError):
        s.add("x", "@daily")
    for op in (s.remove, s.get, s.pause, s.resume):
        with pytest.raises(SchedulerError):
            op("nope")
    with pytest.raises(CronSyntaxError):
        s.add("y", "61 * * * *")
    assert [j.name for j in s.jobs()] == ["x"]
    s.remove("x")
    assert s.jobs() == [] and s.next_wakeup() is None
    assert issubclass(SchedulerError, CronError)


def test_run_pending_order_and_callbacks(clock):
    calls = []
    s = Scheduler(clock)
    s.add("late", "15 * * * *", lambda n, t: calls.append((n, t)))
    s.add("zeta", "*/10 * * * *", lambda n, t: calls.append((n, t)))
    s.add("alpha", "10 * * * *", lambda n, t: calls.append((n, t)))
    s.add("quiet", "*/5 * * * *")
    assert s.run_pending() == []
    clock.advance(minutes=8)  # 10:15
    assert s.run_pending() == ["alpha", "quiet", "zeta", "late"]
    assert calls == [("alpha", D(2026, 11, 5, 10, 10)), ("zeta", D(2026, 11, 5, 10, 10)),
                     ("late", D(2026, 11, 5, 10, 15))]
    q = s.get("quiet")
    assert q.runs == 1 and q.last_run == D(2026, 11, 5, 10, 10) and q.next_run == D(2026, 11, 5, 10, 20)
    assert s.get("alpha").next_run == D(2026, 11, 5, 11, 10)


def test_run_pending_missed_runs_collapse(clock):
    s = Scheduler(clock)
    s.add("m", "* * * * *")
    clock.advance(hours=3, seconds=20)  # 13:07:20
    assert s.run_pending() == ["m"]
    j = s.get("m")
    assert j.runs == 1 and j.last_run == D(2026, 11, 5, 10, 8) and j.next_run == D(2026, 11, 5, 13, 8)
    assert s.run_pending() == []


def test_run_pending_callback_failure(clock):
    def boom(name, when):
        raise RuntimeError("fail")

    s = Scheduler(clock)
    s.add("f", "*/5 * * * *", boom)
    clock.advance(minutes=3)
    assert s.run_pending() == ["f"]
    j = s.get("f")
    assert j.failures == 1 and j.runs == 1 and j.next_run == D(2026, 11, 5, 10, 15)
    clock.advance(minutes=5)
    s.run_pending()
    assert j.failures == 2 and j.runs == 2


def test_pause_resume(clock):
    s = Scheduler(clock)
    s.add("p", "0 * * * *")
    s.add("q", "30 * * * *")
    s.add("a", "45 * * * *")
    s.pause("p")
    s.pause("a")
    s.pause("p")
    assert s.get("p").paused and s.get("p").next_run is None
    assert [j.name for j in s.jobs()] == ["q", "a", "p"]
    clock.advance(hours=2)  # 12:07
    assert s.run_pending() == ["q"]
    assert s.next_wakeup() == D(2026, 11, 5, 12, 30)
    s.resume("p")
    assert s.get("p").next_run == D(2026, 11, 5, 13, 0) and not s.get("p").paused
    clock.advance(minutes=1)
    s.resume("p")
    assert s.get("p").next_run == D(2026, 11, 5, 13, 0)
