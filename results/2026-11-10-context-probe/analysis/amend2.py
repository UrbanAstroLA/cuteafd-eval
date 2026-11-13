#!/usr/bin/env python3
"""Amendment 2, section B4: the fifth configuration, `k325-fp8`, read beside the four earlier arms. Standard library
only.

  amend2.py        prints the tables and writes AMEND2.json beside this file

Reads samples.csv, samples-reference.csv and samples-extension.csv (the four earlier arms, four single-message
passes each), samples-amend2.csv (`k325-fp8`, four passes), endings.csv and endings-amend2.csv (counts over each
reply's reasoning text; no text), and FOURPASS.json and ENDINGS.json, all beside this file.

The four earlier arms are not recomputed differently: this script computes their four-pass figures with the same
rule and stops if any of them differs from FOURPASS.json or ENDINGS.json. The new arm is added beside them.

Rule (frozen, as fourpass.py): request score = correct / fields if the reply finished with `stop`, otherwise 0;
repeats averaged within the item; b - a paired by item; 95% interval from 10,000 item resamples, seed 5. Sign:
b - a, so `k325-fp8 - anchor` below 0 means k325-fp8 scored lower.

Ending terms (make_endings.py and endings.py, unchanged; fixed before this arm's data)
  unfinished   finish class other than `stop`: `cap` (the 32,768-token reply cap) or `repetition` (loop abort)
  step line    a reasoning line that carries the record following the previous record-carrying line's record
  copy share   characters on step lines / characters of the reasoning; `copying` = copy share >= 0.5
  copy run     20 or more consecutive step lines somewhere in the reasoning

`k325-fp8` differs from every other arm in the whole checkpoint (K3.25 routed experts and the official FP8 blocks
outside them), so no difference here is attributed to one component. Its passes ran alone after the others' (not
interleaved): a session effect cannot be excluded by design.
"""
import csv, json, random, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NEW = "k325-fp8"; OLD = ("anchor", "hqa", "compact", "exlr8-k4"); ARMS = OLD + (NEW,)
LS = ("4k", "16k", "64k", "128k"); FAMS = ("join", "ledger", "trace")
ALLP = tuple(f"single-rep{i}" for i in range(4))
BOOT, COPY = 10_000, 0.5
SAMPLES = ("samples.csv", "samples-reference.csv", "samples-extension.csv", "samples-amend2.csv")
ENDINGS = ("endings.csv", "endings-amend2.csv")
INT = ("lines", "chars", "walk_lines", "walk_chars", "step_lines", "step_chars", "reached", "records", "repeat_chars")

R = {}
for n in SAMPLES:
    for r in csv.DictReader(open(HERE / n, newline="")):
        if r["pass"] in ALLP and r["final"] == "1":
            assert (n == "samples-amend2.csv") == (r["arm"] == NEW)
            R[(r["arm"], r["pass"], r["item"], r["length"])] = r
for n in ENDINGS:
    for e in csv.DictReader(open(HERE / n, newline="")):
        r = R[(e["arm"], e["pass"], e["item"], e["length"])]
        assert r["seed"] == e["seed"]
        for k in INT: r[k] = int(e[k])
        r["run"] = e["run_start_chars"] != ""
        r["run_start"] = int(e["run_start_chars"]) if r["run"] else None
        r["answers_before"] = int(e["answers_before"]) if e["answers_before"] != "" else None
        r["copy_share"] = r["step_chars"] / r["chars"] if r["chars"] else 0.0
        r["repeat_share"] = r["repeat_chars"] / r["chars"] if r["chars"] else 0.0
ROWS = list(R.values())
assert len(ROWS) == 4800 and all("copy_share" in r for r in ROWS)
for r in ROWS:
    for k in ("fields", "correct", "prompt_tokens", "completion_tokens", "reasoning_chars", "content_chars"): r[k] = int(r[k])
    for k in ("ttft_s", "decode_tok_s"): r[k] = float(r[k]) if r[k] != "" else None
    r["done"] = r["finish_class"] == "stop"; r["tok"] = r["completion_tokens"]
F = {a: {ps: {(r["item"], r["length"]): r for r in ROWS if r["arm"] == a and r["pass"] == ps} for ps in ALLP} for a in ARMS}
keys = sorted(F["anchor"][ALLP[0]]); items = sorted({k[0] for k in keys}); fam = {r["item"]: r["family"] for r in ROWS}

