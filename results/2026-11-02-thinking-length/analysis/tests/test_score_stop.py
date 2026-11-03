"""Synthetic check of score_stop.py: three arms (k6, all, half) over two finished and one not-finished trace; 'all' adds
+2 nats to </think> on the last 600 rows, 'half' +1. Expected: half closes ~half the lp_close gap; kl to ref is 0 for all."""
import json, os, subprocess, sys, tempfile, types
import numpy as np
sys.path.insert(0, "/run/capture/plugin")
from glm53_capture_plugin import core
V, THINK = 154880, 154842
tmp = tempfile.mkdtemp(); reg = os.path.join(tmp, "reg"); dumps = os.path.join(tmp, "runs")
rng = np.random.default_rng(0)
traces = []
for i, kind in enumerate(["finished", "finished", "not_finished"]):
    n = 700
    toks = rng.integers(0, 1000, n).tolist()
    if kind == "finished": toks[-1] = THINK
    rows = list(range(0, n - 1))
    d = {"window_id": f"tr{i:03d}", "set": "tr", "tokens": toks, "rows": rows,
         "meta": {"reduce": {"topk": 64, "token_ids": [THINK, 151336]}, "doc": 1, "kind": kind}}
    os.makedirs(os.path.join(reg, "tr"), exist_ok=True); json.dump(d, open(os.path.join(reg, "tr", f"tr{i:03d}.json"), "w"))
    traces.append((d, np.asarray(toks)))
base_logits = {d["window_id"]: rng.normal(0, 3, (699, 2000)).astype(np.float32) for d, _ in traces}
for arm, bump in (("k6", 0.0), ("all", 2.0), ("half", 1.0)):
    for d, toks in traces:
        e = core.Entry(d["window_id"], "tr", len(toks), core.tokens_sha256(toks), np.asarray(d["rows"], np.int32), "", d["meta"])
        dump = core.ReducedDump(os.path.join(dumps, arm), e, V, {}, toks)
        z = np.full((699, V), -30.0, np.float32); z[:, :2000] = base_logits[d["window_id"]]; z[:, THINK] = 0.0
        z[-600:, THINK] += bump
        z = z - (z.max(1, keepdims=True) + np.log(np.exp(z - z.max(1, keepdims=True)).sum(1, keepdims=True)))
        for s in range(0, 699, 233): dump.write(s, z[s:s + 233])
        dump.close(True)
out = os.path.join(tmp, "s.json")
r = subprocess.run([sys.executable, "/run/analysis/score_stop.py", "--dumps", dumps, "--reg", reg, "--out", out], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-2000:]
S = json.load(open(out)); c = S["contrast_vs_base"]
assert abs(c["half"]["lp_close"]["closure"] - 0.5) < 0.15, c["half"]["lp_close"]
assert c["all"]["lp_close"]["closure"] == 1.0 and S["per_arm"]["all"]["kl64_vs_ref_all_rows"] < 1e-9
assert c["half"]["max_p_think"]["delta"] > 0
print("PASS", json.dumps({k: {m: round(v["closure"], 3) for m, v in x.items() if v["closure"] is not None} for k, x in c.items()}))
