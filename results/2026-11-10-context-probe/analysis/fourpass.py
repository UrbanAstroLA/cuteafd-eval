#!/usr/bin/env python3
"""Amendment 1, section A3: the frozen comparison rule applied to four single-message passes per arm, beside the
two-pass result of the frozen protocol. Standard library only.

  fourpass.py        prints the tables and writes FOURPASS.json beside this file

Reads samples.csv (probe arms, passes 1-2), samples-reference.csv (exlr8-k4, passes 1-2) and samples-extension.csv
(all four arms, passes 3-4), all beside this file. Only single-message rows are used.

Rule (frozen, as posthoc.py boot5): request score = correct / fields if the reply finished with `stop`, otherwise 0;
repeats averaged within the item; b - a paired by item; 95% interval from 10,000 item resamples, seed 5.

Every quantity is given for three pass sets:
  p12    passes 1-2   the frozen protocol's result (already published)
  p34    passes 3-4   the added passes alone: data that had not been seen when amendment 1 was written
  p1234  passes 1-4   the amendment's four-pass reading

exlr8-k4 is a reference checkpoint that differs from the probe arms in the whole checkpoint; a difference from a
probe arm is not attributed to one tensor group. The four-pass reading is an extension decided after the two-pass
results were read.
"""
import csv, json, random, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ARMS = ("anchor", "hqa", "compact", "exlr8-k4"); LS = ("4k", "16k", "64k", "128k"); FAMS = ("join", "ledger", "trace")
ALLP = tuple(f"single-rep{i}" for i in range(4))
SETS = {"p12": ALLP[:2], "p34": ALLP[2:], "p1234": ALLP}
BOOT = 10_000

def read(name):
    rows = list(csv.DictReader(open(HERE / name, newline="")))
    for r in rows:
        for k in ("fields", "correct", "prompt_tokens", "completion_tokens", "reasoning_chars"):
            r[k] = int(r[k]) if r[k] != "" else None
        for k in ("ttft_s", "decode_tok_s"): r[k] = float(r[k]) if r[k] != "" else None
    return rows
ROWS = [r for n in ("samples.csv", "samples-reference.csv", "samples-extension.csv") for r in read(n)
        if r["pass"] in ALLP and r["final"] == "1"]
F = {a: {ps: {(r["item"], r["length"]): r for r in ROWS if r["arm"] == a and r["pass"] == ps} for ps in ALLP} for a in ARMS}
items = sorted({k[0] for k in F["anchor"][ALLP[0]]}); fam = {r["item"]: r["family"] for r in F["anchor"][ALLP[0]].values()}
def value(r): return r["correct"] / r["fields"] if r["finish_class"] == "stop" and r["fields"] else 0.0
def right(r): return value(r) == 1.0
def boot5(per_item):
    vals = [per_item[i] for i in sorted(per_item)]; rng, n = random.Random(5), len(vals)
    d = sorted(st.fmean(vals[rng.randrange(n)] for _ in range(n)) for _ in range(BOOT))
    return [round(st.fmean(vals), 4), round(d[int(0.025 * BOOT)], 4), round(d[int(0.975 * BOOT) - 1], 4), n]
def rows(a, PS, L=None, f=None):
    return [r for ps in PS for (i, l), r in F[a][ps].items() if (L is None or l == L) and (f is None or fam[i] == f)]
def mean(a, PS, Ls=None, f=None):
    acc = defaultdict(list)
    for ps in PS:
        for (i, l), r in F[a][ps].items():
            if (Ls is None or l in Ls) and (f is None or fam[i] == f): acc[i].append(value(r))
    return boot5({i: st.fmean(v) for i, v in acc.items()})
def diff(a, b, PS, Ls=None, f=None, strict=False):
    g = (lambda r: float(right(r))) if strict else value
    acc = defaultdict(list)
    for ps in PS:
        for (i, l), ra in F[a][ps].items():
            if (Ls is None or l in Ls) and (f is None or fam[i] == f): acc[i].append(g(F[b][ps][(i, l)]) - g(ra))
    return boot5({i: st.fmean(v) for i, v in acc.items()})

