#!/usr/bin/env python3
"""Checks the run index (site/runs/<run>.json) against the published run folders. Standard library only.

  check_runs.py [run ...]     checks the named runs (default: every run folder under results/)

A run file passes when it has every required field, every goal has every required field with an allowed value, and
every file in results/<run>/ belongs to exactly one goal or to the run's own `run_files` (paths or fnmatch globs,
relative to the run folder). Exit 0 when every checked run passes.
"""
import fnmatch
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "site" / "runs"
RUN_KEYS = ("id", "date", "title", "kind", "question", "engines", "checkpoints", "hardware", "protocol", "goals",
            "run_files")
GOAL_KEYS = ("id", "question", "added", "design", "files", "result_docs", "status", "headline", "findings")
DESIGN_KEYS = ("instrument", "arms", "items", "unit", "n", "repeats", "interval")
ADDED = {"protocol", "amendment", "follow-up", "post hoc", "exploratory", "check", "source reading", "accounting"}
STATUS = {"done", "partial", "not run", "withdrawn"}


def files_of(run):
    root = REPO / "results" / run
    return sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs)


def owners(path, patterns):
    return [p for p in patterns if path == p or fnmatch.fnmatchcase(path, p)]


def check(run):
    errs, src = [], RUNS / f"{run}.json"
    if not src.exists():
        return [f"{run}: no index file"]
    try:
        r = json.loads(src.read_text())
    except ValueError as e:
        return [f"{run}: not JSON ({e})"]
    errs += [f"{run}: missing {k}" for k in RUN_KEYS if k not in r]
    if r.get("id") != run:
        errs.append(f"{run}: id is {r.get('id')!r}")
    ids = set()
    claim = {}                                     # pattern -> owner
    for p in r.get("run_files", []):
        claim.setdefault(p, []).append("run_files")
    for g in r.get("goals", []):
        gid = g.get("id", "?")
        if gid in ids:
            errs.append(f"{run}/{gid}: duplicate goal id")
        ids.add(gid)
        errs += [f"{run}/{gid}: missing {k}" for k in GOAL_KEYS if k not in g]
        errs += [f"{run}/{gid}: design missing {k}" for k in DESIGN_KEYS if k not in g.get("design", {})]
        if g.get("added") not in ADDED:
            errs.append(f"{run}/{gid}: added {g.get('added')!r} not in {sorted(ADDED)}")
        if g.get("status") not in STATUS:
            errs.append(f"{run}/{gid}: status {g.get('status')!r} not in {sorted(STATUS)}")
        if not g.get("findings") and not g.get("no_findings_reason"):
            errs.append(f"{run}/{gid}: no findings and no no_findings_reason")
        for p in g.get("files", []):
            claim.setdefault(p, []).append(gid)
    have = files_of(run)
    for d in r.get("goals", []):
        for p in d.get("result_docs", []):
            if p not in have:
                errs.append(f"{run}/{d.get('id')}: result_doc {p} does not exist")
    for f in have:
        own = [o for p, os_ in claim.items() if f == p or fnmatch.fnmatchcase(f, p) for o in os_]
        if len(own) != 1:
            errs.append(f"{run}: {f} belongs to {len(own)} owners {own}")
    for p, os_ in claim.items():
        if not any(f == p or fnmatch.fnmatchcase(f, p) for f in have):
            errs.append(f"{run}: pattern {p} ({os_}) matches no file")
    return errs


def main(argv):
    runs = argv or sorted(p.name for p in (REPO / "results").iterdir() if p.is_dir())
    bad = 0
    for run in runs:
        e = check(run)
        bad += bool(e)
        print(f"{run}: {'ok' if not e else f'{len(e)} problem(s)'}")
        for x in e[:40]:
            print("  ", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
