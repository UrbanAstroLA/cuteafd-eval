#!/usr/bin/env python3
"""The reference checkpoint (exlr8-k4) beside the three probe arms, single-message passes 1 and 2 only. Standard
library only.

  reference.py        prints the tables and writes REFERENCE.json beside this file

Reads samples.csv (probe arms) and samples-reference.csv (reference checkpoint), both beside this file; only the
rows of single-rep0 and single-rep1 are used. Same request score and interval as posthoc.py (the frozen rule:
b - a, item as the unit, repeats averaged within the item, 10,000 item resamples, seed 5).

The reference arm was added after the measured results were read, and it differs from the probe arms in the whole
checkpoint, not in one setting: every interval here that involves it is post hoc, and a difference from a probe arm
is not attributed to any one tensor group.

Sections of the output
  requests, errors, prompt_tokens_equal_to_anchor
  by_length      per arm and length (and all): item-mean score with interval, score per pass, requests with every
                 field right, outcome classes (right, 1 wrong, 2 wrong, 3+ wrong, cap, repetition), score of the
                 finished replies alone, medians of completion tokens, reasoning characters, decode speed, time to
                 first chunk
  by_family      per arm, family and length: requests, every field right, unfinished, score
  paired         b - a on score and on every-field-right, per length, all lengths, 4k+16k and 64k+128k pooled
  flip_floor     per arm: of 240 item-length pairs, how many change between right and not right from pass 1 to pass 2
  discordant     per pair and pass: [b right and a not, a right and b not]
  agreement      item-length-pass cells where all four are right, and where none is
"""
import csv, json, random, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ARMS = ("anchor", "hqa", "compact", "exlr8-k4"); LS = ("4k", "16k", "64k", "128k"); PS = ("single-rep0", "single-rep1")
FAMS = ("join", "ledger", "trace"); BOOT = 10_000

INT = ("fields", "correct", "prompt_tokens", "completion_tokens", "reasoning_chars")
def read(name):
    rows = list(csv.DictReader(open(HERE / name, newline="")))
    for r in rows:
        for k in INT: r[k] = int(r[k]) if r[k] != "" else None
        for k in ("ttft_s", "decode_tok_s"): r[k] = float(r[k]) if r[k] != "" else None
    return rows
ROWS = [r for r in read("samples.csv") + read("samples-reference.csv") if r["pass"] in PS and r["final"] == "1"]
def load(arm, ps):
    return {(r["item"], r["length"]): r for r in ROWS if r["arm"] == arm and r["pass"] == ps}
def value(r):
    return r["correct"] / r["fields"] if r["finish_class"] == "stop" and r["fields"] else 0.0
def cls(r):
    if r["finish_class"] != "stop": return r["finish_class"]
    w = r["fields"] - r["correct"]
    return "right" if w == 0 else "1 wrong" if w == 1 else "2 wrong" if w == 2 else "3+ wrong"
def boot5(per_item):
    vals = [per_item[i] for i in sorted(per_item)]; rng, n = random.Random(5), len(vals)
    d = sorted(st.fmean(vals[rng.randrange(n)] for _ in range(n)) for _ in range(BOOT))
    return [round(st.fmean(vals), 4), round(d[int(0.025 * BOOT)], 4), round(d[int(0.975 * BOOT) - 1], 4), n]

F = {a: {ps: load(a, ps) for ps in PS} for a in ARMS}
items = sorted({k[0] for k in F["anchor"][PS[0]]}); fam = {r["item"]: r["family"] for r in F["anchor"][PS[0]].values()}
out = {"source": ["samples.csv", "samples-reference.csv"], "passes": PS, "sign": "b - a",
       "note": "exlr8-k4 is a reference checkpoint added after the results were read; it differs from the probe arms in the whole checkpoint",
       "requests": {a: {ps: len(F[a][ps]) for ps in PS} for a in ARMS},
       "errors": {a: sum(r["status"] != "ok" for ps in PS for r in F[a][ps].values()) for a in ARMS},
       "prompt_tokens_equal_to_anchor": {a: [sum(F[a][ps][k]["prompt_tokens"] == F["anchor"][ps][k]["prompt_tokens"] for ps in PS for k in F[a][ps]), sum(len(F[a][ps]) for ps in PS)] for a in ARMS}}
def rows(a, L=None, f=None, passes=PS):
    return [r for ps in passes for (i, l), r in F[a][ps].items() if (L is None or l == L) and (f is None or fam[i] == f)]
sb = {}
for a in ARMS:
    for L in LS + (None,):
        rs = rows(a, L)
        per = defaultdict(list)
        for ps in PS:
            for (i, l), r in F[a][ps].items():
                if L is None or l == L: per[i].append(value(r))
        sb.setdefault(a, {})[L or "all"] = {
            "n": len(rs), "score": boot5({i: st.fmean(v) for i, v in per.items()}),
            "score_by_pass": [round(st.fmean(value(r) for r in rows(a, L, passes=(ps,))), 4) for ps in PS],
            "right": sum(cls(r) == "right" for r in rs), "classes": dict(Counter(cls(r) for r in rs)),
            "score_finished_only": round(st.fmean(value(r) for r in rs if r["finish_class"] == "stop"), 4),
            "completion_tokens_median": st.median(r["completion_tokens"] for r in rs),
            "completion_tokens_p90": sorted(r["completion_tokens"] for r in rs)[int(0.9 * len(rs))],
            "reasoning_chars_median": st.median(r["reasoning_chars"] for r in rs),
            "decode_tok_s_median": round(st.median(r["decode_tok_s"] for r in rs if r["decode_tok_s"]), 1),
            "ttft_s_median": round(st.median(r["ttft_s"] for r in rs if r["ttft_s"] is not None), 1)}
