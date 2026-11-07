#!/usr/bin/env python3
"""vLLM code-thinking reading (PROTOCOL.md). Standard library only.
    analyze_vct.py --l <run>/l --cuteafd <ct-run>/l --out VCT-RESULT.json
The CuteAFD study's estimator (analyze_ct.py) on V-K6 / V-BF16: pairs by (prompt, rep), which share a seed; mean of
log(reasoning tokens) ratios over pairs where both finished; ratio = exp(mean); 95% bootstrap (4,000, seed 20261106)
over prompts (primary) and pairs. Sets: primary p4-p15, secondary all 16 and p0-p3. Reasoning tokens and code checks
from L-analysis.json (the analyzer writes the checks only there).
Engine comparison (paired by prompt): log ratio vLLM minus log ratio CuteAFD (C-K6 / C-K6x), bootstrap over prompts."""
import argparse, json, math, os, random, statistics as st

ARMS = ("V-K6", "V-BF16"); CARMS = ("C-K6", "C-K6x"); NB, SEED = 4000, 20261106
SETS = {"primary_p4_p15": range(4, 16), "all_p0_p15": range(16), "blockL_p0_p3": range(4)}


def load(ldir, arms):
    res = json.load(open(os.path.join(ldir, "L-analysis.json")))["results"]
    return {a: {(r["prompt_index"], r["rep"]): r for r in res if r["label"] == a} for a in arms}


def ok(r):
    return r and r.get("finish_reason") == "stop" and not r.get("hit_cap") and r.get("reasoning_tokens")


def boot(units, rng):
    keys = sorted(units); out = []
    for _ in range(NB):
        out.append(st.mean([x for k in (rng.choice(keys) for _ in keys) for x in units[k]]))
    out.sort(); return out[int(.025 * NB)], out[int(.975 * NB) - 1]


def sign_p(k, n):
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pair_logs(R, hi, lo):
    return {k: math.log(R[hi][k]["reasoning_tokens"] / R[lo][k]["reasoning_tokens"])
            for k in R[hi] if ok(R[hi].get(k)) and ok(R[lo].get(k))}


def reading(pairs, rng_):
    units = {}
    for (p, rep), v in pairs.items():
        if p in rng_:
            units.setdefault(p, []).append(v)
    vals = [x for v in units.values() for x in v]
    if not vals:
        return {"pairs": 0}, units
    lo, hi = boot(units, random.Random(SEED)); plo, phi = boot({i: [v] for i, v in enumerate(vals)}, random.Random(SEED))
    above = sum(st.mean(v) > 0 for v in units.values())
    return {"pairs": len(vals), "prompts": len(units), "ratio": math.exp(st.mean(vals)),
            "ratio_ci95_prompts": [math.exp(lo), math.exp(hi)], "ratio_ci95_pairs": [math.exp(plo), math.exp(phi)],
            "detected": lo > 0 or hi < 0, "prompts_above_1": above, "sign_test_p": sign_p(above, len(units)),
            "pairs_above_1": sum(v > 0 for v in vals),
            "per_prompt": {f"p{p}": math.exp(st.mean(v)) for p, v in sorted(units.items())}}, units


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--l", required=True); ap.add_argument("--cuteafd", required=True)
    ap.add_argument("--out", required=True); a = ap.parse_args()
    R = load(a.l, ARMS); C = load(a.cuteafd, CARMS)
    out = {"per_arm": {}, "core": {}, "engine_comparison": {}}
    for arm, rows in R.items():
        fin = [r for r in rows.values() if ok(r)]
        out["per_arm"][arm] = {
            "requests": len(rows), "finished": len(fin), "capped": sum(bool(r.get("hit_cap")) for r in rows.values()),
            "capped_looping": sum(bool(r.get("hit_cap")) and (r.get("loop") or {}).get("onset") is not None for r in rows.values()),
            "finished_with_terminal_repeat": sum((r.get("loop") or {}).get("onset") is not None for r in fin),
            "all_tests_pass_of_finished": sum(bool((r.get("check") or {}).get("all_pass")) for r in fin),
            "mean_share_tests_passed": st.mean([((r.get("check") or {}).get("passed") or 0) / ((r.get("check") or {}).get("tests") or 1) for r in rows.values()] or [0]),
            "median_reasoning_tokens": st.median([r["reasoning_tokens"] for r in fin] or [0]),
            "median_decode_tok_s": st.median([r["decode_tok_s"] for r in fin if r.get("decode_tok_s")] or [0])}
    vp, cp = pair_logs(R, "V-K6", "V-BF16"), pair_logs(C, "C-K6", "C-K6x")
    for name, rng_ in SETS.items():
        out["core"][name], vu = reading(vp, rng_)
        _, cu = reading(cp, rng_)
        common = sorted(set(vu) & set(cu))
        if common:
            d = {p: [st.mean(vu[p]) - st.mean(cu[p])] for p in common}
            lo, hi = boot(d, random.Random(SEED))
            out["engine_comparison"][name] = {"prompts": len(common), "vllm_over_cuteafd_ratio": math.exp(st.mean(x[0] for x in d.values())),
                                              "ci95_prompts": [math.exp(lo), math.exp(hi)],
                                              "per_prompt_corr": (st.correlation([st.mean(vu[p]) for p in common], [st.mean(cu[p]) for p in common])
                                                                  if len(common) > 2 else None)}
    out["unpaired"] = [{"prompt": p, "rep": r, **{arm: (R[arm].get((p, r)) or {}).get("finish_reason") for arm in ARMS}}
                       for (p, r) in sorted(set(R["V-K6"]) | set(R["V-BF16"])) if (p, r) not in vp]
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
