#!/usr/bin/env python3
"""How the replies of the four single-message passes ended, and what the reasoning of the unfinished ones was made
of. Descriptive and post hoc: written on 2026-11-12 after the four-pass results were read. Standard library only.

  endings.py        prints the tables and writes ENDINGS.json beside this file

Reads samples.csv, samples-reference.csv and samples-extension.csv (how each request finished and scored) and
endings.csv (counts over each reply's reasoning text, made by make_endings.py from the saved replies; no text).

Terms
  unfinished   finish class other than `stop`: `cap` (the reply reached the 32,768-token reply cap) or
               `repetition` (the engine's loop abort). Scores 0 under the frozen rule.
  step line    a reasoning line that carries the record following the previous record-carrying line's record in
               the prompt (make_endings.py): the reply is writing the prompt's records out in the prompt's order
  copy share   characters on step lines / characters of the reasoning
  copying      copy share >= 0.5 (the 44 unfinished replies are listed with their shares, so another threshold
               can be applied by a reader)
  copy run     20 or more consecutive step lines somewhere in the reasoning
  repeat share characters on lines (of 8 or more characters) that occurred earlier in the same reasoning / characters
Intervals: b - a per item, repeats averaged within the item, 10,000 item resamples, seed 5 (the frozen rule's
resampling, applied here to the share of unfinished replies; these are post hoc readings, many per table).
"""
import csv, json, random, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ARMS = ("anchor", "hqa", "compact", "exlr8-k4"); LS = ("4k", "16k", "64k", "128k"); FAMS = ("join", "ledger", "trace")
ALLP = tuple(f"single-rep{i}" for i in range(4))
SETS = {"p12": ALLP[:2], "p34": ALLP[2:], "p1234": ALLP}
BOOT, COPY, RUN_NOTE = 10_000, 0.5, "copy run = 20 or more consecutive step lines"
INT = ("lines", "chars", "walk_lines", "walk_chars", "step_lines", "step_chars", "reached", "records", "repeat_chars")

R = {}
for n in ("samples.csv", "samples-reference.csv", "samples-extension.csv"):
    for r in csv.DictReader(open(HERE / n, newline="")):
        if r["pass"] in ALLP and r["final"] == "1":
            R[(r["arm"], r["pass"], r["item"], r["length"])] = r
for e in csv.DictReader(open(HERE / "endings.csv", newline="")):
    r = R[(e["arm"], e["pass"], e["item"], e["length"])]
    assert r["seed"] == e["seed"]
    for k in INT: r[k] = int(e[k])
    r["run"] = e["run_start_chars"] != ""
    r["run_start"] = int(e["run_start_chars"]) if r["run"] else None
    r["answers_before"] = int(e["answers_before"]) if e["answers_before"] != "" else None
    r["copy_share"] = r["step_chars"] / r["chars"] if r["chars"] else 0.0
    r["repeat_share"] = r["repeat_chars"] / r["chars"] if r["chars"] else 0.0
ROWS = list(R.values())
assert len(ROWS) == 3840 and all("copy_share" in r for r in ROWS)
for r in ROWS:
    r["fields"], r["correct"], r["tok"] = int(r["fields"]), int(r["correct"]), int(r["completion_tokens"])
    r["done"] = r["finish_class"] == "stop"
items = sorted({r["item"] for r in ROWS})

def sel(a=None, PS=ALLP, L=None, f=None):
    return [r for r in ROWS if (a is None or r["arm"] == a) and r["pass"] in PS and (L is None or r["length"] == L)
            and (f is None or r["family"] == f)]
def boot5(vals):
    rng, n = random.Random(5), len(vals)
    d = sorted(st.fmean(vals[rng.randrange(n)] for _ in range(n)) for _ in range(BOOT))
    return [round(st.fmean(vals), 4), round(d[int(0.025 * BOOT)], 4), round(d[int(0.975 * BOOT) - 1], 4), n]
def paired(a, b, PS, L, f, g):
    acc = defaultdict(list)
    for r in sel(b, PS, L, f): acc[r["item"]].append(g(r))
    for r in sel(a, PS, L, f): acc[r["item"]].append(-g(r))
    k = len(PS)
    return boot5([sum(acc[i]) / k for i in sorted(acc)])
def ended(rs):
    c = Counter()
    for r in rs:
        if not r["done"]: c["reply cap" if r["finish_class"] == "cap" else "loop abort"] += 1
        else: c[("every field right", "1 wrong", "2 wrong")[w] if (w := r["fields"] - r["correct"]) < 3 else "3 or more wrong"] += 1
    return {k: c[k] for k in ("every field right", "1 wrong", "2 wrong", "3 or more wrong", "reply cap", "loop abort")}
