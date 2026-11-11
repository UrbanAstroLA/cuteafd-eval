#!/usr/bin/env python3
"""Recomputes the published scores, differences and intervals of the graded task runs from samples.csv. Standard library only.

  posthoc.py [samples.csv]        prints the tables and writes POSTHOC.json beside this file

Sections of the output
  frozen_rule          the protocol's paired differences (drivers/analyze_tasks.py compare), recomputed from the
                       published table: per cell and length, b - a, item as the unit, 95% interval from resampling
                       items (10,000 draws, seed 5)
  score_by_length      per arm, cell and length: mean item score, share of requests with every field right,
                       finish classes, and the score of the finished replies alone
  by_family            the same per task family (single message)
  turns_minus_single   per arm and length: 8-turn score minus single-message score, same items
  long_context_pooled  POST HOC (added after the results were read): 64K and 127K pooled, and 4K and 16K pooled
  ledger_alone         by family, outside the frozen comparison rule: paired differences on `ledger` alone, per length
  model_written_share  8-turn pass: tokens the model wrote in the eight delivery turns, as a share of the prompt
                       of the question turn
  intermediate_caps    8-turn pass: delivery turns that ran to the acknowledgement cap, and delivery turns whose
                       reply was not the requested acknowledgement

Score of a request: correct / fields when it finished with `stop`, otherwise 0. Repeats of an item are averaged
within the item before anything is compared. Sign: b - a.
"""
import csv
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ARMS = ("anchor", "hqa", "compact")
PAIRS = (("anchor", "hqa"), ("anchor", "compact"), ("compact", "hqa"))
LENGTHS = ("4k", "16k", "64k", "128k")
SINGLE, TURNS = ("single-rep0", "single-rep1"), ("turns-p8-rep0",)
BOOT = 10_000


def read(path):
    rows = list(csv.DictReader(open(path, newline="")))
    for r in rows:
        for k in ("rep", "turn", "final", "seed", "fields", "correct", "prompt_tokens", "completion_tokens",
                  "cached_tokens", "reasoning_chars", "content_chars"):
            r[k] = int(r[k]) if r[k] != "" else None
        for k in ("ttft_s", "decode_tok_s"):
            r[k] = float(r[k]) if r[k] != "" else None
    return rows


def value(r):
    return r["correct"] / r["fields"] if r["finish_class"] == "stop" and r["fields"] else 0.0


def boot5(per_item):
    """drivers/analyze_tasks.py boot_mean: seed 5, fmean, percentile indices 250 and 9749."""
    vals = [per_item[i] for i in sorted(per_item)]
    rng, n = random.Random(5), len(vals)
    draws = sorted(statistics.fmean(vals[rng.randrange(n)] for _ in range(n)) for _ in range(BOOT))
    return [round(statistics.fmean(vals), 4), round(draws[int(0.025 * BOOT)], 4),
            round(draws[int(0.975 * BOOT) - 1], 4), n]


def boot(vals, seed):
    """The post hoc and exploratory readings: plain mean, percentile indices 250 and 9750."""
    rng, m = random.Random(seed), len(vals)
    b = sorted(sum(vals[rng.randrange(m)] for _ in range(m)) / m for _ in range(BOOT))
    return [round(sum(vals) / m, 4), round(b[int(0.025 * BOOT)], 4), round(b[int(0.975 * BOOT)], 4), m]