def value(r): return r["correct"] / r["fields"] if r["done"] and r["fields"] else 0.0
def right(r): return value(r) == 1.0
def boot5(vals):
    rng, n = random.Random(5), len(vals)
    d = sorted(st.fmean(vals[rng.randrange(n)] for _ in range(n)) for _ in range(BOOT))
    return [round(st.fmean(vals), 4), round(d[int(0.025 * BOOT)], 4), round(d[int(0.975 * BOOT) - 1], 4), n]
def rows(a, L=None, f=None, PS=ALLP):
    return [r for ps in PS for (i, l), r in F[a][ps].items() if (L is None or l == L) and (f is None or fam[i] == f)]
def mean(a, Ls=None, f=None):
    acc = defaultdict(list)
    for ps in ALLP:
        for (i, l), r in F[a][ps].items():
            if (Ls is None or l in Ls) and (f is None or fam[i] == f): acc[i].append(value(r))
    return boot5([st.fmean(acc[i]) for i in sorted(acc)])
def diff(a, b, Ls=None, f=None, g=value):
    acc = defaultdict(list)
    for ps in ALLP:
        for (i, l), ra in F[a][ps].items():
            if (Ls is None or l in Ls) and (f is None or fam[i] == f): acc[i].append(g(F[b][ps][(i, l)]) - g(ra))
    return boot5([st.fmean(acc[i]) for i in sorted(acc)])
def length_row(a, L):
    rs = rows(a, L)
    return {"n": len(rs), "score": mean(a, None if L is None else (L,)), "right": sum(right(r) for r in rs),
            "finish": dict(Counter(r["finish_class"] for r in rs)), "unfinished": sum(not r["done"] for r in rs),
            "score_finished_only": round(st.fmean(value(r) for r in rs if r["done"]), 4),
            "completion_tokens_median": st.median(r["completion_tokens"] for r in rs),
            "reasoning_chars_median": st.median(r["reasoning_chars"] for r in rs),
            "decode_tok_s_median": round(st.median(r["decode_tok_s"] for r in rs if r["decode_tok_s"]), 1),
            "ttft_s_median": round(st.median(r["ttft_s"] for r in rs if r["ttft_s"] is not None), 1)}
def family_row(a, f, L):
    rs = rows(a, L, f)
    return {"n": len(rs), "right": sum(right(r) for r in rs), "unfinished": sum(not r["done"] for r in rs),
            "score": round(st.fmean(value(r) for r in rs), 4)}
def ended(rs):
    c = Counter()
    for r in rs:
        if not r["done"]: c["reply cap" if r["finish_class"] == "cap" else "loop abort"] += 1
        else: c[("every field right", "1 wrong", "2 wrong")[w] if (w := r["fields"] - r["correct"]) < 3 else "3 or more wrong"] += 1
    return {k: c[k] for k in ("every field right", "1 wrong", "2 wrong", "3 or more wrong", "reply cap", "loop abort")}
def kind(r): return ("copying" if r["copy_share"] >= COPY else "other") + (", cap" if r["finish_class"] == "cap" else ", loop abort")
KINDS = ("copying, cap", "copying, loop abort", "other, cap", "other, loop abort")
def join127(a):
    rs = rows(a, "128k", "join"); run = [r for r in rs if r["run"]]
    return {"requests": len(rs), "unfinished": sum(not r["done"] for r in rs),
            "with_copy_run": len(run), "copy_run_finished": sum(r["done"] for r in run),
            "copy_run_unfinished": sum(not r["done"] for r in run),
            "unfinished_without_copy_run": sum(not r["done"] and not r["run"] for r in rs),
            "copy_run_unfinished_all_8_docks_before": sum(not r["done"] and r["answers_before"] == 8 for r in run),
            "copy_run_unfinished_7_docks_before": sum(not r["done"] and r["answers_before"] == 7 for r in run),
            "copy_run_finished_score": round(st.fmean(r["correct"] / r["fields"] for r in run if r["done"]), 4) if any(r["done"] for r in run) else None,
            "no_copy_run_finished_score": round(st.fmean(r["correct"] / r["fields"] for r in rs if r["done"] and not r["run"]), 4),
            "items_with_unfinished": len({r["item"] for r in rs if not r["done"]})}
