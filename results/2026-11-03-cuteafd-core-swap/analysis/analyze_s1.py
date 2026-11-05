#!/usr/bin/env python3
"""Core-swap step 1 reading (PROTOCOL.md, frozen). Standard library only.
    analyze_s1.py --l <run>/l --out S1-RESULT.json
Reads the analyzer's per-request records (<arm>-o20-L3.inner.json, <arm>-o30-L3.inner.json; reasoning tokens by
re-tokenization) for arms C-K6, C-K6x, C-K4. Pairs requests across arms by (content, prompt, rep), which share a seed.
Per contrast (core = C-K6 vs C-K6x, experts = C-K6x vs C-K4, total = C-K6 vs C-K4): mean of log(reasoning tokens a /
reasoning tokens b) over pairs where both finished (finish stop, under the cap); 95% bootstrap (4,000 replicates, seed
20261103) over prompts (content x prompt: 8 units; primary) and over pairs (secondary); ratio = exp(mean). Detected when
the prompt-level interval excludes 1. Per arm: finished and capped counts, capped replies that loop, finished replies with a terminal repetition onset
(descriptive), median reasoning tokens by content.
"""
import argparse, glob, json, math, os, random, statistics as st

ARMS = ("C-K6", "C-K6x", "C-K4")
CONTRASTS = {"core": ("C-K6", "C-K6x"), "experts": ("C-K6x", "C-K4"), "total": ("C-K6", "C-K4")}
NB, SEED = 4000, 20261103


def load(ldir, arm):
    rows = {}
    for f in sorted(glob.glob(os.path.join(ldir, f"{arm}-o*-L3.inner.json"))):
        for r in json.load(open(f))["results"]:
            rows[(r["content"], r["prompt_index"], r["rep"])] = r
    return rows


def ok(r):
    return r and r.get("finish_reason") == "stop" and not r.get("hit_cap") and r.get("reasoning_tokens")


def boot(units, rng):
    keys = sorted(units); out = []
    for _ in range(NB):
        v = [x for k in (rng.choice(keys) for _ in keys) for x in units[k]]
        out.append(st.mean(v))
    out.sort(); return out[int(.025 * NB)], out[int(.975 * NB) - 1]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--l", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    R = {arm: load(a.l, arm) for arm in ARMS}
    out = {"per_arm": {}, "contrasts": {}}
    for arm, rows in R.items():
        out["per_arm"][arm] = {
            "requests": len(rows), "finished": sum(bool(ok(r)) for r in rows.values()),
            "capped": sum(bool(r.get("hit_cap")) for r in rows.values()),
            # a loop = a capped reply with a terminal repetition onset; finished code replies also show an onset (the
            # answer repeats code from the reasoning), so the onset alone is reported separately, not as a loop
            "capped_looping": sum(bool(r.get("hit_cap")) and (r.get("loop") or {}).get("onset") is not None for r in rows.values()),
            "finished_with_terminal_repetition": sum(bool(ok(r)) and (r.get("loop") or {}).get("onset") is not None for r in rows.values()),
            "median_reasoning_tokens": {c: st.median([r["reasoning_tokens"] for k, r in rows.items() if k[0] == c and ok(r)] or [0])
                                        for c in ("code", "prose")}}
    for name, (x, y) in CONTRASTS.items():
        pairs = {k: math.log(R[x][k]["reasoning_tokens"] / R[y][k]["reasoning_tokens"])
                 for k in R[x] if ok(R[x].get(k)) and ok(R[y].get(k))}
        if not pairs:
            out["contrasts"][name] = {"pairs": 0}; continue
        units = {}
        for (c, p, rep), v in pairs.items():
            units.setdefault((c, p), []).append(v)
        m = st.mean(pairs.values())
        lo, hi = boot(units, random.Random(SEED)); plo, phi = boot({k: [v] for k, v in pairs.items()}, random.Random(SEED))
        by_c = {c: math.exp(st.mean([v for (cc, _, _), v in pairs.items() if cc == c])) for c in ("code", "prose")
                if any(cc == c for (cc, _, _) in pairs)}
        out["contrasts"][name] = {"a": x, "b": y, "pairs": len(pairs), "prompts": len(units), "ratio": math.exp(m),
                                  "ratio_ci95_prompts": [math.exp(lo), math.exp(hi)], "ratio_ci95_pairs": [math.exp(plo), math.exp(phi)],
                                  "detected": lo > 0 or hi < 0, "ratio_by_content": by_c,
                                  "per_prompt": {f"{c}-p{p}": math.exp(st.mean(v)) for (c, p), v in sorted(units.items())}}
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