def kind(r):
    return ("copying" if r["copy_share"] >= COPY else "other") + (", cap" if r["finish_class"] == "cap" else ", loop abort")
KINDS = ("copying, cap", "copying, loop abort", "other, cap", "other, loop abort")

out = {"source": ["samples.csv", "samples-reference.csv", "samples-extension.csv", "endings.csv"],
       "note": "descriptive and post hoc (2026-11-12, after the four-pass results were read); every interval here is one of many",
       "copying_threshold": COPY, "copy_run": RUN_NOTE, "reply_cap_tokens": 32768,
       "pass_sets": {k: list(v) for k, v in SETS.items()}}
out["how_each_request_ended"] = {a: {s: {**{L: ended(sel(a, PS, L)) for L in LS}, "all": ended(sel(a, PS))}
                                     for s, PS in SETS.items()} for a in ARMS}
un = [r for r in ROWS if not r["done"]]
out["unfinished"] = {
    "total": len(un), "with_answer_text": sum(int(r["content_chars"]) > 0 for r in un),
    "by_arm_family_length": {a: {f: {L: len([r for r in un if r["arm"] == a and r["family"] == f and r["length"] == L])
                                     for L in LS} for f in FAMS} for a in ARMS},
    "by_arm_family_kind": {a: {f: {k: len([r for r in un if r["arm"] == a and r["family"] == f and kind(r) == k])
                                   for k in KINDS} for f in FAMS} for a in ARMS},
    "by_arm_kind": {a: {s: {k: len([r for r in un if r["arm"] == a and r["pass"] in PS and kind(r) == k]) for k in KINDS}
                        for s, PS in SETS.items()} for a in ARMS},
    "distinct_items": {a: len({r["item"] for r in un if r["arm"] == a}) for a in ARMS},
    "items_in_two_or_more_arms": sorted(i for i in items if len({r["arm"] for r in un if r["item"] == i}) >= 2),
    "list": [{"arm": r["arm"], "pass": int(r["pass"][-1]) + 1, "item": r["item"], "length": r["length"],
              "finish": r["finish_class"], "tokens": r["tok"], "reasoning_chars": r["chars"],
              "copy_share": round(r["copy_share"], 3), "repeat_share": round(r["repeat_share"], 3),
              "run_start_chars": r["run_start"], "reached": r["reached"], "records": r["records"],
              "answers_before": r["answers_before"], "kind": kind(r)}
             for r in sorted(un, key=lambda r: (ARMS.index(r["arm"]), r["pass"], r["item"], LS.index(r["length"])))]}

# join at 127K: copy runs in every reply, finished or not
j = {}
for a in ARMS:
    for s, PS in SETS.items():
        rs = sel(a, PS, "128k", "join"); run = [r for r in rs if r["run"]]
        j.setdefault(a, {})[s] = {
            "requests": len(rs), "unfinished": sum(not r["done"] for r in rs),
            "with_copy_run": len(run), "copy_run_finished": sum(r["done"] for r in run),
            "copy_run_unfinished": sum(not r["done"] for r in run),
            "unfinished_without_copy_run": sum(not r["done"] and not r["run"] for r in rs),
            "copy_run_unfinished_all_8_docks_before": sum(not r["done"] and r["answers_before"] == 8 for r in run),
            "copy_run_unfinished_7_docks_before": sum(not r["done"] and r["answers_before"] == 7 for r in run),
            "copy_run_finished_score": round(st.fmean(r["correct"] / r["fields"] for r in run if r["done"]), 4) if any(r["done"] for r in run) else None,
            "no_copy_run_finished_score": round(st.fmean(r["correct"] / r["fields"] for r in rs if r["done"] and not r["run"]), 4),
            "items_with_unfinished": len({r["item"] for r in rs if not r["done"]})}
out["join_127k"] = j
out["join_127k_items_with_unfinished_any_arm"] = len({r["item"] for r in sel(None, ALLP, "128k", "join") if not r["done"]})
out["copy_runs_all_requests"] = {a: {f: {L: {"requests": len(rs := sel(a, ALLP, L, f)), "with_copy_run": sum(r["run"] for r in rs),
                                              "of_which_unfinished": sum(r["run"] and not r["done"] for r in rs)}
                                         for L in LS} for f in FAMS} for a in ARMS}

