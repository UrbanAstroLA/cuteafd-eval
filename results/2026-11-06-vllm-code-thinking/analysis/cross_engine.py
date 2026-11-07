#!/usr/bin/env python3
"""Post hoc (not in the frozen rule): each arm of this run against each arm of the CuteAFD code study, same prompts and
seeds. Seeds do not give the same samples across engines, so this compares per-prompt means of log reasoning-token
ratios over the 4 seeds; descriptive only. Standard library only.
    cross_engine.py --l <run>/l --cuteafd <ct-run>/l --out cross_engine.json"""
import argparse, json, math, os, statistics as st


def load(ldir, arms):
    res = json.load(open(os.path.join(ldir, "L-analysis.json")))["results"]
    return {a: {(r["prompt_index"], r["rep"]): r for r in res if r["label"] == a} for a in arms}


def ok(r):
    return r and r.get("finish_reason") == "stop" and not r.get("hit_cap") and r.get("reasoning_tokens")


def ratio(A, B, prompts):
    per = {}
    for k, r in A.items():
        if k[0] in prompts and ok(r) and ok(B.get(k)):
            per.setdefault(k[0], []).append(math.log(r["reasoning_tokens"] / B[k]["reasoning_tokens"]))
    m = [st.mean(v) for v in per.values()]
    return {"ratio": math.exp(st.mean(m)), "prompts_above_1": sum(x > 0 for x in m), "prompts": len(m)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--l", required=True); ap.add_argument("--cuteafd", required=True)
    ap.add_argument("--out", required=True); a = ap.parse_args()
    arms = {**load(a.l, ("V-K6", "V-BF16")), **load(a.cuteafd, ("C-K6", "C-K6x"))}
    out = {"median_reasoning_tokens": {k: st.median([r["reasoning_tokens"] for r in v.values() if ok(r)]) for k, v in arms.items()},
           "all_tests_pass_of_finished": {k: sum(bool((r.get("check") or {}).get("all_pass")) for r in v.values() if ok(r)) for k, v in arms.items()},
           "ratios": {}}
    for x, y in (("C-K6", "V-K6"), ("C-K6", "V-BF16"), ("C-K6x", "V-BF16"), ("C-K6x", "V-K6"), ("C-K6", "C-K6x"), ("V-K6", "V-BF16")):
        out["ratios"][f"{x}/{y}"] = {"p4_p15": ratio(arms[x], arms[y], range(4, 16)), "all_p0_p15": ratio(arms[x], arms[y], range(16))}
    json.dump(out, open(a.out, "w"), indent=1); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
