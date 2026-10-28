#!/usr/bin/env python3
"""K4 Q2 per-position values (V and C arms only), for the public per-position file q2-rows.csv.

The frozen Q2 scorer (score_q2_20.py) writes window and document means only. This applies its own per-row
definitions (k4score.arm_window, k4score.pair_kl20, the same plan and row checks) to the same captures and saves
one value per scored position, so the published means can be recomputed from the rows:
  nll_<arm>            -lpE(t) of the actual next token (exact under top-20)
  kl20n_<a>_<b>        KL20n(a || b), the top-20 intersection cells + rest form (pair_kl20 kl20_ab)
  top1_<a>_<b>         1 when both arms' most likely token is the same
Arms: V-r1, V-r2 (two vLLM launches), C-r1 (CuteAFD; its repeat C-r1b is checked byte-identical and not repeated).

  nice -n 19 ionice -c3 taskset -c 0-3 <venv>/bin/python -B q2_rows.py OUT.npz
"""
import json
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, "<k4-run>/scorers")
import k4score as S  # noqa: E402

Q = "<k4-run>/q"
PLAN = "<run>/stage0/scorers/plans/q2.cuteafd-plan.json"
ARMS = {"V-r1": f"{Q}/V-r1/q2", "V-r2": f"{Q}/V-r2/q2", "C-r1": f"{Q}/C-r1/q2", "C-r1b": f"{Q}/C-r1b/q2"}


def main(out):
    plan = json.load(open(PLAN))["windows"]
    cols = {k: [] for k in ("window", "row", "nll_Vr1", "nll_Vr2", "nll_Cr1", "kl20n_Vr1_Cr1", "kl20n_Vr2_Cr1",
                            "top1_Vr1_Cr1", "top1_Vr2_Cr1", "kl20n_Vr1_Vr2", "top1_Vr1_Vr2")}
    for w in plan:
        wid = w["window_id"]
        toks = np.asarray(w["tokens"], dtype=np.int64)
        want = np.asarray(sorted(w["positions"]), dtype=np.int64)
        e = {}
        for n, d in ARMS.items():
            e[n] = S.arm_window(d, wid)
            if not np.array_equal(e[n]["r"], want) or not np.array_equal(e[n]["tok"], toks[want + 1]):
                raise SystemExit(f"{n} {wid}: rows differ from the plan")
        for k in ("ids", "v32", "t32"):
            if not np.array_equal(e["C-r1"][k], e["C-r1b"][k]):
                raise SystemExit(f"{wid}: C-r1b differs from C-r1 ({k}); add it as an arm")
        p1, p2, pf = S.pair_kl20(e["V-r1"], e["C-r1"]), S.pair_kl20(e["V-r2"], e["C-r1"]), S.pair_kl20(e["V-r1"], e["V-r2"])
        n = len(want)
        cols["window"] += [wid] * n
        cols["row"].append(want)
        cols["nll_Vr1"].append(-e["V-r1"]["t32"]); cols["nll_Vr2"].append(-e["V-r2"]["t32"]); cols["nll_Cr1"].append(-e["C-r1"]["t32"])
        cols["kl20n_Vr1_Cr1"].append(p1["kl20_ab"]); cols["kl20n_Vr2_Cr1"].append(p2["kl20_ab"])
        cols["top1_Vr1_Cr1"].append(p1["agree"]); cols["top1_Vr2_Cr1"].append(p2["agree"])
        cols["kl20n_Vr1_Vr2"].append(pf["kl20_ab"]); cols["top1_Vr1_Vr2"].append(pf["agree"])
    arrs = {k: (np.asarray(v) if k == "window" else np.concatenate(v)) for k, v in cols.items()}
    arrs["row"] = arrs["row"].astype(np.int64)
    np.savez_compressed(out, **arrs)
    print(f"wrote {out}: {len(arrs['row'])} rows, {len(plan)} windows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
