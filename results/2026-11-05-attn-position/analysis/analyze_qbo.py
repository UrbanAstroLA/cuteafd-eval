#!/usr/bin/env python3
"""vLLM q_b + o_proj arm (NOTE.md "vLLM arm"): two K4-Core-K6 launches (k6-a, k6-b) against two launches with
mla_q_b, mla_o and kda_o in BF16 (qbo-a, qbo-b), on the 93 fixed traces. Reuses position.py's definitions (not its run).
Primary: lp_close, BF16 side minus 6-bit, launch means per arm, per finished trace; 95% bootstrap clustered by question
(and over traces, as G2). Secondary: the four cross-launch pairings, hazard, last-512 mean log p(</think>), position
slopes, KL. kld venv python. Writes analysis/QBO.json."""
import itertools, json
import numpy as np
SRC = "<ap-run>/position.py"
src = open(SRC).read()
exec(compile(src[:src.index('out = {"note"')], SRC, "exec"))  # noqa: S102 - definitions only
N = "<ap-run>"; TLD = "<tl-run>/dumps/runs"
A = {t: load(f"{N}/dumps/runs", t) for t in ("k6-a", "k6-b", "qbo-a", "qbo-b")}  # noqa: F821
G = {t: load(TLD, t) for t in ("k6", "k6r2")}  # noqa: F821
fin = sorted(k for k, v in A["k6-a"].items() if v[1] == "finished")
docs = [A["k6-a"][k][2] for k in fin]


def per(arms, f):
    return np.array([np.mean([f(arms[a][k][0]) for a in arms]) for k in fin])


lpc = lambda t: t["lp_think"][-1]
haz = lambda t: float(np.mean(np.exp(t["lp_think"][-513:-1])))
l512 = lambda t: float(np.mean(t["lp_think"][-513:-1]))


def tboot(d):
    rng = np.random.default_rng(SEED); b = d[rng.integers(0, d.size, (NB, d.size))].mean(1)  # noqa: F821
    return [float(d.mean()), float(np.quantile(b, .025)), float(np.quantile(b, .975))]


out = {"note": "exploratory; NOTE.md vLLM arm", "finished_traces": len(fin), "questions": len(set(docs))}
K = {a: A[a] for a in ("k6-a", "k6-b")}; Q = {a: A[a] for a in ("qbo-a", "qbo-b")}
for name, f in (("lp_close", lpc), ("hazard", haz), ("last512_logp", l512)):
    d = per(Q, f) - per(K, f)
    o = {"delta_by_question": cboot(d, docs), "delta_by_trace": tboot(d)}  # noqa: F821
    o["launch_k6_b_minus_a"] = tboot(np.array([f(A["k6-b"][k][0]) - f(A["k6-a"][k][0]) for k in fin]))
    o["launch_qbo_b_minus_a"] = tboot(np.array([f(A["qbo-b"][k][0]) - f(A["qbo-a"][k][0]) for k in fin]))
    o["cross_pairings"] = {f"{q}-{k}": tboot(np.array([f(A[q][kk][0]) - f(A[k][kk][0]) for kk in fin]))
                           for q, k in itertools.product(Q, K)}
    o["vs_g2_k6_launches"] = {f"{q}-g2{k}": tboot(np.array([f(A[q][kk][0]) - f(G[k][kk][0]) for kk in fin]))
                              for q, k in itertools.product(Q, G)}
    out[name] = o
band = max(abs(out["lp_close"]["launch_k6_b_minus_a"][0]), abs(out["lp_close"]["launch_qbo_b_minus_a"][0]))
p = out["lp_close"]
out["reading_rule"] = {"ci_excludes_0_positive": p["delta_by_question"][1] > 0, "exceeds_launch_band": abs(p["delta_by_question"][0]) > band,
                       "launch_band": band, "all_cross_pairings_positive": all(v[0] > 0 for v in p["cross_pairings"].values())}
out["reading_rule"]["supported"] = all(out["reading_rule"][k] for k in ("ci_excludes_0_positive", "exceeds_launch_band", "all_cross_pairings_positive"))
pos = {}
for q, k in itertools.product(Q, K):
    c = contrast(A[k], A[q])  # noqa: F821
    pos[f"{q}-{k}"] = {m: c[m] for m in ("m1_slope_kl_per_log2pos", "m1_kl_mean_per_trace", "m2_lp_close_slope_per_log2pos", "m2_last512_slope_per_log2pos", "m1_kl_by_bin")}
pos["k6-b-k6-a"] = {m: contrast(A["k6-a"], A["k6-b"])[m] for m in ("m1_kl_mean_per_trace", "m1_slope_kl_per_log2pos")}  # noqa: F821
out["position"] = pos
json.dump(out, open(f"{N}/analysis/QBO.json", "w"), indent=1)
f3 = lambda v: "%+.4f [%+.4f, %+.4f]" % tuple(v)
for m in ("lp_close", "hazard", "last512_logp"):
    o = out[m]; print(m, "by question", f3(o["delta_by_question"]), "by trace", f3(o["delta_by_trace"]),
                      "| k6 b-a", f3(o["launch_k6_b_minus_a"]), "qbo b-a", f3(o["launch_qbo_b_minus_a"]))
    print("   cross", {k: round(v[0], 4) for k, v in o["cross_pairings"].items()}, "vs G2 k6", {k: round(v[0], 4) for k, v in o["vs_g2_k6_launches"].items()})
print("rule", out["reading_rule"])
for k, v in pos.items():
    print(k, {m: (f3(x) if isinstance(x, list) else None) for m, x in v.items() if m != "m1_kl_by_bin"})
