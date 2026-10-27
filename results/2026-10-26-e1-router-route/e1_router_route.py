#!/usr/bin/env python3
"""E1 for CuteAFD: are GLM-5.3-Flash router logits bit-identical across the
router program's route switch (skinny GEMV at <= 160 rows, TMA tensor-core GEMM
above)? And if not, does expert selection or its weights change?

Runs the same kernel class the served program builds (glmf.py _RouterScores:
RoutedBf16Projection(288, 4096, out_dtype=Float32), default routes), JIT-compiled
from the image's sparkinfer b12x, with the checkpoint's real router weights and
correction biases. One GPU, small memory. The served engine runs an AOT export of
this program; the JIT build is the same source, not the same binary.

Inputs are approximations of router inputs (the real input is the post-attention
RMSNorm of the mHC-collapsed residual, which this test does not reproduce):
  embed  : RMS-normalized embedding rows of seeded random token ids x post-attention norm weight
  random : N(0,1) rows x post-attention norm weight
For each layer and input kind, BATCHES batches of 160 base rows:
  A = rows in a 160-row launch (skinny)      C = first 100 rows in a 100-row launch (skinny)
  B = same rows in a 161-row launch (TMA)    D = same rows in a 512-row launch (TMA)
Selection follows the config: sigmoid scores, top-8 of (score + correction bias),
weights = selected scores normalized x routed_scaling_factor (2.5).
"""
from __future__ import annotations

import json
import os
import sys

import torch
from safetensors import safe_open

SNAP, OUT = sys.argv[1], sys.argv[2]
LAYERS = [3, 12, 24, 36, 44]
BATCHES = 40
TOPK, SCALE = 8, 2.5
dev = torch.device("cuda:0")


def compile_router(n=288, k=4096):
    import cutlass
    import cutlass.cute as cute
    from b12x._lib.compiler import KernelCompileSpec, compile as compile_cute
    from b12x._lib.utils import current_cuda_stream, make_ptr
    from b12x.gemm.bf16_gemv._skinny import RoutedBf16Projection

    launch = RoutedBf16Projection(n, k, out_dtype=cutlass.Float32)
    ptr = lambda dt: make_ptr(dt, 16, cute.AddressSpace.gmem, assumed_align=16)  # noqa: E731
    compiled = compile_cute(launch, ptr(cutlass.BFloat16), ptr(cutlass.BFloat16), ptr(cutlass.Float32),
                            cutlass.Int32(1), current_cuda_stream(),
                            compile_spec=KernelCompileSpec.from_key("local.e1_router", 1, launch.key()))

    def run(x, w):
        out = torch.full((x.shape[0], n), float("nan"), dtype=torch.float32, device=dev)
        p = lambda t, dt: make_ptr(dt, t.data_ptr(), cute.AddressSpace.gmem, assumed_align=16)  # noqa: E731
        compiled(p(x, cutlass.BFloat16), p(w, cutlass.BFloat16), p(out, cutlass.Float32),
                 cutlass.Int32(x.shape[0]), current_cuda_stream())
        torch.cuda.synchronize()
        return out

    return run, launch.max_skinny_rows


def tensors(names):
    idx = json.load(open(os.path.join(SNAP, "model.safetensors.index.json")))["weight_map"]
    out = {}
    for n in names:
        with safe_open(os.path.join(SNAP, idx[n]), "pt") as f:
            out[n] = f.get_tensor(n)
    return out


def select(logits, bias):
    s = torch.sigmoid(logits.float())
    ids = torch.topk(s + bias, TOPK, dim=-1).indices
    w = torch.gather(s, -1, ids)
    w = w / w.sum(-1, keepdim=True) * SCALE
    order = torch.argsort(ids, dim=-1)
    return torch.gather(ids, -1, order), torch.gather(w, -1, order)


def compare(a, b, bias):
    ia, wa = select(a, bias)
    ib, wb = select(b, bias)
    same_set = (ia == ib).all(-1)
    wdiff = (wa - wb).abs()[same_set]
    return {"rows": a.shape[0],
            "logits_bit_equal_frac": float((a.view(torch.int32) == b.view(torch.int32)).float().mean()),
            "rows_all_bit_equal_frac": float((a.view(torch.int32) == b.view(torch.int32)).all(-1).float().mean()),
            "logit_max_abs_diff": float((a - b).abs().max()),
            "top8_set_equal_frac": float(same_set.float().mean()),
            "top8_set_changed_rows": int((~same_set).sum()),
            "weight_max_abs_diff_same_set": float(wdiff.max()) if wdiff.numel() else None,
            "weight_bit_equal_frac_same_set": float((wdiff == 0).float().mean()) if wdiff.numel() else None}