out = {"source": ["samples.csv", "samples-reference.csv", "samples-extension.csv"], "sign": "b - a",
       "pass_sets": {k: list(v) for k, v in SETS.items()},
       "note": "p1234 is an extension decided after the p12 results were read (amendment 1); exlr8-k4 differs from the probe arms in the whole checkpoint",
       "requests": {a: {ps: len(F[a][ps]) for ps in ALLP} for a in ARMS},
       "errors": {a: sum(r["status"] != "ok" for ps in ALLP for r in F[a][ps].values()) for a in ARMS}}
SCOPES = {**{L: (L,) for L in LS}, "all": None, "4k+16k": ("4k", "16k"), "64k+128k": ("64k", "128k")}
by = {}
for a in ARMS:
    for s, PS in SETS.items():
        for L in LS + (None,):
            rs = rows(a, PS, L)
            by.setdefault(a, {}).setdefault(s, {})[L or "all"] = {
                "n": len(rs), "score": mean(a, PS, None if L is None else (L,)),
                "right": sum(right(r) for r in rs), "finish": dict(Counter(r["finish_class"] for r in rs)),
                "unfinished": sum(r["finish_class"] != "stop" for r in rs),
                "score_finished_only": round(st.fmean(value(r) for r in rs if r["finish_class"] == "stop"), 4),
                "completion_tokens_median": st.median(r["completion_tokens"] for r in rs),
                "reasoning_chars_median": st.median(r["reasoning_chars"] for r in rs),
                "decode_tok_s_median": round(st.median(r["decode_tok_s"] for r in rs if r["decode_tok_s"]), 1),
                "ttft_s_median": round(st.median(r["ttft_s"] for r in rs if r["ttft_s"] is not None), 1)}
    by[a]["score_by_pass"] = {L or "all": [round(st.fmean(value(r) for r in rows(a, (ps,), L)), 4) for ps in ALLP] for L in LS + (None,)}
out["by_length"] = by
out["by_family"] = {a: {f: {L: {s: {"n": len(rows(a, PS, L, f)), "right": sum(right(r) for r in rows(a, PS, L, f)),
                                     "unfinished": sum(r["finish_class"] != "stop" for r in rows(a, PS, L, f)),
                                     "score": round(st.fmean(value(r) for r in rows(a, PS, L, f)), 4)} for s, PS in SETS.items()}
                                for L in LS} for f in FAMS} for a in ARMS}
PAIRS = [("anchor", "hqa"), ("anchor", "compact"), ("compact", "hqa")] + [(a, "exlr8-k4") for a in ARMS[:3]]
pd = {}
for a, b in PAIRS:
    e = pd.setdefault(f"{b} - {a}", {})
    for s, PS in SETS.items():
        e[s] = {"score": {k: diff(a, b, PS, v) for k, v in SCOPES.items()},
                "every_field_right": {k: diff(a, b, PS, SCOPES[k], strict=True) for k in LS + ("all", "64k+128k")},
                "ledger_64k+128k_score": diff(a, b, PS, ("64k", "128k"), "ledger"),
                "by_family_all_lengths": {f: diff(a, b, PS, None, f) for f in FAMS}}
out["paired"] = pd
def excl(m): return m[1] > 0 or m[2] < 0
def walk(d):
    for v in d.values():
        if isinstance(v, dict): yield from walk(v)
        else: yield v
out["intervals_excluding_zero"] = {s: {"count": sum(excl(m) for e in pd.values() for m in walk(e[s])),
                                       "of": sum(1 for e in pd.values() for _ in walk(e[s]))} for s in SETS}
hw = lambda m: (m[2] - m[1]) / 2
out["half_width_ratio_p1234_over_p12"] = {
    "paired_score_all": {k: round(hw(e["p1234"]["score"]["all"]) / hw(e["p12"]["score"]["all"]), 3) for k, e in pd.items()},
    "arm_mean_all": {a: round(hw(by[a]["p1234"]["all"]["score"]) / hw(by[a]["p12"]["all"]["score"]), 3) for a in ARMS},
    "stated_before_the_data": {"paired": "about 0.71", "arm_mean": "0.80 to 0.90"}}
