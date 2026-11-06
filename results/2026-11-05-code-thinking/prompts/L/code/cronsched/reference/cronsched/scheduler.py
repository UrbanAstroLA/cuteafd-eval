import datetime
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .errors import SchedulerError
from .expr import CronExpr


@dataclass
class Job:
    name: str
    expr: CronExpr
    callback: Optional[Callable[..., Any]] = None
    next_run: Optional[datetime.datetime] = None
    last_run: Optional[datetime.datetime] = None
    runs: int = 0
    failures: int = 0
    paused: bool = False


class Scheduler:
    def __init__(self, clock=datetime.datetime.now):
        self._clock = clock
        self._jobs = {}

    def add(self, name, expr, callback=None):
        if name in self._jobs:
            raise SchedulerError(f"job {name!r} already exists")
        if not isinstance(expr, CronExpr):
            expr = CronExpr(expr)
        job = Job(name, expr, callback, expr.next_run(self._clock()))
        self._jobs[name] = job
        return job

    def get(self, name):
        try:
            return self._jobs[name]
        except KeyError:
            raise SchedulerError(f"no job {name!r}") from None

    def remove(self, name):
        self.get(name)
        del self._jobs[name]

    def pause(self, name):
        job = self.get(name)
        if not job.paused:
            job.paused = True
            job.next_run = None

    def resume(self, name):
        job = self.get(name)
        if job.paused:
            job.paused = False
            job.next_run = job.expr.next_run(self._clock())

    def jobs(self):
        active = sorted((j for j in self._jobs.values() if not j.paused), key=lambda j: (j.next_run, j.name))
        paused = sorted((j for j in self._jobs.values() if j.paused), key=lambda j: j.name)
        return active + paused

    def next_wakeup(self):
        times = [j.next_run for j in self._jobs.values() if not j.paused]
        return min(times) if times else None

    def run_pending(self):
        now = self._clock()
        due = sorted((j for j in self._jobs.values() if not j.paused and j.next_run <= now),
                     key=lambda j: (j.next_run, j.name))
        ran = []
        for job in due:
            scheduled = job.next_run
            if job.callback is not None:
                try:
                    job.callback(job.name, scheduled)
                except Exception:
                    job.failures += 1
            job.runs += 1
            job.last_run = scheduled
            job.next_run = job.expr.next_run(now)
            ran.append(job.name)
        return ran