def main(path=HERE / "samples.csv"):
    rows = read(path)
    F = defaultdict(dict)                       # F[arm][pass][(item, length)] = final row
    for r in rows:
        if r["final"] and r["status"] == "ok":
            F[r["arm"]].setdefault(r["pass"], {})[(r["item"], r["length"])] = r
    items = sorted({k[0] for k in F["anchor"]["single-rep0"]})
    fam = {r["item"]: r["family"] for r in rows}
    out = {"source": "samples.csv", "sign": "b - a", "unit": "item (60; 20 per family)",
           "request_score": "correct / fields if finish_class == stop else 0"}

    def cellpasses(cell):
        return SINGLE if cell == "single" else TURNS

    # --- frozen rule ------------------------------------------------------------------------------------------
    fr = {}
    for a, b in PAIRS:
        for cell in ("single", "turns-p8"):
            res = {}
            for ln in LENGTHS + (None,):
                acc = defaultdict(list)
                for ps in cellpasses(cell):
                    for (it, L), ra in F[a][ps].items():
                        if (ln is None or L == ln) and (it, L) in F[b][ps]:
                            acc[it].append(value(F[b][ps][(it, L)]) - value(ra))
                res[ln or "all"] = boot5({i: statistics.fmean(v) for i, v in acc.items()})
            fr.setdefault(f"{b} - {a}", {})[cell] = res
    out["frozen_rule"] = fr

    # --- score by length, by family ---------------------------------------------------------------------------
    sb, bf = {}, {}
    for arm in ARMS:
        for cell in ("single", "turns-p8"):
            for ln in LENGTHS:
                rs = [F[arm][ps][(i, ln)] for ps in cellpasses(cell) for i in items]
                per = {i: statistics.fmean(value(F[arm][ps][(i, ln)]) for ps in cellpasses(cell)) for i in items}
                fin = defaultdict(int)
                for r in rs:
                    fin[r["finish_class"]] += 1
                sb.setdefault(arm, {}).setdefault(cell, {})[ln] = {
                    "requests": len(rs), "score": round(statistics.fmean(per.values()), 4),
                    "every_field_right": round(sum(value(r) == 1.0 for r in rs) / len(rs), 4),
                    "finish": dict(fin), "unfinished": sum(r["finish_class"] != "stop" for r in rs),
                    "score_finished_only": round(statistics.fmean(value(r) for r in rs if r["finish_class"] == "stop"), 6),
                    "reasoning_chars_median": statistics.median(r["reasoning_chars"] for r in rs),
                    "completion_tokens_median": statistics.median(r["completion_tokens"] for r in rs),
                    "decode_tok_s_median": statistics.median(r["decode_tok_s"] for r in rs if r["decode_tok_s"]),
                    "ttft_s_median": statistics.median(r["ttft_s"] for r in rs if r["ttft_s"] is not None)}
        for f in ("join", "ledger", "trace"):
            for ln in LENGTHS:
                rs = [F[arm][ps][(i, ln)] for ps in SINGLE for i in items if fam[i] == f]
                bf.setdefault(arm, {}).setdefault(f, {})[ln] = {
                    "score": round(statistics.fmean(value(r) for r in rs), 4),
                    "every_field_right": [sum(value(r) == 1.0 for r in rs), len(rs)],
                    "unfinished": sum(r["finish_class"] != "stop" for r in rs),
                    "score_finished_only": round(statistics.fmean(value(r) for r in rs if r["finish_class"] == "stop"), 6)}
    out["score_by_length"], out["by_family"] = sb, bf

    # --- turns minus single -----------------------------------------------------------------------------------
    ts = {}
    for arm in ARMS:
        for ln in LENGTHS:
            d = {i: value(F[arm]["turns-p8-rep0"][(i, ln)])
                 - statistics.fmean(value(F[arm][ps][(i, ln)]) for ps in SINGLE) for i in items}
            ts.setdefault(arm, {})[ln] = boot5(d)
    out["turns_minus_single"] = ts

    # --- post hoc: long context pooled ------------------------------------------------------------------------
    def sc(arm, passes, i, Ls, strict):
        v = [value(F[arm][ps][(i, L)]) for ps in passes for L in Ls]
        return sum((x == 1.0) if strict else x for x in v) / len(v)

    lc = {"note": "post hoc; not in the frozen protocol; this section holds 48 intervals, of which two exclude 0",
          "interval": "10,000 item resamples, seed 7"}
    for name, Ls in (("4k+16k", ("4k", "16k")), ("64k+128k", ("64k", "128k"))):
        for a, b in PAIRS:
            for scope, ids in (("all families", items), ("ledger", [i for i in items if fam[i] == "ledger"])):
                for strict in (False, True):
                    for label, passes in (("single", SINGLE), ("single+turns", SINGLE + TURNS)):
                        d = [sc(b, passes, i, Ls, strict) - sc(a, passes, i, Ls, strict) for i in ids]
                        lc.setdefault(name, {}).setdefault(f"{b} - {a}", {}).setdefault(scope, {}).setdefault(
                            "every_field_right" if strict else "score", {})[label] = boot(d, 7)
    out["long_context_pooled"] = lc

    # --- exploratory: ledger alone ----------------------------------------------------------------------------
    la = {"note": "by family, as the protocol asks of every table; outside the frozen comparison rule", "interval": "10,000 item resamples, seed 20261111"}
    ids = [i for i in items if fam[i] == "ledger"]
    for label, passes in (("single", SINGLE), ("turns-p8", TURNS)):
        for a, b in PAIRS:
            for ln in LENGTHS:
                d = [sc(b, passes, i, (ln,), False) - sc(a, passes, i, (ln,), False) for i in ids]
                la.setdefault(label, {}).setdefault(f"{b} - {a}", {})[ln] = boot(d, 20261111)
    out["ledger_alone"] = la

    # --- 8-turn pass: what the history was made of ------------------------------------------------------------
    mw, ic = {}, {}
    for arm in ARMS:
        S = defaultdict(lambda: {"dec": 0, "caps": 0, "noack": 0, "noack_stop": 0})
        for r in rows:
            if r["arm"] == arm and r["pass"] == "turns-p8-rep0":
                s = S[(r["item"], r["length"])]
                if r["final"]:
                    s["pt"] = r["prompt_tokens"]
                else:
                    s["dec"] += r["completion_tokens"] or 0
                    s["caps"] += r["finish_class"] != "stop"
                    s["noack"] += r["ack_ok"] == "0"
                    s["noack_stop"] += r["ack_ok"] == "0" and r["finish_class"] == "stop"
        for ln in LENGTHS:
            f = [s["dec"] / s["pt"] for (i, L), s in S.items() if L == ln and "pt" in s]
            mw.setdefault(arm, {})[ln] = {"median": round(statistics.median(f), 4), "max": round(max(f), 4),
                                          "sessions": len(f)}
        ic[arm] = {"delivery_turns": 8 * len(S), "sessions": len(S),
                   "turns_not_stop": sum(s["caps"] for s in S.values()),
                   "turns_not_the_acknowledgement": sum(s["noack"] for s in S.values()),
                   "of_which_finished_with_stop": sum(s["noack_stop"] for s in S.values()),
                   "sessions_with_one": sum(s["caps"] > 0 for s in S.values()),
                   "most_in_one_session": max(s["caps"] for s in S.values())}
    out["model_written_share"], out["intermediate_caps"] = mw, ic

    (HERE / "POSTHOC.json").write_text(json.dumps(out, indent=1) + "\n")

    def f3(m):
        return f"{m[0]:+.3f} [{m[1]:+.3f}, {m[2]:+.3f}]"
    print("frozen rule, single message, all lengths:", {k: f3(v["single"]["all"]) for k, v in fr.items()})
    print("long context pooled (64k+128k), single:")
    for k, v in lc["64k+128k"].items():
        print(f"  {k}: all {f3(v['all families']['score']['single'])}  ledger {f3(v['ledger']['score']['single'])}"
              f"  ledger strict {f3(v['ledger']['every_field_right']['single'])}"
              f"  (with turns {f3(v['ledger']['every_field_right']['single+turns'])})")
    print("model-written share of the question-turn prompt, median:",
          {a: {ln: v["median"] for ln, v in d.items()} for a, d in mw.items()})
    print("delivery turns not finished with stop:", ic)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
