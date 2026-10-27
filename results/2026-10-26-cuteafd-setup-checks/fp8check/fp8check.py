#!/usr/bin/env python3
"""CPU only. For the 179 projection tensors Core-FP8 replaced:
  1. dequantize the official FP8 (E4M3 x FP32 128x128 block scale_inv) and
     compare it with K3.25-v1's BF16 tensor;
  2. quantize K3.25-v1's BF16 to E4M3 with amax/448 128x128 block scales (the
     usual recipe; what a load-time quantizer would plausibly do) and compare
     codes and scales with the official FP8 bytes.
Usage: fp8check.py BF16_SNAPSHOT FP8_SNAPSHOT OUT_JSON"""
import json, os, sys
import torch
from safetensors import safe_open

bf_dir, f8_dir, out = sys.argv[1:4]
bf_map = json.load(open(os.path.join(bf_dir, "model.safetensors.index.json")))["weight_map"]
f8_map = json.load(open(os.path.join(f8_dir, "model.safetensors.index.json")))["weight_map"]
names = sorted(n for n in f8_map if n.endswith(".weight") and n + "_scale_inv" in f8_map and n in bf_map)

def get(d, m, n):
    with safe_open(os.path.join(d, m[n]), "pt") as f:
        return f.get_tensor(n)

def expand(s, shape, b=128):
    return s.repeat_interleave(b, 0).repeat_interleave(b, 1)[: shape[0], : shape[1]]

rows, tot = [], {"n": 0, "err2": 0.0, "ref2": 0.0, "codes": 0, "codes_equal": 0, "scales": 0, "scales_equal": 0}
for n in names:
    bf = get(bf_dir, bf_map, n).float()
    q = get(f8_dir, f8_map, n)
    s = get(f8_dir, f8_map, n + "_scale_inv").float()
    deq = q.float() * expand(s, q.shape)
    diff = deq - bf
    # Own quantization of the BF16 tensor.
    R, C = bf.shape
    pr, pc = (-R) % 128, (-C) % 128
    bp = torch.nn.functional.pad(bf, (0, pc, 0, pr)).view((R + pr) // 128, 128, (C + pc) // 128, 128)
    amax = bp.abs().amax(dim=(1, 3)).clamp_min(1e-12)
    my_s = amax / 448.0
    my_q = (bf / expand(my_s, bf.shape)).to(torch.float8_e4m3fn)
    codes_eq = int((my_q.view(torch.uint8) == q.view(torch.uint8)).sum())
    scales_eq = int((my_s == s).sum())
    r = {"name": n, "shape": list(bf.shape),
         "rel_fro_err_official_vs_bf16": float(diff.norm() / bf.norm()),
         "max_abs_diff": float(diff.abs().max()),
         "own_quant_codes_equal_frac": codes_eq / q.numel(),
         "own_quant_scales_equal_frac": scales_eq / s.numel(),
         "own_vs_official_scale_max_rel": float(((my_s - s).abs() / s.abs().clamp_min(1e-30)).max())}
    rows.append(r)
    tot["n"] += 1; tot["err2"] += float(diff.pow(2).sum()); tot["ref2"] += float(bf.pow(2).sum())
    tot["codes"] += q.numel(); tot["codes_equal"] += codes_eq; tot["scales"] += s.numel(); tot["scales_equal"] += scales_eq
    print("%-70s rel %.5f codes= %.4f scales= %.4f" % (n, r["rel_fro_err_official_vs_bf16"], r["own_quant_codes_equal_frac"], r["own_quant_scales_equal_frac"]), flush=True)
summary = {"tensors": tot["n"], "rel_fro_err_all": (tot["err2"] / tot["ref2"]) ** 0.5,
           "own_quant_codes_equal_frac": tot["codes_equal"] / tot["codes"],
           "own_quant_scales_equal_frac": tot["scales_equal"] / tot["scales"]}
json.dump({"summary": summary, "tensors": rows}, open(out, "w"), indent=1)
print(json.dumps(summary, indent=1))