def score127(a):
    rs = rows(a, "128k")
    return {"score": round(st.fmean(value(r) for r in rs), 4),
            "by_family": {f: {"score": round(st.fmean(value(r) for r in rs if r["family"] == f), 4),
                              "unfinished": sum(not r["done"] for r in rs if r["family"] == f),
                              "finished_only": round(st.fmean(value(r) for r in rs if r["family"] == f and r["done"]), 4),
                              "requests": sum(r["family"] == f for r in rs)} for f in FAMS},
            "finished_only": round(st.fmean(value(r) for r in rs if r["done"]), 4)}
def q(v, p): v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))]
def tokens(a, L):
    t = [r["tok"] for r in rows(a, L) if r["done"]]
    return {"n": len(t), "median": int(st.median(t)), "p90": q(t, 0.90), "p99": q(t, 0.99), "max": max(t), "over_half_cap": sum(x > 16384 for x in t)}
def copy_runs(a):
    return {f: {L: {"requests": len(rs := rows(a, L, f)), "with_copy_run": sum(r["run"] for r in rs),
                    "of_which_unfinished": sum(r["run"] and not r["done"] for r in rs)} for L in LS} for f in FAMS}

# --- the four earlier arms: the same figures as published, or stop ---------------------------------------------------
FP = json.loads((HERE / "FOURPASS.json").read_text()); EN = json.loads((HERE / "ENDINGS.json").read_text())
by = {a: {L or "all": length_row(a, L) for L in LS + (None,)} for a in ARMS}
byf = {a: {f: {L: family_row(a, f, L) for L in LS} for f in FAMS} for a in ARMS}
for a in OLD:
    assert by[a] == FP["by_length"][a]["p1234"], f"{a}: by length differs from FOURPASS.json"
    assert all(byf[a][f][L] == FP["by_family"][a][f][L]["p1234"] for f in FAMS for L in LS), f"{a}: by family differs from FOURPASS.json"
    assert {**{L: ended(rows(a, L)) for L in LS}, "all": ended(rows(a))} == EN["how_each_request_ended"][a]["p1234"], f"{a}: endings differ"
    assert join127(a) == EN["join_127k"][a]["p1234"] and score127(a) == EN["score_127k"][a]["p1234"], f"{a}: join or 127K score differs"
    assert {L: tokens(a, L) for L in LS} == EN["finished_reply_tokens"][a] and copy_runs(a) == EN["copy_runs_all_requests"][a], f"{a}: tokens or copy runs differ"
assert diff("anchor", "exlr8-k4") == FP["paired"]["exlr8-k4 - anchor"]["p1234"]["score"]["all"]

# --- checks on the new arm's passes ------------------------------------------------------------------------------------
new = [r for r in ROWS if r["arm"] == NEW]
same = lambda col: sum(F[NEW][ps][k][col] == F["anchor"][ps][k][col] for ps in ALLP for k in keys)
out = {"source": list(SAMPLES) + list(ENDINGS), "arm": NEW, "sign": "b - a", "passes": list(ALLP),
       "note": "amendment 2: four passes, a total fixed before the first request; k325-fp8 differs from every other arm in the whole "
               "checkpoint; its passes ran alone after the others' (not interleaved)",
       "four_earlier_arms": "their four-pass figures are recomputed here by the same rule and checked equal to FOURPASS.json and ENDINGS.json",
       "requests": {ps: len(F[NEW][ps]) for ps in ALLP}, "errors": sum(r["status"] != "ok" for r in new),
       "checks": {"requests": len(new), "prompt_tokens_equal_to_anchor": same("prompt_tokens"), "seed_equal_to_anchor": same("seed"),
                  "cached_tokens_nonzero": sum(int(r["cached_tokens"] or 0) > 0 for r in new)}}

# --- score ---------------------------------------------------------------------------------------------------------------
SCOPES = {**{L: (L,) for L in LS}, "all": None, "4k+16k": ("4k", "16k"), "64k+128k": ("64k", "128k")}
out["by_length"] = by
out["score_by_pass"] = {L or "all": [round(st.fmean(value(r) for r in rows(NEW, L, None, (ps,))), 4) for ps in ALLP] for L in LS + (None,)}
out["by_family"] = byf
pd = {}
for a in OLD:
    pd[f"{NEW} - {a}"] = {
        "score": {k: diff(a, NEW, v) for k, v in SCOPES.items()},
        "every_field_right": {k: diff(a, NEW, SCOPES[k], None, lambda r: float(right(r))) for k in LS + ("all", "64k+128k")},
        "by_family_all_lengths": {f: diff(a, NEW, None, f) for f in FAMS},
        "by_family_127k": {f: diff(a, NEW, ("128k",), f) for f in FAMS}}
