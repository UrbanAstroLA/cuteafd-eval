#!/usr/bin/env python3
"""G0 integrity check (CPU): every downloaded BF16 core tensor against K4-Core-K6's own 6-bit record decoded with the
route-b decoder (exl3_core_dequant.reconstruct_bf16, exact fp64 then one BF16 rounding). A correct byte range agrees to
within 6-bit quantization error; a misplaced or corrupt range is uncorrelated (relative error ~1.4).
Runs in the v0.9.2-experimental image, --network none. Writes g0/core-check.json.
"""
import glob, json, os, sys, time
import torch
from safetensors import safe_open
sys.path.insert(0, "/patch")
from exl3_core_dequant import reconstruct_bf16
torch.set_num_threads(int(os.environ.get("THREADS", "12")))
K6 = glob.glob("/k6/snapshots/*/")[0]
q = json.load(open(K6 + "quantize_config.json"))["tensor_storage"]
wmap = json.load(open(K6 + "model.safetensors.index.json"))["weight_map"]
core = sorted(k for k, v in q.items() if v.get("bits_per_weight") == 6)
out, t0 = {}, time.time()
with safe_open("/core/core.safetensors", "pt") as bf:
    for i, owner in enumerate(core):
        e = q[owner]; parts = {}
        for full in e["stored_tensors"]:
            field = full.rsplit(".", 1)[1]
            with safe_open(K6 + wmap[full], "pt") as f:
                parts[field] = f.get_tensor(full)
        w6 = reconstruct_bf16(e, parts, owner, device="cpu").double()
        wb = bf.get_tensor(owner + ".weight").double()
        if tuple(w6.shape) != tuple(wb.shape):
            out[owner] = {"shape_mismatch": [list(w6.shape), list(wb.shape)]}; continue
        d = (w6 - wb)
        rel = float(d.norm() / wb.norm()); cos = float((w6 * wb).sum() / (w6.norm() * wb.norm()))
        out[owner] = {"rel_err": rel, "cos": cos, "numel": wb.numel(), "bf16_zero": bool(wb.abs().max() == 0)}
        print(f"{i + 1}/316 {owner} rel {rel:.5f} cos {cos:.6f} {time.time() - t0:.0f}s", flush=True)
        del w6, wb, d, parts
bad = {k: v for k, v in out.items() if "rel_err" not in v or v["rel_err"] > 0.05 or v["bf16_zero"]}
rels = sorted(v["rel_err"] for v in out.values() if "rel_err" in v)
summary = {"tensors": len(out), "fail": bad, "rel_err_min": rels[0], "rel_err_median": rels[len(rels) // 2], "rel_err_max": rels[-1],
           "rule": "pass when rel_err <= 0.05 and the BF16 tensor is non-zero; uncorrelated bytes give ~1.4"}
json.dump({"summary": summary, "per_tensor": out}, open("/g0/core-check.json", "w"), indent=1)
print(json.dumps(summary, indent=1)); sys.exit(1 if bad else 0)
