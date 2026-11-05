#!/usr/bin/env python3
"""The observation that raised the core-swap question, recomputed from the CuteAFD v4 run's Block L stage L3 (130K cap)
records: K4-Core-K6 (K6-r1, K6-r2) against K4 (C4-r1, C4-r2), seed-paired (same content, prompt, rep and seed), reasoning
tokens by re-tokenization (the v4 run's analyzer records). Post hoc: Block L was not designed for this contrast.
Per content: ratio = exp(mean log(K6 / K4)) over pairs where both finished; 95% bootstrap over prompts (4,000
replicates, seed 20261103; the S1 reading's method). Standard library only.

    block_l_posthoc.py --l <v4 run>/l/r2 --out BLOCK-L-POSTHOC.json
"""
import argparse, json, math, os, random, statistics as st

NB, SEED = 4000, 20261103


def load(ldir, name):
    return {(r["content"], r["prompt_index"], r["rep"], r["seed"]): r
            for r in json.load(open(os.path.join(ldir, f"{name}-L3.inner.json")))["results"]}


def ok(r):
    return r and r.get("finish_reason") == "stop" and not r.get("hit_cap") and r.get("reasoning_tokens")


def boot(units, rng):
    keys = sorted(units); out = []
    for _ in range(NB):
        out.append(st.mean([x for k in (rng.choice(keys) for _ in keys) for x in units[k]]))
    out.sort(); return out[int(.025 * NB)], out[int(.975 * NB) - 1]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--l", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pairs, unpaired = {}, 0
    for run in ("r1", "r2"):
        k6, k4 = load(a.l, f"K6-{run}"), load(a.l, f"C4-{run}")
        for key, r in k6.items():
            if ok(r) and ok(k4.get(key)):
                pairs[(run,) + key] = math.log(r["reasoning_tokens"] / k4[key]["reasoning_tokens"])
            else:
                unpaired += 1
    out = {"note": "post hoc; CuteAFD v4.0.0 Block L L3, K4-Core-K6 / K4, seed-paired", "pairs": len(pairs),
           "requests_without_a_finished_pair": unpaired, "by_content": {}}
    for c in sorted({k[1] for k in pairs}):
        units = {}
        for (run, cc, p, rep, seed), v in pairs.items():
            if cc == c:
                units.setdefault(p, []).append(v)
        vals = [x for v in units.values() for x in v]
        lo, hi = boot(units, random.Random(SEED))
        out["by_content"][c] = {"pairs": len(vals), "prompts": len(units), "ratio": math.exp(st.mean(vals)),
                                "ratio_ci95_prompts": [math.exp(lo), math.exp(hi)],
                                "per_prompt": {f"p{p}": math.exp(st.mean(v)) for p, v in sorted(units.items())},
                                "prompts_above_1": sum(st.mean(v) > 0 for v in units.values())}
    json.dump(out, open(a.out, "w"), indent=1)
    for c, v in out["by_content"].items():
        print(c, v["pairs"], f"{v['ratio']:.2f}", [round(x, 2) for x in v["ratio_ci95_prompts"]], {k: round(x, 2) for k, x in v["per_prompt"].items()})


if __name__ == "__main__":
    main()
