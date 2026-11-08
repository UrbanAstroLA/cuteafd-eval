#!/usr/bin/env python3
"""FP8 ablation reading (PROTOCOL.md). Standard library only.
    analyze_fa.py --l <run>/l --ct <ct-run>/l --out FA-RESULT.json
Same engine, same seeds as the code study, so arms pair by (prompt, rep). Estimator as the code study: mean of
log(reasoning tokens) ratios over pairs where both finished; ratio = exp(mean); 95% bootstrap (4,000, seed 20261106)
over prompts. Primary set p4-p15; secondary all 16. Arms: C-K6x, C-K6 (code study), F-kda, F-head, F-pre (this run).
Gap share of arm X = log(X / C-K6x) / log(C-K6 / C-K6x), bootstrapped over prompts with the same resamples."""
import argparse, gzip, json, math, os, random, statistics as st

NB, SEED = 4000, 20261106
SETS = {"primary_p4_p15": range(4, 16), "all_p0_p15": range(16)}
F = ("F-kda", "F-head", "F-pre")
CONTRASTS = [("F-kda", "C-K6x", "step: KDA projections BF16"), ("F-head", "F-kda", "step: head BF16"),
             ("F-pre", "F-head", "step: prefill activations unquantized"), ("C-K6", "F-pre", "remaining gap to the native 6-bit core"),
             ("F-kda", "C-K6"), ("F-head", "C-K6"), ("F-pre", "C-K6x"), ("C-K6", "C-K6x", "reference: the code study's gap")]


def load(ldir, arms):
    res = json.load(open(os.path.join(ldir, "L-analysis.json")))["results"]
    return {a: {(r["prompt_index"], r["rep"]): r for r in res if r["label"] == a} for a in arms}


def ok(r):
    return r and r.get("finish_reason") == "stop" and not r.get("hit_cap") and r.get("reasoning_tokens")


def units(A, B, prompts):
    u = {}
    for k, r in A.items():
        if k[0] in prompts and ok(r) and ok(B.get(k)):
            u.setdefault(k[0], []).append(math.log(r["reasoning_tokens"] / B[k]["reasoning_tokens"]))
    return u


def resamples(keys):
    rng = random.Random(SEED)
    return [[rng.choice(keys) for _ in keys] for _ in range(NB)]


def mean_over(u, sample):
    return st.mean([x for k in sample for x in u[k]])


def ci(vals):
    v = sorted(vals); return v[int(.025 * NB)], v[int(.975 * NB) - 1]


def contrast(A, B, prompts):
    u = units(A, B, prompts)
    if not u:
        return {"pairs": 0}
    keys = sorted(u); lo, hi = ci([mean_over(u, s) for s in resamples(keys)])
    vals = [x for v in u.values() for x in v]
    return {"pairs": len(vals), "prompts": len(u), "ratio": math.exp(st.mean(vals)), "ratio_ci95_prompts": [math.exp(lo), math.exp(hi)],
            "detected": lo > 0 or hi < 0, "prompts_above_1": sum(st.mean(v) > 0 for v in u.values()),
            "per_prompt": {f"p{p}": math.exp(st.mean(v)) for p, v in sorted(u.items())}}


def gap_share(arms, x, prompts):
    ux, ug = units(arms[x], arms["C-K6x"], prompts), units(arms["C-K6"], arms["C-K6x"], prompts)
    keys = sorted(set(ux) & set(ug))
    if not keys:
        return None
    sh = []
    for s in resamples(keys):
        g = mean_over(ug, s)
        sh.append(mean_over(ux, s) / g if g else float("nan"))
    g0 = st.mean([x_ for k in keys for x_ in ug[k]])
    lo, hi = ci(sh) if all(v == v for v in sh) else (None, None)   # a resample with a zero gap leaves the interval undefined
    return {"share": st.mean([x_ for k in keys for x_ in ux[k]]) / g0, "ci95_prompts": [lo, hi], "prompts": len(keys)}


def control(ldir, ctdir):
    try:
        a = json.load(gzip.open(os.path.join(ldir, "F-ctrl-L3-texts", "F-ctrl-L3-code-p3-r3.json.gz")))
        b = json.load(gzip.open(os.path.join(ctdir, "C-K6x-L3-texts", "C-K6x-L3-code-p3-r3.json.gz")))
    except OSError as e:
        return {"error": str(e)}
    return {"request": "p3 r3 (seed 2026110803)", "reasoning_identical": a["reasoning"] == b["reasoning"],
            "content_identical": a["content"] == b["content"], "reasoning_chars": [len(a["reasoning"]), len(b["reasoning"])],
            "note": "descriptive: the original ran 2 requests in flight, the replay runs alone"}


def per_arm(rows):
    fin = [r for r in rows.values() if ok(r)]
    return {"requests": len(rows), "finished": len(fin), "capped": sum(bool(r.get("hit_cap")) for r in rows.values()),
            "capped_looping": sum(bool(r.get("hit_cap")) and (r.get("loop") or {}).get("onset") is not None for r in rows.values()),
            "finished_with_terminal_repeat": sum((r.get("loop") or {}).get("onset") is not None for r in fin),
            "all_tests_pass_of_finished": sum(bool((r.get("check") or {}).get("all_pass")) for r in fin),
            "mean_share_tests_passed": st.mean([((r.get("check") or {}).get("passed") or 0) / ((r.get("check") or {}).get("tests") or 1) for r in rows.values()] or [0]),
            "median_reasoning_tokens": st.median([r["reasoning_tokens"] for r in fin] or [0]),
            "median_decode_tok_s": st.median([r["decode_tok_s"] for r in fin if r.get("decode_tok_s")] or [0])}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--l", required=True); ap.add_argument("--ct", required=True)
    ap.add_argument("--out", required=True); a = ap.parse_args()
    arms = {**load(a.ct, ("C-K6", "C-K6x")), **load(a.l, F)}
    out = {"per_arm": {k: per_arm(v) for k, v in arms.items()}, "contrasts": {}, "gap_share": {}, "control": control(a.l, a.ct)}
    for name, prompts in SETS.items():
        out["contrasts"][name] = {f"{c[0]} / {c[1]}": {"what": c[2] if len(c) > 2 else "", **contrast(arms[c[0]], arms[c[1]], prompts)}
                                  for c in CONTRASTS}
        out["gap_share"][name] = {x: gap_share(arms, x, prompts) for x in F}
    json.dump(out, open(a.out, "w"), indent=1); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