def merge(parts):
    tot = sum(p["rows"] for p in parts)
    m = {"rows": tot}
    for k in ("logits_bit_equal_frac", "rows_all_bit_equal_frac", "top8_set_equal_frac"):
        m[k] = sum(p[k] * p["rows"] for p in parts) / tot
    m["top8_set_changed_rows"] = sum(p["top8_set_changed_rows"] for p in parts)
    m["logit_max_abs_diff"] = max(p["logit_max_abs_diff"] for p in parts)
    ws = [p["weight_max_abs_diff_same_set"] for p in parts if p["weight_max_abs_diff_same_set"] is not None]
    m["weight_max_abs_diff_same_set"] = max(ws) if ws else None
    return m


def main():
    run, skinny_rows = compile_router()
    assert skinny_rows == 160, skinny_rows
    pre = "model.language_model."
    names = [pre + "embed_tokens.weight"]
    for L in LAYERS:
        names += [f"{pre}layers.{L}.mlp.gate.weight", f"{pre}layers.{L}.mlp.gate.e_score_correction_bias",
                  f"{pre}layers.{L}.post_attention_layernorm.weight"]
    t = tensors(names)
    emb = t[pre + "embed_tokens.weight"]
    report = {"snapshot": SNAP, "skinny_max_rows": skinny_rows, "layers": LAYERS, "batches": BATCHES,
              "torch": torch.__version__, "device": torch.cuda.get_device_name(0), "cells": []}
    gen = torch.Generator().manual_seed(70901)
    for L in LAYERS:
        w = t[f"{pre}layers.{L}.mlp.gate.weight"].to(dev).bfloat16().contiguous()
        bias = t[f"{pre}layers.{L}.mlp.gate.e_score_correction_bias"].to(dev).float()
        ln = t[f"{pre}layers.{L}.post_attention_layernorm.weight"].float()
        for kind in ("embed", "random"):
            parts = {"skinny160_vs_tma161": [], "skinny160_vs_skinny100": [], "tma161_vs_tma512": [],
                     "skinny160_vs_fp64": [], "tma161_vs_fp64": []}
            err = {"skinny160": 0.0, "tma161": 0.0}
            for _ in range(BATCHES):
                rows = 512
                if kind == "embed":
                    ids = torch.randint(0, emb.shape[0], (rows,), generator=gen)
                    e = emb[ids].float()
                    x = e * torch.rsqrt(e.pow(2).mean(-1, keepdim=True) + 1e-5) * ln
                else:
                    x = torch.randn((rows, emb.shape[1]), generator=gen) * ln
                x = x.bfloat16().to(dev).contiguous()
                A = run(x[:160].contiguous(), w)
                B = run(x[:161].contiguous(), w)[:160]
                C = run(x[:100].contiguous(), w)
                D = run(x, w)[:160]
                ref = (x[:160].double() @ w.double().t())
                parts["skinny160_vs_tma161"].append(compare(A, B, bias))
                parts["skinny160_vs_skinny100"].append(compare(A[:100], C, bias))
                parts["tma161_vs_tma512"].append(compare(B, D, bias))
                parts["skinny160_vs_fp64"].append(compare(A, ref.float(), bias))
                parts["tma161_vs_fp64"].append(compare(B, ref.float(), bias))
                scale = ref.abs().max()
                err["skinny160"] = max(err["skinny160"], float((A.double() - ref).abs().max() / scale))
                err["tma161"] = max(err["tma161"], float((B.double() - ref).abs().max() / scale))
            cell = {"layer": L, "input": kind, **{k: merge(v) for k, v in parts.items()},
                    "max_abs_err_vs_fp64_rel_to_max_logit": err}
            report["cells"].append(cell)
            s = cell["skinny160_vs_tma161"]
            print(f"layer {L:2d} {kind:6s} skinny-vs-TMA: logits bit-equal {s['logits_bit_equal_frac']:.4f} "
                  f"max|d| {s['logit_max_abs_diff']:.2e} top8 changed {s['top8_set_changed_rows']}/{s['rows']} "
                  f"weight max|d| {s['weight_max_abs_diff_same_set']}  | skinny 160-vs-100 bit-equal "
                  f"{cell['skinny160_vs_skinny100']['logits_bit_equal_frac']:.4f}  TMA 161-vs-512 bit-equal "
                  f"{cell['tma161_vs_tma512']['logits_bit_equal_frac']:.4f}", flush=True)
            json.dump(report, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
