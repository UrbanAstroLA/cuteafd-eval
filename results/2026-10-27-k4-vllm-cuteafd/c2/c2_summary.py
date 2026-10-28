#!/usr/bin/env python3
"""K4 Q2 document c2: per-window summary for the public note (V and C arms only), from the top-20 captures.

Per window: V-r1's mean NLL of the actual token and its mean top-20 entropy (the 20 returned probabilities
renormalised); per pair (V-r1|V-r2, V-r1|C-r1, V-r2|C-r1): rows where |NLL_a - NLL_b| > 1 nat. For V-r1|V-r2 on
those rows: how many have one launch near-certain of the actual token (p > 0.9), and how many are top-1/top-2 swaps
(the launches' most likely ids differ and each launch ranks the other's first id second).

  nice -n 19 taskset -c 0-3 <venv>/bin/python -B c2_summary.py OUT.json
"""
import json
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, "<k4-run>/scorers")
import k4score as S  # noqa: E402

Q = "<k4-run>/q"
WINDOWS = ["q2-code-c2-032k", "q2-code-c2-064k", "q2-code-c2-128k", "q2-code-c0-064k", "q2-code-c1-064k",
           "q2-prose-pg28988-064k"]
PAIRS = [("V-r1", "V-r2"), ("V-r1", "C-r1"), ("V-r2", "C-r1")]


def main(out):
    res = {}
    for w in WINDOWS:
        e = {a: S.arm_window(f"{Q}/{a}/q2", w) for a in ("V-r1", "V-r2", "C-r1")}
        p = np.exp(e["V-r1"]["v32"]); pn = p / p.sum(axis=1, keepdims=True)
        r = {"scored_rows": int(len(e["V-r1"]["r"])), "first_row": int(e["V-r1"]["r"][0]), "last_row": int(e["V-r1"]["r"][-1]),
             "nll_V-r1": float(-e["V-r1"]["t32"].mean()), "top20_entropy_V-r1": float(-(pn * np.log(pn)).sum(axis=1).mean()),
             "rows_absdnll_gt_1nat": {}}
        for a, b in PAIRS:
            r["rows_absdnll_gt_1nat"][f"{a}|{b}"] = int((np.abs(e[a]["t32"] - e[b]["t32"]) > 1.0).sum())
        a, b = e["V-r1"], e["V-r2"]
        big = np.abs(a["t32"] - b["t32"]) > 1.0
        conf = (np.maximum(np.exp(a["t32"]), np.exp(b["t32"])) > 0.9) & big
        swap = (a["ids"][:, 0] != b["ids"][:, 0]) & (a["ids"][:, 1] == b["ids"][:, 0]) & (b["ids"][:, 1] == a["ids"][:, 0]) & big
        r["V-r1|V-r2 big rows"] = {"one_launch_p_actual_gt_0.9": int(conf.sum()), "top1_top2_swaps": int(swap.sum())}
        res[w] = r
    json.dump({"about": "Q2 document c2 and controls, K4 top-20 captures, arms V-r1, V-r2 (two vLLM launches) and C-r1 "
                        "(CuteAFD). Definitions: c2_summary.py docstring.", "windows": res}, open(out, "w"), indent=1)
    for w, r in res.items():
        print(w, round(r["nll_V-r1"], 3), round(r["top20_entropy_V-r1"], 3), r["rows_absdnll_gt_1nat"], r["V-r1|V-r2 big rows"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
