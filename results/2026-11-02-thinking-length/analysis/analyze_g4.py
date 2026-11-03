#!/usr/bin/env python3
"""G4 (reduced) analysis, frozen in G4-PROTOCOL.md. Standard library only.

    python3 analyze_g4.py --g4 <run>/g4 --out <file.json> [--g1b <run>/g1b]

Arms g4/k6 and g4/all, question 12, samples doc12_rep<r>.json from gen_traces.py.
Primary: delta = mean(log completion tokens | all) - mean(log completion tokens | k6) over samples with a usage record,
95% bootstrap interval (2,000 replicates, samples resampled within each arm, seed 20261103); ratio = exp(delta).
A shift is detected when the interval excludes 0; "no shift of 1.25x or more" when the interval lies inside +-log(1.25).
Secondary, descriptive: seed-paired delta (same seed in both arms), class counts (ok / loop / exhaust / cut / error),
answer letter vs the gold (D) (reported, not used), G1b question-12 samples (k6, other seeds) for context.
"""
import argparse, glob, json, math, os, random, re

GOLD = "D"
NB, SEED = 2000, 20261103


def load(d):
    out = {}
    for f in glob.glob(os.path.join(d, "doc12_rep*.json")):
        r = json.load(open(f))
        out[r["rep"]] = r
    return out


def letter(content):
    m = re.findall(r"\(([A-D])\)|boxed\{[^}]*?\b([A-D])\b", content or "")
    return (m[-1][0] or m[-1][1]) if m else None


def logtok(rs):
    return [math.log(r["usage"]["completion_tokens"]) for r in rs if r.get("usage")]


def mean(x):
    return sum(x) / len(x)


def boot_diff(x, y):
    rng = random.Random(SEED)
    b = sorted(mean([rng.choice(y) for _ in y]) - mean([rng.choice(x) for _ in x]) for _ in range(NB))
    return mean(y) - mean(x), [b[int(.025 * NB)], b[int(.975 * NB) - 1]]


def summary(rs):
    cls = {}
    for r in rs:
        cls[r["cls"]] = cls.get(r["cls"], 0) + 1
    toks = sorted(r["usage"]["completion_tokens"] for r in rs if r.get("usage"))
    lt = logtok(rs)
    sd = (sum((v - mean(lt)) ** 2 for v in lt) / (len(lt) - 1)) ** .5 if len(lt) > 1 else None
    ans = [letter(r.get("content")) for r in rs]
    return {"n": len(rs), "classes": cls, "tokens_sorted": toks, "median_tokens": toks[len(toks) // 2] if toks else None,
            "geo_mean_tokens": round(math.exp(mean(lt))) if lt else None, "sd_log_tokens": sd,
            "correct": sum(a == GOLD for a in ans), "no_letter": sum(a is None for a in ans)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--g4", required=True); ap.add_argument("--out", required=True); ap.add_argument("--g1b")
    a = ap.parse_args()
    A = {arm: load(os.path.join(a.g4, arm)) for arm in ("k6", "all")}
    out = {"per_arm": {arm: summary(list(v.values())) for arm, v in A.items()}}
    x, y = logtok(A["k6"].values()), logtok(A["all"].values())
    if len(x) > 1 and len(y) > 1:
        d, ci = boot_diff(x, y)
        lim = math.log(1.25)
        out["primary"] = {"delta_log": d, "ci95": ci, "ratio": math.exp(d), "ratio_ci95": [math.exp(c) for c in ci],
                          "shift_detected": ci[0] > 0 or ci[1] < 0, "no_shift_ge_1_25x": -lim < ci[0] and ci[1] < lim}
    reps = sorted(set(A["k6"]) & set(A["all"]))
    pd = [math.log(A["all"][r]["usage"]["completion_tokens"]) - math.log(A["k6"][r]["usage"]["completion_tokens"])
          for r in reps if A["all"][r].get("usage") and A["k6"][r].get("usage")]
    out["seed_paired"] = {"pairs": len(pd), "mean_delta_log": mean(pd) if pd else None}
    if a.g1b:
        out["g1b_q12_k6_context"] = summary(list(load(a.g1b).values()))
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