keys = sorted(F["anchor"][ALLP[0]])
out["agreement_p1234"] = {"all_four_arms_right": sum(all(right(F[a][ps][k]) for a in ARMS) for ps in ALLP for k in keys),
                          "no_arm_right": sum(not any(right(F[a][ps][k]) for a in ARMS) for ps in ALLP for k in keys), "of": 4 * len(keys)}
out["times_right_of_4_per_item_length"] = {a: dict(sorted(Counter(sum(right(F[a][ps][k]) for ps in ALLP) for k in keys).items())) for a in ARMS}
(HERE / "FOURPASS.json").write_text(json.dumps(out, indent=1) + "\n")

f3 = lambda m: f"{m[0]:+.3f} [{m[1]:+.3f},{m[2]:+.3f}]" + ("*" if excl(m) else " ")
m3 = lambda m: f"{m[0]:.3f} [{m[1]:.3f},{m[2]:.3f}]"
print("requests", out["requests"]["anchor"], "errors", out["errors"])
print("\nARM SCORE (item mean, interval)")
for a in ARMS:
    for s in SETS: print(f" {a:9s}{s:6s}", "  ".join(f"{L}: {m3(by[a][s][L]['score'])}" for L in LS + ("all",)))
    print(f" {a:9s}by pass all: {by[a]['score_by_pass']['all']}  128k: {by[a]['score_by_pass']['128k']}")
print("\nRIGHT / UNFINISHED by length (p12 of 120, p34 of 120, p1234 of 240)")
for a in ARMS:
    for s in SETS: print(f" {a:9s}{s:6s}", "  ".join(f"{L}: {by[a][s][L]['right']}/{by[a][s][L]['unfinished']}" for L in LS + ("all",)), by[a][s]["all"]["finish"])
print("\nPAIRED b - a, score  (* = interval excludes 0)")
for k, e in pd.items():
    print(f" {k}")
    for s in SETS: print(f"   {s:6s}", "  ".join(f"{sc}: {f3(e[s]['score'][sc])}" for sc in SCOPES))
    for s in SETS: print(f"   {s:6s} strict all: {f3(e[s]['every_field_right']['all'])}  strict 64k+128k: {f3(e[s]['every_field_right']['64k+128k'])}  strict 128k: {f3(e[s]['every_field_right']['128k'])}  ledger 64k+128k: {f3(e[s]['ledger_64k+128k_score'])}")
    for s in SETS: print(f"   {s:6s} family: " + "  ".join(f"{f}: {f3(e[s]['by_family_all_lengths'][f])}" for f in FAMS))
print("\nintervals excluding zero", out["intervals_excluding_zero"])
print("half-width ratio", out["half_width_ratio_p1234_over_p12"])
print("agreement", out["agreement_p1234"]); print("times right of 4", out["times_right_of_4_per_item_length"])
print("\nBY FAMILY p1234: right/n [unfinished]")
for a in ARMS:
    for f in FAMS: print(f" {a:9s}{f:7s}", "  ".join(f"{L}: {out['by_family'][a][f][L]['p1234']['right']}/{out['by_family'][a][f][L]['p1234']['n']}[{out['by_family'][a][f][L]['p1234']['unfinished']}]" for L in LS))
print("\nDESCRIPTIVE p34 / p1234: median completion tokens, reasoning chars, decode tok/s, ttft s")
for a in ARMS:
    for L in LS:
        d, e = by[a]["p34"][L], by[a]["p1234"][L]
        print(f" {a:9s}{L:5s} {d['completion_tokens_median']:7.0f} {d['reasoning_chars_median']:7.0f} {d['decode_tok_s_median']:6.1f} {d['ttft_s_median']:6.1f}   | {e['completion_tokens_median']:7.0f} {e['reasoning_chars_median']:7.0f} {e['decode_tok_s_median']:6.1f} {e['ttft_s_median']:6.1f}")
