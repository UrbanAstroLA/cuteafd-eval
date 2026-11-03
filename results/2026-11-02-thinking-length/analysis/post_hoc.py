#!/usr/bin/env python3
"""Post-hoc contrasts, computed after G2 and G4 were read. Not part of any frozen reading; quoted as post hoc.

    python3 post_hoc.py --scores G2-SCORES-A1.json --out POST-HOC.json [--dumps <capture out>/runs --reg <traces/reg>]

From G2-SCORES-A1.json alone (per-trace values):
  lp_close, hazard and max_p_think contrasts of every arm against two other bases: the second 6-bit launch (k6r2) and
  the mean of the two 6-bit launches (pooled), paired over traces, 2,000-replicate bootstrap as in score_stop.py.
With the reduced dumps (local; the dumps hold model output and are not published):
  top-64 KL(k6 || k6r2) over every trace row and over the last 512 rows of finished traces (score_stop.py convention),
  and loop check c: mean chosen-token log-prob per not-finished trace, arm - k6 for all and k6r2.
"""
import argparse, glob, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_stop as S  # noqa: E402

FIELDS = (("lp_close", "finished"), ("hazard", "finished"), ("max_p_think", "not_finished"))


def contrasts(scores):
    pa = scores["per_arm"]
    out = {}
    for base in ("k6r2", "pooled"):
        out[base] = {}
        for arm in sorted(pa):
            if arm in ("k6", "k6r2"):
                continue
            c = {}
            for field, kind in FIELDS:
                keys = sorted(k for k, m in pa["k6"]["per_trace"].items() if (m["kind"] == "finished") == (kind == "finished"))
                if base == "pooled":
                    x = [(pa["k6"]["per_trace"][k][field] + pa["k6r2"]["per_trace"][k][field]) / 2 for k in keys]
                else:
                    x = [pa[base]["per_trace"][k][field] for k in keys]
                y = [pa[arm]["per_trace"][k][field] for k in keys]
                d, ci = S.boot_paired(x, y)
                c[field] = {"delta": d, "ci95": ci, "n": len(keys)}
            out[base][arm] = c
    return out


def from_dumps(dumps, reg_dir):
    reg = S.load_reg(reg_dir)
    T = {arm: S.trace_measures(os.path.join(dumps, arm), reg) for arm in ("k6", "k6r2", "all")}
    kl_all, kl_stop = [], []
    for key, (m, t) in T["k6r2"].items():
        rt = T["k6"][key][1]
        k = S.kl_top(rt["topk_ids"], rt["topk_logprobs"].astype(np.float64), t["topk_ids"], t["topk_logprobs"].astype(np.float64))
        kl_all.append(float(k.mean()))
        if m["kind"] == "finished":
            kl_stop.append(float(k[-512:].mean()))
    non = sorted(k for k, v in T["k6"].items() if v[0]["kind"] != "finished")
    chosen = {arm: [float(T[arm][k][1]["chosen_logprobs"].astype(np.float64).mean()) for k in non] for arm in T}
    c = {"traces": non, "rows_per_trace": [T["k6"][k][0]["rows"] for k in non],
         "mean_chosen_logprob": {arm: float(np.mean(v)) for arm, v in chosen.items()},
         "per_trace": chosen}
    for arm in ("all", "k6r2"):
        d, ci = S.boot_paired(chosen["k6"], chosen[arm])
        c[f"{arm}_minus_k6"] = {"delta": d, "ci95": ci}
    return {"kl64_k6_vs_k6r2": {"all_rows": float(np.mean(kl_all)), "last_512_rows_finished": float(np.mean(kl_stop)),
                                "traces": len(kl_all), "finished": len(kl_stop)},
            "loop_check_c": c}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--dumps"); ap.add_argument("--reg")
    a = ap.parse_args()
    out = {"about": "post hoc, computed after G2 and G4 were read; not a frozen reading",
           "contrasts": contrasts(json.load(open(a.scores)))}
    if a.dumps:
        out.update(from_dumps(a.dumps, a.reg))
    json.dump(out, open(a.out, "w"), indent=1)
    show = {b: {arm: {f: (round(v["delta"], 4), [round(x, 4) for x in v["ci95"]]) for f, v in c.items() if f == "lp_close"}
                for arm, c in cs.items() if arm in ("all", "mla_o", "mla_q_b")} for b, cs in out["contrasts"].items()}
    print(json.dumps(show, indent=1))
    if a.dumps:
        print(json.dumps({"kl64_k6_vs_k6r2": out["kl64_k6_vs_k6r2"],
                          "c": {k: v for k, v in out["loop_check_c"].items() if k.endswith("_k6") or k == "mean_chosen_logprob"}}, indent=1))


if __name__ == "__main__":
    main()
