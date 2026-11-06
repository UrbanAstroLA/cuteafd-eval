Build a Python package named `cronsched`: a parser for five-field cron expressions, next-run computation on naive datetimes, and an in-process job scheduler with an injectable clock. Python 3.12, standard library only.

## Files

- `cronsched/__init__.py` — re-exports `CronExpr`, `Scheduler`, `Job`, `CronError`, `CronSyntaxError`, `SchedulerError`.
- `cronsched/errors.py` — the exception classes.
- `cronsched/fields.py` — parsing of a single field.
- `cronsched/expr.py` — `CronExpr`.
- `cronsched/scheduler.py` — `Job` and `Scheduler`.

## errors.py

- `CronError(Exception)` — base class.
- `CronSyntaxError(CronError)` — `CronSyntaxError(message, field=None)`; attribute `field` is the name of the offending field (`"minute"`, `"hour"`, `"day"`, `"month"`, `"weekday"`), or `None` when the problem is not inside one field.
- `SchedulerError(CronError)`.

## fields.py

The fields, in order, with their allowed values: `minute` 0-59, `hour` 0-23, `day` 1-31, `month` 1-12, `weekday` 0-7 (0 and 7 both mean Sunday).

A field is a comma-separated list of one or more items. An item is `BASE` or `BASE/STEP`, where `BASE` is `*`, a value `V`, or a range `V1-V2`, and `STEP` is decimal digits with value at least 1.

- A value is decimal digits, or a name: `JAN`-`DEC` (1-12) in the month field only, `SUN`-`SAT` (0-6) in the weekday field only, case-insensitive. Names may be range endpoints.
- `*` means the whole field range, except that for `weekday` it means 0-6.
- `V1-V2` requires `V1 <= V2` (no wrap-around).
- `V/STEP` means `V-M/STEP` where `M` is the field maximum (6 for `weekday`).
- A step selects the first value of the range and every `STEP`-th value after it, up to the range end.
- In `weekday`, 7 becomes 0 after expansion.

Anything else — an empty item, a value out of range, a name in the wrong field, a reversed range, a step of 0 — raises `CronSyntaxError` with that field's name.

## expr.py

`CronExpr(text)` parses `text` after stripping surrounding whitespace.

- If it starts with `@` it must be one of these macros (case-insensitive): `@yearly` and `@annually` = `0 0 1 1 *`, `@monthly` = `0 0 1 * *`, `@weekly` = `0 0 * * 0`, `@daily` and `@midnight` = `0 0 * * *`, `@hourly` = `0 * * * *`. Any other `@` word raises `CronSyntaxError` with `field=None`.
- Otherwise it is split on runs of whitespace and must have exactly five fields, else `CronSyntaxError` with `field=None`.

Attributes: `text` (the argument as given) and `minutes`, `hours`, `days`, `months`, `weekdays` — sorted tuples of the distinct allowed values (weekdays use 0 = Sunday … 6 = Saturday).

A datetime matches when its minute, hour and month are allowed and its day matches. Day rule: if the day field's text or the weekday field's text starts with `*` (for a macro, use its expansion), the day must satisfy both the day field and the weekday field; otherwise it must satisfy at least one of them. So `0 0 13 * FRI` runs on every 13th and every Friday, while `0 0 */2 * MON` runs only on Mondays that are odd-numbered days.

- `matches(dt) -> bool` — seconds and microseconds are ignored.
- `next_run(after) -> datetime` — the earliest datetime strictly later than `after`, with zero seconds and microseconds, that matches. `after` must be a naive `datetime.datetime`; one with `tzinfo` raises `ValueError`. If nothing matches up to and including `after + timedelta(days=3660)`, raise `CronError` (not `CronSyntaxError`). The search must skip whole days and hours that cannot match instead of checking every minute; every call, including a failing one, must finish in well under a second.
- `next_n(after, n) -> list[datetime]` — the next `n` run times, each computed from the previous one. `n < 0` raises `ValueError`; `n == 0` gives `[]`.

## scheduler.py

`Job` is a dataclass with fields `name`, `expr` (a `CronExpr`), `callback`, `next_run` (datetime or `None`), `last_run` (initially `None`), `runs` (initially 0), `failures` (initially 0), `paused` (initially `False`).

`Scheduler(clock=datetime.datetime.now)`. `clock` is a zero-argument callable returning a naive datetime.

- `add(name, expr, callback=None) -> Job` — `expr` is a `CronExpr` or a string (parsed with `CronExpr`; errors propagate and nothing is added). A name already in use raises `SchedulerError`. The job's `next_run` is `expr.next_run(clock())`.
- `remove(name)`, `get(name) -> Job` — an unknown name raises `SchedulerError`.
- `pause(name)` — sets `paused` and clears `next_run` to `None`; pausing a paused job changes nothing. `resume(name)` — clears `paused` and sets `next_run` to `expr.next_run(clock())`; resuming an active job changes nothing. Both raise `SchedulerError` for an unknown name.
- `jobs() -> list[Job]` — active jobs ordered by `(next_run, name)`, followed by paused jobs ordered by name.
- `next_wakeup()` — the earliest `next_run` among active jobs, or `None`.
- `run_pending() -> list[str]` — read `now = clock()` once. Every active job with `next_run <= now` is due; run the due jobs in `(next_run, name)` order. Running a job: let `scheduled = job.next_run`; call `callback(name, scheduled)` if there is a callback; if it raises any `Exception`, increment `failures` and continue (the exception is not propagated). In either case increment `runs`, set `last_run = scheduled` and `next_run = expr.next_run(now)`. A job runs at most once per call, however many scheduled times it missed. Return the names in the order run.
