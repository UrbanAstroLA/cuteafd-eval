#!/usr/bin/env python3
"""Code-thinking reading (PROTOCOL.md). Standard library only.   analyze_ct.py --l <run>/l --out CT-RESULT.json
Reads the analyzer's per-request records (<arm>-L3.inner.json; reasoning tokens by re-tokenization; code checks) for
C-K6 and C-K6x. Pairs by (prompt, rep), which share a seed. Contrast core = C-K6 / C-K6x: mean of log(reasoning tokens)
ratios over pairs where both finished (stop, under the cap); ratio = exp(mean); 95% bootstrap (4,000 replicates, seed
20261105) over prompts (primary) and over pairs; the core-swap step 1 estimator. Sets: primary = p4-p15 (new prompts),
secondary = all 16 and p0-p3 (the Block L projects). Detected when the prompt-level interval of the primary set excludes
1. Direction: prompts whose mean log ratio is above 0, with a two-sided sign-test p (descriptive). Per arm: finished,
capped, capped with a terminal repetition onset, all-tests-pass share of finished replies, median reasoning tokens,
median decode tok/s."""
import argparse, json, math, os, random, statistics as st

ARMS = ("C-K6", "C-K6x"); NB, SEED = 4000, 20261105
SETS = {"primary_p4_p15": range(4, 16), "all_p0_p15": range(16), "blockL_p0_p3": range(4)}


def load(ldir, arm):
    return {(r["prompt_index"], r["rep"]): r for r in json.load(open(os.path.join(ldir, f"{arm}-L3.inner.json")))["results"]}


def ok(r):
    return r and r.get("finish_reason") == "stop" and not r.get("hit_cap") and r.get("reasoning_tokens")


def boot(units, rng):
    keys = sorted(units); out = []
    for _ in range(NB):
        out.append(st.mean([x for k in (rng.choice(keys) for _ in keys) for x in units[k]]))
    out.sort(); return out[int(.025 * NB)], out[int(.975 * NB) - 1]


def sign_p(k, n):
    """two-sided exact binomial p for k of n above 0 under p = 0.5"""
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--l", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    R = {arm: load(a.l, arm) for arm in ARMS}
    out = {"per_arm": {}, "core": {}}
    for arm, rows in R.items():
        fin = [r for r in rows.values() if ok(r)]
        out["per_arm"][arm] = {
            "requests": len(rows), "finished": len(fin), "capped": sum(bool(r.get("hit_cap")) for r in rows.values()),
            "capped_looping": sum(bool(r.get("hit_cap")) and (r.get("loop") or {}).get("onset") is not None for r in rows.values()),
            "all_tests_pass_of_finished": sum(bool((r.get("check") or {}).get("all_pass")) for r in fin),
            "median_reasoning_tokens": st.median([r["reasoning_tokens"] for r in fin] or [0]),
            "median_decode_tok_s": st.median([r["decode_tok_s"] for r in fin if r.get("decode_tok_s")] or [0])}
    pairs = {k: math.log(R["C-K6"][k]["reasoning_tokens"] / R["C-K6x"][k]["reasoning_tokens"])
             for k in R["C-K6"] if ok(R["C-K6"].get(k)) and ok(R["C-K6x"].get(k))}
    for name, rng_ in SETS.items():
        units = {}
        for (p, rep), v in pairs.items():
            if p in rng_:
                units.setdefault(p, []).append(v)
        vals = [x for v in units.values() for x in v]
        if not vals:
            out["core"][name] = {"pairs": 0}; continue
        lo, hi = boot(units, random.Random(SEED))
        plo, phi = boot({i: [v] for i, v in enumerate(vals)}, random.Random(SEED))
        above = sum(st.mean(v) > 0 for v in units.values())
        out["core"][name] = {"pairs": len(vals), "prompts": len(units), "ratio": math.exp(st.mean(vals)),
                             "ratio_ci95_prompts": [math.exp(lo), math.exp(hi)], "ratio_ci95_pairs": [math.exp(plo), math.exp(phi)],
                             "detected": lo > 0 or hi < 0, "prompts_above_1": above, "sign_test_p": sign_p(above, len(units)),
                             "per_prompt": {f"p{p}": math.exp(st.mean(v)) for p, v in sorted(units.items())},
                             "pairs_per_prompt": {f"p{p}": len(v) for p, v in sorted(units.items())}}
    out["unpaired"] = [{"prompt": p, "rep": r, **{arm: (R[arm].get((p, r)) or {}).get("finish_reason") for arm in ARMS}}
                       for (p, r) in sorted(set(R["C-K6"]) | set(R["C-K6x"])) if (p, r) not in pairs]
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