out["paired"] = pd
def excl(m): return m[1] > 0 or m[2] < 0
def walk(d, path=()):
    for k, v in d.items():
        if isinstance(v, dict): yield from walk(v, path + (k,))
        else: yield path + (k,), v
listed = [(p, m) for p, m in walk(pd)]
out["intervals"] = {"listed": len(listed), "excluding_zero": [{"pair": p[0], "measure": p[1], "scope": p[2], "value": m} for p, m in listed if excl(m)],
                    "selected": "none", "note": "four pairs x (score in seven scopes, every field right in six, score by family over all lengths "
                                                "and at 127K); no correction for the number of intervals"}
out["agreement"] = {"all_five_arms_right": sum(all(right(F[a][ps][k]) for a in ARMS) for ps in ALLP for k in keys),
                    "no_arm_right": sum(not any(right(F[a][ps][k]) for a in ARMS) for ps in ALLP for k in keys), "of": 4 * len(keys)}
out["times_right_of_4_per_item_length"] = dict(sorted(Counter(sum(right(F[NEW][ps][k]) for ps in ALLP) for k in keys).items()))

# --- how the replies ended -----------------------------------------------------------------------------------------------
un = [r for r in new if not r["done"]]; un5 = [r for r in ROWS if not r["done"]]
out["how_each_request_ended"] = {a: {**{L: ended(rows(a, L)) for L in LS}, "all": ended(rows(a))} for a in ARMS}
out["unfinished"] = {
    "total": len(un), "with_answer_text": sum(r["content_chars"] > 0 for r in un),
    "by_family_length": {a: {f: {L: sum(r["arm"] == a and r["family"] == f and r["length"] == L for r in un5) for L in LS} for f in FAMS} for a in ARMS},
    "by_family_kind": {f: {k: sum(r["family"] == f and kind(r) == k for r in un) for k in KINDS} for f in FAMS},
    "by_kind": {k: sum(kind(r) == k for r in un) for k in KINDS},
    "by_pass": [sum(r["pass"] == ps for r in un) for ps in ALLP],
    "distinct_items": len({r["item"] for r in un}),
    "items_also_unfinished_in_an_earlier_arm": sorted({r["item"] for r in un} & {r["item"] for r in un5 if r["arm"] != NEW}),
    "all_five_arms_total": len(un5),
    "list": [{"arm": NEW, "pass": int(r["pass"][-1]) + 1, "item": r["item"], "length": r["length"], "finish": r["finish_class"],
              "tokens": r["tok"], "reasoning_chars": r["chars"], "copy_share": round(r["copy_share"], 3),
              "repeat_share": round(r["repeat_share"], 3), "run_start_chars": r["run_start"], "reached": r["reached"],
              "records": r["records"], "answers_before": r["answers_before"], "kind": kind(r)}
             for r in sorted(un, key=lambda r: (r["pass"], r["item"], LS.index(r["length"])))]}
out["join_127k"] = {a: join127(a) for a in ARMS}
out["join_127k_unfinished_by_pass"] = [sum(not r["done"] for r in rows(NEW, "128k", "join", (p,))) for p in ALLP]
out["join_127k_items_with_unfinished_any_arm"] = len({r["item"] for r in un5 if r["length"] == "128k" and r["family"] == "join"})
out["copy_runs_all_requests"] = copy_runs(NEW)
nd = lambda r: float(not r["done"])
out["paired_unfinished_share"] = {f"{NEW} - {a}": {"unfinished_all": diff(a, NEW, None, None, nd), "unfinished_127k": diff(a, NEW, ("128k",), None, nd),
                                                   "unfinished_127k_join": diff(a, NEW, ("128k",), "join", nd),
                                                   "unfinished_127k_ledger": diff(a, NEW, ("128k",), "ledger", nd),
                                                   "unfinished_64k_ledger": diff(a, NEW, ("64k",), "ledger", nd)} for a in OLD}