out["by_length"] = sb
out["by_family"] = {a: {f: {L: {"n": len(rows(a, L, f)), "right": sum(cls(r) == "right" for r in rows(a, L, f)),
                                "unfinished": sum(r["finish_class"] != "stop" for r in rows(a, L, f)),
                                "score": round(st.fmean(value(r) for r in rows(a, L, f)), 4)} for L in LS} for f in FAMS} for a in ARMS}
def diff(a, b, Ls=None, f=None, strict=False):
    acc = defaultdict(list)
    for ps in PS:
        for (i, l), ra in F[a][ps].items():
            if (Ls is None or l in Ls) and (f is None or fam[i] == f):
                g = (lambda r: float(value(r) == 1.0)) if strict else value
                acc[i].append(g(F[b][ps][(i, l)]) - g(ra))
    return boot5({i: st.fmean(v) for i, v in acc.items()})
PAIRS = [(a, "exlr8-k4") for a in ARMS[:3]] + [("anchor", "hqa"), ("anchor", "compact"), ("compact", "hqa")]
out["paired"] = {f"{b} - {a}": {"score": {**{L: diff(a, b, (L,)) for L in LS}, "all": diff(a, b), "4k+16k": diff(a, b, ("4k", "16k")), "64k+128k": diff(a, b, ("64k", "128k"))},
                                "every_field_right": {**{L: diff(a, b, (L,), strict=True) for L in LS}, "all": diff(a, b, strict=True), "64k+128k": diff(a, b, ("64k", "128k"), strict=True)},
                                "ledger_64k+128k_score": diff(a, b, ("64k", "128k"), "ledger")} for a, b in PAIRS}
keys = sorted(F["anchor"][PS[0]])
R = lambda a, ps, k: cls(F[a][ps][k]) == "right"
out["flip_floor"] = {a: sum(R(a, PS[0], k) != R(a, PS[1], k) for k in keys) for a in ARMS}
out["discordant"] = {f"{b} vs {a}": {ps: [sum(R(b, ps, k) and not R(a, ps, k) for k in keys), sum(R(a, ps, k) and not R(b, ps, k) for k in keys)] for ps in PS} for a, b in PAIRS}
out["agreement"] = {"all_four_right": sum(all(R(a, ps, k) for a in ARMS) for ps in PS for k in keys), "none_right": sum(not any(R(a, ps, k) for a in ARMS) for ps in PS for k in keys), "of": 2 * len(keys)}
(HERE / "REFERENCE.json").write_text(json.dumps(out, indent=1) + "\n")

f3 = lambda m: f"{m[0]:+.3f} [{m[1]:+.3f}, {m[2]:+.3f}]"
print("requests", out["requests"], "errors", out["errors"], "ptok==anchor", out["prompt_tokens_equal_to_anchor"])
print("\nscore by length (two passes; item mean) [per pass]")
for a in ARMS: print(f" {a:9s}", "  ".join(f"{L}: {sb[a][L]['score'][0]:.3f} {sb[a][L]['score_by_pass']}" for L in LS + ("all",)))
print("\nevery field right (of 120; all of 480)")
for a in ARMS: print(f" {a:9s}", "  ".join(f"{L}: {sb[a][L]['right']}" for L in LS + ("all",)))
print("\nclasses, all lengths"); [print(f" {a:9s}", sb[a]["all"]["classes"]) for a in ARMS]
print("\nunfinished by length"); [print(f" {a:9s}", {L: sb[a][L]['n'] - sum(v for k, v in sb[a][L]['classes'].items() if k not in ('cap', 'repetition')) for L in LS}) for a in ARMS]
print("\npaired differences")
for k, v in out["paired"].items():
    print(f" {k}\n   score  " + "  ".join(f"{L}: {f3(v['score'][L])}" for L in LS) + f"\n          all: {f3(v['score']['all'])}  4k+16k: {f3(v['score']['4k+16k'])}  64k+128k: {f3(v['score']['64k+128k'])}  ledger 64k+128k: {f3(v['ledger_64k+128k_score'])}"
          + f"\n   strict all: {f3(v['every_field_right']['all'])}  64k+128k: {f3(v['every_field_right']['64k+128k'])}  128k: {f3(v['every_field_right']['128k'])}")
print("\nby family: right/n [unfinished]")
for a in ARMS:
    for f in FAMS: print(f" {a:9s}{f:7s}", "  ".join(f"{L}: {out['by_family'][a][f][L]['right']}/{out['by_family'][a][f][L]['n']}[{out['by_family'][a][f][L]['unfinished']}]" for L in LS))
print("\nflip floor (of 240)", out["flip_floor"]); print("discordant [b only, a only]", out["discordant"]); print("agreement", out["agreement"])
print("\ndescriptive: median completion tokens / p90 / reasoning chars / decode tok/s / ttft s")
for a in ARMS:
    for L in LS: d = sb[a][L]; print(f" {a:9s}{L:5s} {d['completion_tokens_median']:7.0f} {d['completion_tokens_p90']:6d} {d['reasoning_chars_median']:7.0f} {d['decode_tok_s_median']:6.1f} {d['ttft_s_median']:6.1f}")
