#!/usr/bin/env python3
"""Post hoc, not in any frozen rule: paired comparison of hidden-test outcomes between the code-thinking arms of both
engines (code study C-*, vLLM code study V-*, FP8 ablation F-*), from the published per-reply samples.csv files.

Pairs: same prompt and seed, both replies finished (finish_reason stop, not capped). Per pair: all-pass difference
(1/0/-1) and difference in share of tests passed. Mean over pairs; 95% bootstrap over the 16 prompts (4,000, seed
20261108), the resampling of analyze_fa.py; Bonferroni intervals over all listed contrasts from 20,000 draws (same seed).
Every contrast examined is listed, so the number of looks is visible.

usage: python3 pass_pairs.py [repo root] > PASS-PAIRS.json
"""
import csv, json, random, statistics as st, sys
from pathlib import Path

NB, SEED = 4000, 20261108
SOURCES = ["results/2026-11-05-code-thinking/analysis/samples.csv", "results/2026-11-06-vllm-code-thinking/analysis/samples.csv",
           "results/2026-11-06-cuteafd-fp8-ablation/analysis/samples.csv"]
# Every contrast looked at for this note or published elsewhere in the run (SUMMARY.json post_hoc_all_tests_pass_pairs):
# all four code-study/vLLM arms pairwise, each F arm against both C arms, and V-K6 against F-kda.
CONTRASTS = [("V-K6", "C-K6"), ("V-K6", "C-K6x"), ("V-BF16", "C-K6"), ("V-BF16", "C-K6x"), ("V-BF16", "V-K6"), ("C-K6", "C-K6x"),
             ("F-kda", "C-K6x"), ("F-kda", "C-K6"), ("F-head", "C-K6x"), ("F-head", "C-K6"), ("F-pre", "C-K6x"), ("F-pre", "C-K6"),
             ("V-K6", "F-kda")]
NB_ADJ = 20000  # draws for the Bonferroni intervals (two-sided 0.05 / number of contrasts)


def load(root):
    arms = {}
    for s in SOURCES:
        for r in csv.DictReader(open(root / s)):
            if r["finish_reason"] != "stop" or r["hit_cap"] in ("1", "True", "true"):
                continue
            t = float(r["tests"] or 0)
            arms.setdefault(r["arm"], {})[(int(r["prompt"]), int(r["rep"]))] = (
                r["all_tests_pass"] in ("1", "True", "true"), float(r["tests_passed"] or 0) / t if t else 0.0)
    return arms


def ci(vals):
    v = sorted(vals); return v[int(.025 * NB)], v[int(.975 * NB) - 1]


def contrast(A, B, m):
    keys = sorted(set(A) & set(B))
    u = {}
    for k in keys:
        u.setdefault(k[0], []).append((int(A[k][0]) - int(B[k][0]), A[k][1] - B[k][1]))
    prompts = sorted(u); rng = random.Random(SEED)
    samples = [[rng.choice(prompts) for _ in prompts] for _ in range(NB)]
    out = {"pairs": len(keys), "prompts": len(prompts),
           "all_pass": [sum(A[k][0] for k in keys), sum(B[k][0] for k in keys)],
           "only_first_passes": sum(A[k][0] and not B[k][0] for k in keys),
           "only_second_passes": sum(B[k][0] and not A[k][0] for k in keys)}
    for i, name in ((0, "all_pass_difference"), (1, "share_passed_difference")):
        mu = st.mean(x[i] for v in u.values() for x in v)
        lo, hi = ci([st.mean(x[i] for p in s for x in u[p]) for s in samples])
        out[name] = {"mean": mu, "ci95_prompts": [lo, hi], "excludes_0": lo > 0 or hi < 0}
    rng = random.Random(SEED); a = .05 / m / 2
    v = sorted(st.mean(x[0] for p in [rng.choice(prompts) for _ in prompts] for x in u[p]) for _ in range(NB_ADJ))
    lo, hi = v[int(a * NB_ADJ)], v[int((1 - a) * NB_ADJ) - 1]
    out["all_pass_difference"]["bonferroni_ci"] = {"looks": m, "interval": [lo, hi], "excludes_0": lo > 0 or hi < 0}
    return out


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    arms = load(root)
    res = {f"{a} vs {b}": contrast(arms[a], arms[b], len(CONTRASTS)) for a, b in CONTRASTS}
    print(json.dumps({"about": __doc__.strip().split("\n\n")[0], "sources": SOURCES, "bootstrap": {"draws": NB, "seed": SEED},
                      "contrasts_examined": len(res), "contrasts": res}, indent=1))


if __name__ == "__main__":
    main()