out["score_127k"] = {a: score127(a) for a in ARMS}
fm = lambda a, f=None: st.fmean(value(r) for r in rows(a, "128k", f))
out["gap_127k_by_family"] = {f"{NEW} - {a}": {"all": round(fm(NEW) - fm(a), 4), **{f: round((fm(NEW, f) - fm(a, f)) / 3, 4) for f in FAMS}} for a in OLD}
out["finished_reply_tokens"] = {a: {L: tokens(a, L) for L in LS} for a in ARMS}
(HERE / "AMEND2.json").write_text(json.dumps(out, indent=1) + "\n")

f3 = lambda m: f"{m[0]:+.3f} [{m[1]:+.3f},{m[2]:+.3f}]" + ("*" if excl(m) else " ")
m3 = lambda m: f"{m[0]:.3f} [{m[1]:.3f},{m[2]:.3f}]"
print("requests", out["requests"], "errors", out["errors"], "checks", out["checks"])
print("\nARM SCORE, four passes (item mean, interval) | right | unfinished | finished only")
for a in ARMS: print(f" {a:9s}", "  ".join(f"{L}: {m3(by[a][L]['score'])}" for L in LS + ("all",)), "|", [by[a][L]["right"] for L in LS + ("all",)],
                     "|", [by[a][L]["unfinished"] for L in LS + ("all",)], "|", [by[a][L]["score_finished_only"] for L in LS + ("all",)])
print(f" {NEW} by pass:", out["score_by_pass"])
print("\nPAIRED b - a  (* = interval excludes 0)")
for k, e in pd.items():
    print(f" {k}")
    print("   score ", "  ".join(f"{sc}: {f3(e['score'][sc])}" for sc in SCOPES))
    print("   strict", "  ".join(f"{sc}: {f3(v)}" for sc, v in e["every_field_right"].items()))
    print("   family all:", "  ".join(f"{f}: {f3(v)}" for f, v in e["by_family_all_lengths"].items()), " 127K:", "  ".join(f"{f}: {f3(v)}" for f, v in e["by_family_127k"].items()))
print("\nintervals", out["intervals"]["listed"], "excluding zero", len(out["intervals"]["excluding_zero"]))
print("agreement", out["agreement"], "times right of 4", out["times_right_of_4_per_item_length"])
print("\nBY FAMILY right/n [unfinished] score")
for a in ARMS:
    for f in FAMS: print(f" {a:9s}{f:7s}", "  ".join(f"{L}: {byf[a][f][L]['right']}/{byf[a][f][L]['n']}[{byf[a][f][L]['unfinished']}] {byf[a][f][L]['score']:.3f}" for L in LS))
print("\nENDED all / 127K")
for a in ARMS: print(f" {a:9s}", list(out["how_each_request_ended"][a]["all"].values()), list(out["how_each_request_ended"][a]["128k"].values()))
u = out["unfinished"]
print("unfinished", u["total"], "with answer text", u["with_answer_text"], "kinds", u["by_kind"], "by pass", u["by_pass"], "items", u["distinct_items"], "shared", u["items_also_unfinished_in_an_earlier_arm"], "five-arm total", u["all_five_arms_total"])
print(" by family/length", u["by_family_length"][NEW]); print(" by family/kind", u["by_family_kind"])
print("join 127K"); [print(f"  {a:9s}", out["join_127k"][a]) for a in ARMS]
print(" by pass", out["join_127k_unfinished_by_pass"], "items any arm", out["join_127k_items_with_unfinished_any_arm"])
print("paired unfinished share"); [print(f"  {k}", {m: f3(x) for m, x in v.items()}) for k, v in out["paired_unfinished_share"].items()]
print("score 127K"); [print(f"  {a:9s}", out["score_127k"][a]) for a in ARMS]
print("gap 127K by family", out["gap_127k_by_family"])
print("copy runs", {f: [(d["with_copy_run"], d["of_which_unfinished"]) for d in out["copy_runs_all_requests"][f].values()] for f in FAMS})
print("finished tokens"); [print(f"  {a:9s}", out["finished_reply_tokens"][a]["128k"]) for a in ARMS]
print("descriptive: median completion tokens, reasoning chars, decode tok/s, ttft s")
for a in ARMS: print(f"  {a:9s}", " | ".join(f"{L} {by[a][L]['completion_tokens_median']:.0f} {by[a][L]['reasoning_chars_median']:.0f} {by[a][L]['decode_tok_s_median']:.1f} {by[a][L]['ttft_s_median']:.1f}" for L in LS))
