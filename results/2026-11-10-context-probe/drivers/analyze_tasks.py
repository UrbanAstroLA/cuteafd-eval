#!/usr/bin/env python3
"""Reads the task receipts (run_tasks.py) of the context probe. Standard library only.

  analyze_tasks.py summary --arm hqa [--set measured]
  analyze_tasks.py compare --a hqa --b compact [--set measured]

Unit of analysis: the item (family + index; the same item exists at every length). A request's score is the
fraction of answer fields correct; a request that did not finish with `stop` (cap, repetition abort) scores 0
and is counted separately. Repeats of an item (distinct seeds) are averaged within the item before anything is
compared. Arm differences are paired on (cell, length, item, rep), b - a, with a 95% interval from resampling
items (10,000 draws); the length interaction is the 128k difference minus the 4k difference, resampled the same
way. Descriptive columns (reasoning characters: the engine reports no reasoning token count, finish classes, speed, cache restores) are printed beside every score.

Beside the interval, `compare` prints two request-level readings on "every field correct" (PROTOCOL-DRAFT section
5): an exact McNemar test per repeat on the paired requests of the two arms, and the flip floor, the share of
(length, item) pairs whose outcome differs between two repeats of the same arm. A between-arm discordance at or
under the floor, with the two off-diagonal counts balanced, is no measured difference.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probelib as P  # noqa: E402

TASKS = P.RUN / "tasks"
LENGTHS = ["4k", "16k", "64k", "128k"]
BOOT = 10_000


def load_arm(arm: str, set_name: str) -> dict:
    """{cell: {(length, item, rep): final record}} plus per-cell part-turn records, over every run-tag of the arm.
    The latest ok final record of a unit wins (a resumed run re-does a failed unit)."""
    finals, parts = defaultdict(dict), defaultdict(list)
    for report in sorted((TASKS / arm).glob("*/*/report.json")):
        rep_doc = json.loads(report.read_text())
        if rep_doc.get("args", {}).get("set") != set_name:
            continue
        cell = report.parent.name.rsplit("-rep", 1)[0]
        for r in P.read_jsonl(report.parent / "requests.jsonl"):
            r["run_tag"] = report.parent.parent.name
            if r.get("final"):
                if r["status"] == "ok":
                    finals[cell][(r["length"], r["item"], r["rep"])] = r
            else:
                parts[cell].append(r)
    return {"finals": finals, "parts": parts}


def value(r: dict) -> float:
    s = r.get("score") or {}
    if r["finish_class"] != "stop" or not s.get("fields"):
        return 0.0
    return s["correct"] / s["fields"]


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def fmt(x, spec=".0f"):
    return "n/a" if x is None else format(x, spec)


def by_item(records: dict, length=None) -> dict:
    """{item: mean score over its repeats} for one length (or all lengths pooled per item)."""
    acc = defaultdict(list)
    for (ln, item, _rep), r in records.items():
        if length is None or ln == length:
            acc[item].append(value(r))
    return {k: statistics.fmean(v) for k, v in acc.items()}


def boot_mean(per_item: dict, seed=5):
    items = sorted(per_item)
    if not items:
        return None
    vals = [per_item[i] for i in items]
    rng = random.Random(seed)
    n = len(vals)
    draws = sorted(statistics.fmean(vals[rng.randrange(n)] for _ in range(n)) for _ in range(BOOT))
    return statistics.fmean(vals), draws[int(0.025 * BOOT)], draws[int(0.975 * BOOT) - 1], n


def evidence_table(records: dict, set_name: str) -> dict:
    """Field-level accuracy by how far back a field's earliest evidence sits (fraction of the document, 0 = start),
    in thirds of the fields at each length (cut points reported, since evidence positions are not uniform)."""
    index = json.loads((P.ITEMS / set_name / "index.json").read_text())
    files = {(i["id"], i["length"]): P.ITEMS / set_name / i["file"] for i in index["items"]}
    cache, acc = {}, defaultdict(list)
    for (ln, item, _rep), r in records.items():
        per = (r.get("score") or {}).get("per_field")
        if not per or r["finish_class"] != "stop":
            continue
        if (item, ln) not in cache:
            cache[(item, ln)] = json.loads(files[(item, ln)].read_text()).get("evidence_frac") or {}
        for field, ok in per.items():
            ev = cache[(item, ln)].get(field)
            if ev:
                acc[ln].append((min(ev), float(bool(ok))))
    out = {}
    for ln in LENGTHS:
        rows = sorted(acc.get(ln, []))
        if len(rows) < 3:
            continue
        cuts = [0, len(rows) // 3, 2 * len(rows) // 3, len(rows)]
        out[ln] = [{"earliest_evidence_from": rows[cuts[t]][0], "to": rows[cuts[t + 1] - 1][0],
                    "fields": cuts[t + 1] - cuts[t],
                    "accuracy": statistics.fmean(v for _, v in rows[cuts[t]:cuts[t + 1]])} for t in range(3)]
    return out


def summary(a) -> int:
    data = load_arm(a.arm, a.set)
    if not data["finals"]:
        sys.exit("no receipts for this arm and set")
    out = {"arm": a.arm, "set": a.set, "cells": {}}
    for cell in sorted(data["finals"]):
        recs = data["finals"][cell]
        print(f"\n{a.arm} {cell} ({a.set})")
        print(f"{'length':>6} {'items':>5} {'req':>4} {'score [95%]':>24} {'all ok':>6} {'fmt ok':>6} "
              f"{'stop/cap/rep':>12} {'think ch':>9} {'out tok':>8} {'tok/s':>6} {'ttft s':>6} {'cached':>6}")
        out["cells"][cell] = {}
        for ln in LENGTHS:
            rs = [r for (l2, _i, _r), r in recs.items() if l2 == ln]
            if not rs:
                continue
            m = boot_mean(by_item(recs, ln))
            fc = [r["finish_class"] for r in rs]
            row = {"items": m[3], "requests": len(rs), "score": m[:3],
                   "all_correct": statistics.fmean(float(value(r) == 1.0) for r in rs),
                   "format_ok": statistics.fmean(float((r.get("score") or {}).get("format") == "ok") for r in rs),
                   "finish": {k: fc.count(k) for k in sorted(set(fc))},
                   "reasoning_chars_median": med([r.get("reasoning_chars") for r in rs]),
                   "completion_tokens_median": med([r.get("completion_tokens") for r in rs]),
                   "decode_tok_s_median": med([r.get("decode_tok_s") for r in rs]),
                   "ttft_s_median": med([r.get("ttft_s") for r in rs]),
                   "cached_fraction_median": med([(r.get("cached_tokens") or 0) / r["prompt_tokens"]
                                                  for r in rs if r.get("prompt_tokens")])}
            out["cells"][cell][ln] = row
            print(f"{ln:>6} {row['items']:>5} {row['requests']:>4} "
                  f"{'{:.3f} [{:.3f}, {:.3f}]'.format(*row['score']):>24} {row['all_correct']:>6.2f} "
                  f"{row['format_ok']:>6.2f} "
                  f"{'{}/{}/{}'.format(fc.count('stop'), fc.count('cap'), fc.count('repetition')):>12} "
                  f"{fmt(row['reasoning_chars_median']):>9} {fmt(row['completion_tokens_median']):>8} "
                  f"{fmt(row['decode_tok_s_median'], '.1f'):>6} {fmt(row['ttft_s_median'], '.1f'):>6} "
                  f"{fmt(row['cached_fraction_median'], '.2f'):>6}")
        fam = defaultdict(dict)
        for (ln, item, rep), r in recs.items():
            fam[r["family"]][(ln, item, rep)] = r
        out["cells"][cell]["by_family"] = {f: {ln: (boot_mean(by_item(rr, ln)) or [None])[0] for ln in LENGTHS}
                                           for f, rr in sorted(fam.items())}
        for f, row in out["cells"][cell]["by_family"].items():
            print(f"  {f:>7}: " + "  ".join(f"{ln} {fmt(v, '.3f')}" for ln, v in row.items()))
        out["cells"][cell]["by_family_all_correct"] = {
            f: {ln: [sum(value(r) == 1.0 for (l2, _i, _r), r in rr.items() if l2 == ln),
                     sum(l2 == ln for (l2, _i, _r) in rr)] for ln in LENGTHS} for f, rr in sorted(fam.items())}
        for f, row in out["cells"][cell]["by_family_all_correct"].items():
            print(f"  {f:>7} every field correct: " + "  ".join(f"{ln} {k}/{n}" for ln, (k, n) in row.items()))
        out["cells"][cell]["by_evidence_position"] = evidence_table(recs, a.set)
        for ln, rows in out["cells"][cell]["by_evidence_position"].items():
            print(f"  evidence {ln:>4}: " + "  ".join(
                f"[{t['earliest_evidence_from']:.2f}-{t['to']:.2f}] {t['accuracy']:.3f}" for t in rows))
        pt = data["parts"].get(cell)
        if pt:
            ok = [r for r in pt if r["status"] == "ok"]
            out["cells"][cell]["part_turns"] = {
                "requests": len(pt), "ack_ok": statistics.fmean(float(bool(r.get("ack_ok"))) for r in ok),
                "finish": {k: [r["finish_class"] for r in pt].count(k) for k in {r["finish_class"] for r in pt}},
                "reasoning_chars_median": med([r.get("reasoning_chars") for r in ok])}
            print(f"  part turns: {out['cells'][cell]['part_turns']}")
    P.write_json_atomic(TASKS / a.arm / f"summary-{a.set}.json", out)
    return 0


def paired(xa: dict, xb: dict, length=None) -> dict:
    """{item: mean over shared (length, rep) of value_b - value_a}."""
    acc = defaultdict(list)
    for k in set(xa) & set(xb):
        if length is None or k[0] == length:
            acc[k[1]].append(value(xb[k]) - value(xa[k]))
    return {i: statistics.fmean(v) for i, v in acc.items()}


def right(r: dict) -> bool:
    return value(r) == 1.0


def mcnemar(pairs: list) -> dict:
    """pairs of (a right, b right). Exact two-sided binomial test on the discordant pairs."""
    b = sum(x and not y for x, y in pairs)
    c = sum(y and not x for x, y in pairs)
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)
    return {"pairs": len(pairs), "a_only": b, "b_only": c, "discordant": round(n / len(pairs), 4) if pairs else None,
            "p_exact": round(p, 4)}


def flip_tables(A: dict, B: dict) -> dict:
    """One cell. between: per repeat, arms paired on (length, item). floor: per arm, every pair of its repeats
    paired on (length, item) (distinct seeds, same engine setting)."""
    reps = lambda X: sorted({k[2] for k in X})  # noqa: E731
    out = {"between": {}, "floor": {}}
    for rep in sorted(set(reps(A)) & set(reps(B))):
        keys = [k for k in set(A) & set(B) if k[2] == rep]
        out["between"][f"rep{rep}"] = mcnemar([(right(A[k]), right(B[k])) for k in keys])
    for name, X in (("a", A), ("b", B)):
        rs = reps(X)
        for i, r0 in enumerate(rs):
            for r1 in rs[i + 1:]:
                keys = [(ln, it) for (ln, it, rep) in X if rep == r0 and (ln, it, r1) in X]
                out["floor"][f"{name} rep{r0}|rep{r1}"] = mcnemar(
                    [(right(X[(ln, it, r0)]), right(X[(ln, it, r1)])) for ln, it in keys])
    return out


def compare(a) -> int:
    A, B = load_arm(a.a, a.set)["finals"], load_arm(a.b, a.set)["finals"]
    out = {"a": a.a, "b": a.b, "set": a.set, "difference": "b - a, score fraction; 95% from resampling items",
           "cells": {}}
    for cell in sorted(set(A) & set(B)):
        print(f"\n{a.b} - {a.a}, {cell} ({a.set})")
        res = {}
        for ln in LENGTHS + [None]:
            m = boot_mean(paired(A[cell], B[cell], ln))
            if m:
                res[ln or "all"] = m
                print(f"  {ln or 'all':>5}: {m[0]:+.3f} [{m[1]:+.3f}, {m[2]:+.3f}]  items {m[3]}")
        d4, d128 = paired(A[cell], B[cell], "4k"), paired(A[cell], B[cell], "128k")
        inter = boot_mean({i: d128[i] - d4[i] for i in set(d4) & set(d128)})
        if inter:
            res["128k_minus_4k"] = inter
            print(f"  128k difference minus 4k difference: {inter[0]:+.3f} [{inter[1]:+.3f}, {inter[2]:+.3f}]")
        res["flips"] = flip_tables(A[cell], B[cell])
        for kind in ("between", "floor"):
            for name, m in res["flips"][kind].items():
                print(f"  every field correct, {kind} {name}: discordant {m['discordant']} of {m['pairs']} "
                      f"(a only {m['a_only']}, b only {m['b_only']}), exact p {m['p_exact']}")
        out["cells"][cell] = res
    for arm, X in ((a.a, A), (a.b, B)):           # turns - single within an arm, same items
        for cell in sorted(c for c in X if c.startswith("turns")):
            if "single" not in X:
                continue
            strip = lambda d: {(k[0], k[1]): [] for k in d}  # noqa: E731
            sv, tv = strip(X["single"]), strip(X[cell])
            for k, r in X["single"].items():
                sv[(k[0], k[1])].append(value(r))
            for k, r in X[cell].items():
                tv[(k[0], k[1])].append(value(r))
            print(f"\n{arm}: {cell} - single (same items)")
            res = {}
            for ln in LENGTHS:
                d = {i: statistics.fmean(tv[(l2, i)]) - statistics.fmean(sv[(l2, i)]) for (l2, i) in
                     set(sv) & set(tv) if l2 == ln}
                m = boot_mean(d)
                if m:
                    res[ln] = m
                    print(f"  {ln:>5}: {m[0]:+.3f} [{m[1]:+.3f}, {m[2]:+.3f}]  items {m[3]}")
            out.setdefault("turns_minus_single", {})[f"{arm} {cell}"] = res
    P.write_json_atomic(TASKS / f"compare-{a.a}__{a.b}-{a.set}.json", out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--arm", required=True)
    s.add_argument("--set", default="measured")
    c = sub.add_parser("compare")
    c.add_argument("--a", required=True)
    c.add_argument("--b", required=True)
    c.add_argument("--set", default="measured")
    a = ap.parse_args()
    return summary(a) if a.cmd == "summary" else compare(a)


if __name__ == "__main__":
    sys.exit(main())
