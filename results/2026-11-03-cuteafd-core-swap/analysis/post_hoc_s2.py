#!/usr/bin/env python3
"""Post hoc (not in the frozen protocol): where max p(</think>) sits on the 16 unfinished traces, and the same measure
with the opening scored row removed, averaged per question (doc). Needs numpy (kld venv). Writes POST-HOC-S2.json.

Why: the frozen per-trace max p(</think>) falls on the first scored row (the opening of the thinking span) in every
arm, which every seed of a question shares, so it is a per-prompt value repeated once per trace (d13: 5 of 16).
Also counts the same property on the vLLM investigation's capture dumps (12 arms), which are not published."""
import collections, glob, json, os, sys
import numpy as np

sys.path.insert(0, "<tl-run>/capture/plugin")
from glm53_capture_plugin import core  # noqa: E402

R = "<cs-run>"; RUNS = f"{R}/s2/runs"; ARMS = ("C-K6", "C-K6x", "C-K4")
ws = sorted(os.path.relpath(p, f"{RUNS}/C-K6")[:-len(".safetensors")] for p in glob.glob(f"{RUNS}/C-K6/*/*-not.safetensors"))
per = {}
for w in ws:
    per[w] = {}
    for a in ARMS:
        t, _ = core.read_safetensors(f"{RUNS}/{a}/{w}.safetensors", mmap=False)
        rows = np.asarray(t["rows"]); p = np.exp(np.asarray(t["sel_logprobs"])[:, 0].astype(np.float64))
        per[w][a] = {"argmax_row": int(rows[p.argmax()]), "first_row": int(rows[0]), "max_p": float(p.max()),
                     "max_p_after_first": float(p[1:].max()), "mean_p_after_first": float(p[1:].mean())}
docs = collections.defaultdict(list)
for w in ws:
    docs[w.split("-")[1]].append(w)
by_doc = {d: {a: {k: float(np.mean([per[w][a][k] for w in L])) for k in ("max_p", "max_p_after_first", "mean_p_after_first")}
              for a in ARMS} | {"traces": len(L)} for d, L in docs.items()}
out = {"note": "post hoc; not part of the frozen reading", "argmax_at_first_row": sum(
    per[w][a]["argmax_row"] == per[w][a]["first_row"] for w in ws for a in ARMS), "of": len(ws) * len(ARMS),
    "by_doc": by_doc, "per_trace": per}
V = "<tl-run>/dumps/runs"
vn = vat = 0
for p in sorted(glob.glob(f"{V}/*/*/*-not.safetensors")):
    t, _ = core.read_safetensors(p, mmap=False)
    vn += 1; vat += int(np.asarray(t["sel_logprobs"])[:, 0].argmax() == 0)
out["vllm_g2_argmax_at_first_row"] = vat; out["vllm_g2_of"] = vn
json.dump(out, open(f"{R}/analysis/POST-HOC-S2.json", "w"), indent=1)
print(f"argmax at the first scored row: {out['argmax_at_first_row']} of {out['of']} (CuteAFD), {vat} of {vn} (vLLM G2)")
for d, v in by_doc.items():
    print(d, v["traces"], " ".join(f"{a} {v[a]['max_p']:.2e}/{v[a]['max_p_after_first']:.2e}" for a in ARMS))
