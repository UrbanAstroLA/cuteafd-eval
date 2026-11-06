#!/usr/bin/env python3
"""Post hoc (after reading QBO.json; not in the frozen rule): lp_close of the G2 whole-core BF16 launch ("all") and of the
G2 single-group launches against all four K4-Core-K6 launches (G2 k6, k6r2; today k6-a, k6-b), and qbo (mean of qbo-a,
qbo-b) against "all". Same estimator as analyze_qbo.py. Writes analysis/POSTHOC-QBO-ALL.json."""
import json
import numpy as np
SRC = "<ap-run>/position.py"
src = open(SRC).read()
exec(compile(src[:src.index('out = {"note"')], SRC, "exec"))  # noqa: S102 - definitions only
N = "<ap-run>"; TLD = "<tl-run>/dumps/runs"
A = {t: load(f"{N}/dumps/runs", t) for t in ("k6-a", "k6-b", "qbo-a", "qbo-b")}  # noqa: F821
for t in ("k6", "k6r2", "all", "mla_q_b", "mla_o", "kda_o"):
    A["g2-" + t] = load(TLD, t)  # noqa: F821
fin = sorted(k for k, v in A["k6-a"].items() if v[1] == "finished"); docs = [A["k6-a"][k][2] for k in fin]
lpc = lambda arm: np.array([A[arm][k][0]["lp_think"][-1] for k in fin])
K = np.mean([lpc(a) for a in ("g2-k6", "g2-k6r2", "k6-a", "k6-b")], 0)
Q = np.mean([lpc(a) for a in ("qbo-a", "qbo-b")], 0)
out = {"note": "post hoc", "vs_mean_of_4_k6_launches": {a: cboot(lpc(a) - K, docs) for a in  # noqa: F821
       ("g2-all", "g2-mla_q_b", "g2-mla_o", "g2-kda_o", "qbo-a", "qbo-b")},
       "qbo_minus_g2_all": cboot(Q - lpc("g2-all"), docs),  # noqa: F821
       "k6_launch_spread": {a: float((lpc(a) - K).mean()) for a in ("g2-k6", "g2-k6r2", "k6-a", "k6-b")}}
json.dump(out, open(f"{N}/analysis/POSTHOC-QBO-ALL.json", "w"), indent=1)
f = lambda v: "%+.4f [%+.4f, %+.4f]" % tuple(v)
for k, v in out["vs_mean_of_4_k6_launches"].items():
    print(k, f(v))
print("qbo - all", f(out["qbo_minus_g2_all"])); print("k6 launches vs their mean", {k: round(v, 4) for k, v in out["k6_launch_spread"].items()})