# paired differences in the share of unfinished replies
pd = {}
for a, b in (("anchor", "compact"), ("hqa", "compact"), ("exlr8-k4", "compact"), ("anchor", "hqa"), ("anchor", "exlr8-k4")):
    for s, PS in SETS.items():
        pd.setdefault(f"{b} - {a}", {})[s] = {
            "unfinished_127k": paired(a, b, PS, "128k", None, lambda r: float(not r["done"])),
            "unfinished_127k_join": paired(a, b, PS, "128k", "join", lambda r: float(not r["done"])),
            "unfinished_127k_ledger": paired(a, b, PS, "128k", "ledger", lambda r: float(not r["done"])),
            "unfinished_64k_ledger": paired(a, b, PS, "64k", "ledger", lambda r: float(not r["done"]))}
out["paired_unfinished_share"] = pd

# score at 127K with and without the join replies that did not finish
sc = {}
for a in ARMS:
    for s, PS in SETS.items():
        rs = sel(a, PS, "128k")
        val = lambda r: r["correct"] / r["fields"] if r["done"] else 0.0
        sc.setdefault(a, {})[s] = {
            "score": round(st.fmean(val(r) for r in rs), 4),
            "by_family": {f: {"score": round(st.fmean(val(r) for r in rs if r["family"] == f), 4),
                              "unfinished": sum(not r["done"] for r in rs if r["family"] == f),
                              "finished_only": round(st.fmean(val(r) for r in rs if r["family"] == f and r["done"]), 4),
                              "requests": sum(r["family"] == f for r in rs)} for f in FAMS},
            "finished_only": round(st.fmean(val(r) for r in rs if r["done"]), 4)}
out["score_127k"] = sc
# where a 127K difference in score sits: each family is 80 of the 240 requests, so its share of b - a is its own difference / 3
val = lambda r: r["correct"] / r["fields"] if r["done"] else 0.0
fm = lambda a, f=None: st.fmean(val(r) for r in sel(a, ALLP, "128k", f))
out["gap_127k_by_family"] = {f"{b} - {a}": {"all": round(fm(b) - fm(a), 4), **{f: round((fm(b, f) - fm(a, f)) / 3, 4) for f in FAMS}}
                             for a, b in (("compact", "anchor"), ("compact", "hqa"), ("compact", "exlr8-k4"))}
out["join_127k_unfinished_by_pass"] = {a: [sum(not r["done"] for r in sel(a, (p,), "128k", "join")) for p in ALLP] for a in ARMS}

# length of the replies that finished
def q(v, p): v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))]
out["finished_reply_tokens"] = {a: {L: {"n": len(t := [r["tok"] for r in sel(a, ALLP, L) if r["done"]]), "median": int(st.median(t)),
                                        "p90": q(t, 0.90), "p99": q(t, 0.99), "max": max(t),
                                        "over_half_cap": sum(x > 16384 for x in t)} for L in LS} for a in ARMS}

(HERE / "ENDINGS.json").write_text(json.dumps(out, indent=1) + "\n")
f3 = lambda m: f"{m[0]:+.3f} [{m[1]:+.3f}, {m[2]:+.3f}]"
print("how each request ended, four passes, all lengths / 127K")
for a in ARMS: print(f"  {a:9}", list(out["how_each_request_ended"][a]["p1234"]["all"].values()), list(out["how_each_request_ended"][a]["p1234"]["128k"].values()))
print("unfinished:", out["unfinished"]["total"], "with answer text:", out["unfinished"]["with_answer_text"])
for a in ARMS: print(f"  {a:9}", out["unfinished"]["by_arm_family_length"][a], "|", out["unfinished"]["by_arm_family_kind"][a])
print("  distinct items", out["unfinished"]["distinct_items"], "shared", out["unfinished"]["items_in_two_or_more_arms"])
print("join 127K")
for a in ARMS:
    for s in SETS: print(f"  {a:9} {s:6}", {k: v for k, v in j[a][s].items()})
print("join 127K items with an unfinished reply in any arm:", out["join_127k_items_with_unfinished_any_arm"])
print("paired unfinished share")
for k, v in pd.items():
    for s in SETS: print(f"  {k:20} {s:6}", {m: f3(x) for m, x in v[s].items()})
print("score 127K by family, four passes")
for a in ARMS: print(f"  {a:9}", sc[a]["p1234"])
print("127K gap by family:", out["gap_127k_by_family"]); print("join 127K unfinished by pass:", out["join_127k_unfinished_by_pass"])
print("copy runs, all requests")
for a in ARMS: print(f"  {a:9}", {f: [(d['with_copy_run'], d['of_which_unfinished']) for d in out['copy_runs_all_requests'][a][f].values()] for f in FAMS})
print("finished reply tokens")
for a in ARMS: print(f"  {a:9}", out["finished_reply_tokens"][a])
