#!/usr/bin/env python3
"""P-B: a faithful float64 port of tpurtell's CuteAFD v3.0.1 fidelity rule for the published
glm5_flash-v2_20261005_bf16root set (64 windows x 512 scored positions, top-1024 + tail reference).

Source: <cuteafd> (v3.0.1-2-g603fce1). File:line below are relative to
rust/crates/cuteafd-bench/src unless stated. A dataset run (`cuteafd bench fidelity run`, dataset
backed) scores each window in two steps (fidelity_cli.rs:331-337):
  1. `Window::score` on the in-band probe rows (reference.rs:285-317) sets agree, confident, top3,
     agree_text, ref_nll, argmax, reference_argmax and a provisional kl/nll;
  2. `score_compact` on the full-vocabulary F32 dump (fidelity_rows.rs:163-198) recomputes kl and nll
     from the dump in f64 and requires the dump argmax to equal the in-band argmax.
The rule below is what those two steps leave in each record; the engine's in-band rows are not
needed because the dump carries everything.

Reference (per predicted position p; fidelity_dataset.rs:324-377, reference.rs:237-275):
  * 1024 f16 top log-probs and the f32 tail log-mass form one 1025-vector, renormalised by
    logsumexp in f64: lse = max + ln(sum exp(x - max))   (fidelity_dataset.rs:368-371,
    fidelity_rows.rs:108-116). top[i].lp and tail_lp are the renormalised values.
  * next_lp is the f32 next-token log-prob, NOT renormalised (fidelity_dataset.rs:362,371).
  * top order is the stored order; top[0] is the reference argmax (no id tie-break; reference.rs:306).
Engine row (the full-vocabulary row predicting p, = our row p-1):
  * f64 of the stored values, renormalised the same way (fidelity_rows.rs:176-177, 91-105).
  * argmax with ties to the lower id (fidelity_rows.rs:178-179; in-band: probe.rs:466-476).
Per position:
  kl  = sum_{t in top1024} exp(t.lp) (t.lp - e[t.id])
        + [tail_lp finite] exp(tail_lp) (tail_lp - LSE_{v not in top1024} e[v])   fidelity_rows.rs:181-191
        must be finite and >= -1e-10 (else error), then clamped at 0           fidelity_rows.rs:192-193
  nll = -e[next]                                                                 fidelity_rows.rs:194
  ref_nll = -next_lp                                                             reference.rs:309
  agree = argmax == top[0].id;  confident = exp(top[0].lp) >= 0.5;  top3_contained = argmax in top[0..3];
  agree_text = argmax == next                                                    reference.rs:306-310
Rows: all 512 positions per window are scored and recorded; gates and verdict use role == "gen" only
(fidelity.rs:194-213). Role is the window's role mask at p (reference.rs:306). Block and bucket are
the window's stored labels (reference.rs:305); bucket = bucket(score_from): 0-2K if <= 2048, 2-8K if
<= 8192, 8-16K if < 16384 (python/reference/fidelity_windows.py:383-384), checked here.
Aggregates: plain position means over the selected records; confident_top1 over confident records
(reference.rs:335-351). Intervals: window-block bootstrap of ratio-of-sums means, SplitMix64,
seed 20260829, 5,000 replicates (fidelity.rs:125-154, fidelity_cli.rs:47-50), windows in sorted-id
order like his BTreeMap (fidelity.rs:305).

Summation order: --sum-order rust (default) reproduces Rust's left-to-right f64 sums with cumsum, so
the port differs from his binary only by libm-vs-numpy exp/ln last-ulp effects.

Engine rows, per window (--engine DIR):
  layout files       DIR/<window_id>.safetensors (our vLLM plugin or glmf-teacher-kl.py); its rows must
                     include score_from-1 .. n-2 (a superset is fine).
  layout cuteafd-dump the CLI's own --dump-dir: DIR/window-%03d/ (full or quick tier) or
                     DIR/window-<path>-%03d/ (standard tier), index = the window's place in the tier's
                     window list (fidelity_cli.rs:295-299; list order: reference.rs:99-119,
                     fidelity_dataset.rs:46-56,69-78,107-108,135).

  score_pb.py score --engine DIR [--layout files|cuteafd-dump] [--cli-order full] --arm NAME --out OUT
  score_pb.py pair  --a OUT/pb-A.rows.npz --b OUT/pb-B.rows.npz --out OUT/pb-pair-A-B.json
This KL is tpurtell's coarse top-1024-plus-tail KL ("qualified-top1024-plus-tail"), a lower bound on
full-vocabulary KL: never put it next to P-A's full-vocabulary KL as the same quantity.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
from plans import PB_ROOT  # noqa: E402

# fidelity_dataset.rs:46, 69-78
QUICK_WINDOWS = ["legacy", "a00", "a04", "a08", "a20", "c00", "d00", "e00"]
STANDARD_DECODE = ["a00", "a01", "a04", "a05", "a08", "a09", "a10", "a12", "a17", "a19", "a21", "a24", "a25",
                   "b01", "b02", "b06", "b07", "b08", "b10", "c01", "c04", "c06", "c08", "c09",
                   "d01", "d02", "d04", "e00", "e02", "e05", "e06", "e07"]
STANDARD_PREFILL = ["a02", "a03", "a06", "a07", "a11", "a13", "a14", "a15", "a16", "a18", "a20", "a22", "a23",
                    "b00", "b03", "b04", "b05", "b09", "b11", "c00", "c02", "c03", "c05", "c07",
                    "d00", "d03", "d05", "e01", "e03", "e04", "e08", "legacy"]
MAX_TOKENS = 16384


def bucket(position: int) -> str:
    """python/reference/fidelity_windows.py:383-384."""
    return "0-2K" if position <= 2048 else "2-8K" if position <= 8192 else "8-16K" if position < MAX_TOKENS else "16K+"


def half_to_f64(bits: np.ndarray) -> np.ndarray:
    """IEEE half -> f64 (fidelity_rows.rs:80-89 is the exact IEEE decoding; numpy's float16 is the same)."""
    return np.asarray(bits, dtype=np.uint16).view(np.float16).astype(np.float64)


def normalize_rust(x: np.ndarray, rust_order: bool = True) -> np.ndarray:
    """fidelity_rows.rs:108-116 over the last axis: x - (max + ln(sum exp(x - max)))."""
    if np.isnan(x).any() or np.isposinf(x).any():
        raise ValueError("invalid log probability")
    m = x.max(axis=-1, keepdims=True)
    if not np.isfinite(m).all():
        raise ValueError("empty probability distribution")
    e = np.exp(x - m)
    s = np.cumsum(e, axis=-1)[..., -1:] if rust_order else e.sum(axis=-1, keepdims=True)
    return x - (m + np.log(s))


# --------------------------------------------------------------------------
# reference
# --------------------------------------------------------------------------

def load_reference(root: str = PB_ROOT, verify_hashes: bool = True) -> dict:
    """fidelity_dataset.rs:324-377 (+ Window::validate, reference.rs:237-275)."""
    man = json.load(open(os.path.join(root, "manifest.json")))
    if not (man["schema"] == "cuteafd.fidelity.dataset/1" and man["top_k"] == 1024
            and man["kind"] == "reference-top1024-plus-tail"):
        raise ValueError("unsupported dataset format")                           # :325-326
    for name, key in (("windows.json", "windows_sha256"), ("qualification.json", "qualification_sha256")):
        if C.sha256_file(os.path.join(root, name)) != man[key]:
            raise ValueError(f"dataset checksum differs: {name}")                 # :206-210
    panel = json.load(open(os.path.join(root, "windows.json")))
    qual = json.load(open(os.path.join(root, "qualification.json")))
    if not (panel["set_sha256"] == man["set_sha256"] == qual["set_sha256"] and qual["qualifies"] is True):
        raise ValueError("unqualified or mismatched dataset set")                 # :329-330
    vocab = int(man["vocab"])
    files = {e["window"]: e for e in man["files"]}
    if len(files) != len(panel["windows"]):
        raise ValueError("dataset window coverage differs")                       # :344
    windows = []
    for raw in panel["windows"]:
        e = files[raw["id"]]
        path = os.path.join(root, e["path"])
        if verify_hashes and C.sha256_file(path) != e["sha256"]:
            raise ValueError(f"dataset checksum differs: {e['path']}")            # :349
        if os.path.getsize(path) != e["bytes"]:
            raise ValueError("tensor byte length differs")                        # :350
        tokens = np.asarray(raw["tokens"], dtype=np.int64)
        roles = raw["roles"]
        s, n = raw["score_from"], len(raw["tokens"])
        k = n - s
        if k != 512 or e["shape"] != [k, 1024]:
            raise ValueError("dataset scored row count differs")                  # :353-354
        st = C.SafeTensors(path)
        want = {"positions": ("U32", [k]), "next_token_ids": ("U32", [k]), "roles": ("U8", [k]),
                "top_ids": ("U32", [k, 1024]), "top_log_probs": ("F16", [k, 1024]),
                "tail_log_mass": ("F32", [k]), "next_token_log_prob": ("F32", [k])}
        for name, (dt, shape) in want.items():
            t = st.tensors[name]
            if t["dtype"] != dt or t["shape"] != shape:
                raise ValueError(f"dataset tensor shape/dtype differs: {name}")    # :300-316
        pos = np.asarray(st.array("positions"), dtype=np.int64)
        nxt = np.asarray(st.array("next_token_ids"), dtype=np.int64)
        rl = np.asarray(st.array("roles"), dtype=np.int64)
        ids = np.asarray(st.array("top_ids"), dtype=np.int64)
        lps = half_to_f64(np.asarray(st.array("top_log_probs")).view(np.uint16))
        tails = np.asarray(st.array("tail_log_mass"), dtype=np.float64)
        next_lp = np.asarray(st.array("next_token_log_prob"), dtype=np.float64)
        if not (np.array_equal(pos, s + np.arange(k)) and np.array_equal(nxt, tokens[pos])
                and (rl <= 1).all() and np.array_equal(rl == 1, np.array([roles[p] == "gen" for p in pos]))):
            raise ValueError(f"{raw['id']}: tensor token/position/role differs")   # :364-367
        mass = normalize_rust(np.concatenate([lps, tails[:, None]], axis=1))      # :368-369
        top_lp, tail_lp = mass[:, :1024], mass[:, 1024]
        # Window::validate (reference.rs:238-273)
        if not (0 < s < n and len(roles) == n and all(r in ("gen", "ctx") for r in roles)
                and (tokens < vocab).all()):
            raise ValueError(f"{raw['id']}: invalid window")
        if not ((ids < vocab).all() and np.isfinite(top_lp).all() and (top_lp <= 0).all()
                and np.isfinite(next_lp).all() and (next_lp <= 0).all()
                and not np.isnan(tail_lp).any() and (tail_lp <= 0).all()):
            raise ValueError(f"{raw['id']}: invalid probabilities")
        if not all(len(set(r.tolist())) == 1024 for r in ids):
            raise ValueError(f"{raw['id']}: duplicate top ids")
        if not (np.diff(top_lp, axis=1) <= 0).all():
            raise ValueError(f"{raw['id']}: unsorted top-k")                      # reference.rs:271
        windows.append({"id": raw["id"], "block": raw["block"], "bucket": raw["bucket"],
                        "bucket_check": raw["bucket"] == bucket(s), "score_from": s, "n": n,
                        "tokens": tokens, "positions": pos, "next": nxt, "roles": [roles[p] for p in pos],
                        "top_ids": ids, "top_lp": top_lp, "tail_lp": tail_lp, "next_lp": next_lp,
                        "ref_top1_tie": top_lp[:, 0] == top_lp[:, 1]})
    return {"vocab": vocab, "manifest": man, "windows": windows, "set_sha256": man["set_sha256"],
            "expect": man["expect"], "root": root}


def cli_leaf(dump_dir: str, wid: str, order: str, all_ids: list) -> str:
    """fidelity_cli.rs:295-299 leaf naming; index into the tier's window list."""
    if order == "full":
        return os.path.join(dump_dir, f"window-{all_ids.index(wid):03d}")
    if order == "quick":
        q = [w for w in all_ids if w in QUICK_WINDOWS]
        return os.path.join(dump_dir, f"window-{q.index(wid):03d}")
    if order in ("standard-decode", "standard-prefill"):
        lst = STANDARD_DECODE if order == "standard-decode" else STANDARD_PREFILL
        return os.path.join(dump_dir, f"window-{order.split('-')[1]}-{lst.index(wid):03d}")
    raise ValueError(order)


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------

def score_rows(w: dict, values: np.ndarray, i0: int, rust_order: bool) -> dict:
    """Score positions w.positions[i0:i0+len(values)]; `values` are the engine rows (f64)."""
    b = values.shape[0]
    sl = slice(i0, i0 + b)
    if not np.isfinite(values).all():
        raise ValueError(f"{w['id']}: engine row with non-finite values (his CLI refuses: "
                         "fidelity_rows.rs:171, probe/rows.rs:36)")
    e = normalize_rust(values, rust_order)                                         # fidelity_rows.rs:177
    argmax = C.argmax_lowid(e)                                                     # :178-179
    ids = w["top_ids"][sl]
    tlp = w["top_lp"][sl]
    eq = np.take_along_axis(e, ids, axis=1)
    terms = np.exp(tlp) * (tlp - eq)
    kl = np.cumsum(terms, axis=1)[:, -1] if rust_order else terms.sum(axis=1)      # :183-186
    comp = e.copy()
    np.put_along_axis(comp, ids, -np.inf, axis=1)                                 # chosen ids excluded
    peak = comp.max(axis=1, keepdims=True)                                         # :187-188
    ex = np.exp(comp - peak)                                                       # exp(-inf) = 0 exactly
    s = np.cumsum(ex, axis=1)[:, -1] if rust_order else ex.sum(axis=1)
    tail = peak[:, 0] + np.log(s)                                                  # :189-190
    tl = w["tail_lp"][sl]
    fin = np.isfinite(tl)
    kl = kl + np.where(fin, np.exp(np.where(fin, tl, 0.0)) * (np.where(fin, tl, 0.0) - tail), 0.0)  # :191
    if not (np.isfinite(kl).all() and (kl >= -1e-10).all()):
        bad = np.flatnonzero(~(np.isfinite(kl) & (kl >= -1e-10)))
        raise ValueError(f"{w['id']}: invalid compact KL at positions {w['positions'][sl][bad][:5].tolist()}")
    raw_kl = kl.copy()
    kl = np.maximum(kl, 0.0)                                                       # :193
    nll = -e[np.arange(b), w["next"][sl]]                                          # :194
    top0 = ids[:, 0]
    return {"kl": kl, "kl_unclamped": raw_kl, "nll": nll, "argmax": argmax,
            "agree": argmax == top0, "confident": np.exp(tlp[:, 0]) >= 0.5,
            "top3": (ids[:, :3] == argmax[:, None]).any(axis=1), "agree_text": argmax == w["next"][sl],
            "align": C.alignment_nll(e, w["tokens"], w["positions"][sl] - 1)}


def score_window(args) -> dict:
    w, src, vocab, block, rust_order = args
    r = C.open_rows(src, vocab)
    meta_key = C.check_tokens_meta(r, w["tokens"]) if r.meta else None
    want_rows = w["positions"] - 1
    sel = C.select_rows(r, want_rows, exact=False)
    parts = []
    align = {-1: (0.0, 0), 0: (0.0, 0), 1: (0.0, 0)}
    for s in range(0, len(want_rows), block):
        e = min(s + block, len(want_rows))
        res = score_rows(w, r.take(sel[s:e]), s, rust_order)
        align = C.merge_alignment(align, res.pop("align"))
        parts.append(res)
    out = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    out["id"] = w["id"]
    out["align"] = C.alignment_verdict(align)
    out["source"] = {"path": r.path, "layout": r.layout, "dtype": r.dtype, "rows_source": r.rows_source,
                     "token_meta_checked": meta_key}
    return out


def build_rows(ref: dict, results: dict) -> dict:
    """Flatten to per-record arrays in windows.json order. Cluster codes follow sorted window ids."""
    order = sorted(w["id"] for w in ref["windows"])
    code = {wid: i for i, wid in enumerate(order)}
    cols = {k: [] for k in ("window", "cluster", "block", "bucket", "role", "position", "kl", "kl_unclamped", "nll",
                            "ref_nll", "argmax", "reference_argmax", "agree", "confident", "top3", "agree_text",
                            "ref_top1_tie")}
    for w in ref["windows"]:
        r = results[w["id"]]
        k = len(w["positions"])
        cols["window"] += [w["id"]] * k
        cols["cluster"].append(np.full(k, code[w["id"]]))
        cols["block"] += [w["block"]] * k
        cols["bucket"] += [w["bucket"]] * k
        cols["role"] += w["roles"]
        cols["position"].append(w["positions"])
        cols["ref_nll"].append(-w["next_lp"])
        cols["reference_argmax"].append(w["top_ids"][:, 0])
        cols["ref_top1_tie"].append(w["ref_top1_tie"])
        for key in ("kl", "kl_unclamped", "nll", "argmax", "agree", "confident", "top3", "agree_text"):
            cols[key].append(r[key])
    return {k: (np.array(v) if isinstance(v, list) and (not v or not isinstance(v[0], np.ndarray))
                else np.concatenate(v)) for k, v in cols.items()}


def metrics_from(d: dict) -> dict:
    one = np.ones(len(d["kl"]))
    conf = d["confident"].astype(float)
    return {"kl": (d["kl"], one), "nll": (d["nll"], one), "ref_nll": (d["ref_nll"], one),
            "dnll": (d["nll"] - d["ref_nll"], one), "top1": (d["agree"].astype(float), one),
            "confident_top1": ((d["agree"] & d["confident"]).astype(float), conf),
            "confident_fraction": (conf, one), "top3": (d["top3"].astype(float), one),
            "agree_text": (d["agree_text"].astype(float), one)}


def grouped(d: dict, spec: C.BootSpec, fn) -> dict:
    """fn(mask, with_ci) -> summary. gen primary, ctx separate, all for reference."""
    out = {}
    for role in ("gen", "ctx", "all"):
        rm = np.ones(len(d["kl"]), bool) if role == "all" else (d["role"] == role)
        if not rm.any():
            continue
        g = {"overall": fn(rm, True)}
        for dim in ("block", "bucket"):
            g[f"by_{dim}"] = {str(v): fn(rm & (d[dim] == v), True) for v in sorted(set(d[dim][rm].tolist()))}
        g["by_window"] = {str(v): fn(rm & (d["window"] == v), False) for v in sorted(set(d["window"][rm].tolist()))}
        out[role] = g
    return out


def summarize(d: dict, spec: C.BootSpec) -> dict:
    m = metrics_from(d)

    def fn(mask, ci):
        s = C.summarize_metrics(m, d["cluster"], mask, spec if ci else None)
        return s if ci else {k: (v["value"] if isinstance(v, dict) else v) for k, v in s.items()}
    return grouped(d, spec, fn)


def cuteafd_verdict(d: dict, expect: dict) -> dict:
    """fidelity.rs:194-213 on gen rows (informational: his absolute bars for this config)."""
    g = d["role"] == "gen"
    top1 = float(d["agree"][g].mean())
    kl = float(d["kl"][g].mean())
    conf = d["confident"][g]
    ctop1 = float((d["agree"][g] & conf).sum() / conf.sum()) if conf.any() else None
    top3 = float(d["top3"][g].mean())
    top1_min, kl_max = max(expect["top1_min"], 0.90), min(expect["kl_max"], 0.06)
    tw = expect.get("tripwires") or {"confident_top1_min": 0.98, "top3_min": 0.99}
    reasons = []
    if top1 + 1e-12 < top1_min:
        reasons.append("generated top-1 below expect/floor")
    if not math.isfinite(kl) or kl > kl_max:
        reasons.append("generated KL above expect/floor")
    if ctop1 is not None and ctop1 + 1e-12 < tw["confident_top1_min"]:
        reasons.append("confident top-1 below calibrated tripwire")
    if top3 + 1e-12 < tw["top3_min"]:
        reasons.append("top-3 below calibrated tripwire")
    low = [w for w in sorted(set(d["window"][g].tolist())) if d["agree"][g & (d["window"] == w)].mean() + 1e-12 < 0.80]
    if low:
        reasons.append("generated window top-1 below 80% floor")
    return {"pass": not reasons, "positions": int(g.sum()), "top1": top1, "kl": kl, "confident_top1": ctop1,
            "top3_contained": top3, "top1_min": top1_min, "kl_max": kl_max,
            "confident_top1_min": tw["confident_top1_min"], "top3_min": tw["top3_min"],
            "windows_below_80pct": low, "reasons": reasons}


def save_rows(path: str, d: dict) -> None:
    np.savez_compressed(path, **d)


def load_rows(path: str) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def records(d: dict) -> list:
    """Records in his Position field order (reference.rs:320-325)."""
    out = []
    for i in range(len(d["kl"])):
        out.append({"window": str(d["window"][i]), "block": str(d["block"][i]), "bucket": str(d["bucket"][i]),
                    "role": str(d["role"][i]), "position": int(d["position"][i]), "agree": bool(d["agree"][i]),
                    "confident": bool(d["confident"][i]), "top3_contained": bool(d["top3"][i]),
                    "agree_text": bool(d["agree_text"][i]), "finite": True, "kl": float(d["kl"][i]),
                    "nll": float(d["nll"][i]), "ref_nll": float(d["ref_nll"][i]), "argmax": int(d["argmax"][i]),
                    "reference_argmax": int(d["reference_argmax"][i])})
    return out


def cuteafd_compare(da: dict, db: dict, iters: int = 5000, seed: int = 20260829) -> dict:
    """fidelity.rs:269-333 + tripwire metric 350-370, A = baseline (his b), B = candidate (his a).
    Equals `cuteafd bench fidelity compare B.json A.json` when both are his run files."""
    g = da["role"] == "gen"
    wins = sorted(set(da["window"][g].tolist()))
    stats = np.zeros((len(wins), 2))
    counts = np.zeros(len(wins))
    wi = {w: i for i, w in enumerate(wins)}
    a_only = int((db["agree"][g] & ~da["agree"][g]).sum())      # candidate right, baseline wrong
    b_only = int((~db["agree"][g] & da["agree"][g]).sum())
    for j in np.flatnonzero(g):
        k = wi[da["window"][j]]
        stats[k, 0] += float(da["agree"][j]) - float(db["agree"][j])
        stats[k, 1] += db["kl"][j] - da["kl"][j]
        counts[k] += 1
    n = counts.sum()
    idx = C.bootstrap_indices(len(wins), iters, seed, "splitmix")
    reps = stats[idx].sum(axis=1) / counts[idx].sum(axis=1)[:, None]
    loss = (b_only - a_only) / n
    se = float(reps[:, 0].std(ddof=1))
    disc = a_only + b_only
    chi2 = (max(abs(a_only - b_only) - 1.0, 0.0) ** 2 / disc) if disc else 0.0

    def erfc(x):                                                    # fidelity.rs:156-163
        t = 1.0 / (1.0 + 0.5 * abs(x))
        v = t * math.exp(-x * x - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418
            + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587
            + t * (-0.82215223 + t * 0.17087277)))))))))
        return 2.0 - v if x < 0 else min(v, 1.0)

    def metric(confident_only: bool):
        ws, cnt, base, cand = {}, {}, 0, 0
        for j in np.flatnonzero(g):
            if confident_only and not da["confident"][j]:
                continue
            av, bv = (db["agree"][j], da["agree"][j]) if confident_only else (db["top3"][j], da["top3"][j])
            base += int(bv)
            cand += int(av)
            w = da["window"][j]
            ws[w] = ws.get(w, 0.0) + float(bv) - float(av)
            cnt[w] = cnt.get(w, 0) + 1
        if not ws:
            return None
        keys = sorted(ws)
        s = np.array([ws[k] for k in keys])
        c = np.array([cnt[k] for k in keys], dtype=float)
        ix = C.bootstrap_indices(len(keys), iters, seed, "splitmix")
        samp = s[ix].sum(axis=1) / c[ix].sum(axis=1)
        tot = c.sum()
        return {"baseline": base / tot, "candidate": cand / tot, "loss": (base - cand) / tot,
                "lower95": C.quantile_linear(samp, 0.05), "upper95": C.quantile_linear(samp, 0.95)}
    return {"note": "A = baseline, B = candidate; his one-sided statistics on gen rows",
            "positions": int(n), "windows": len(wins), "baseline_only": b_only, "candidate_only": a_only,
            "discordance": disc / n, "top1_loss": loss, "top1_upper95": loss + 1.6448536269514722 * se,
            "top1_se_bootstrap": se, "kl_delta": float(stats[:, 1].sum() / n),
            "kl_upper95": C.quantile_linear(reps[:, 1], 0.95),
            "kl_se_clustered": C.clustered_se(stats[:, 1], counts),
            "mcnemar_p": 1.0 if disc == 0 else erfc(math.sqrt(chi2 / 2.0)),
            "confident_top1": metric(True), "top3": metric(False), "bootstrap": iters, "seed": seed}


def paired(da: dict, db: dict, spec: C.BootSpec) -> dict:
    for k in ("window", "position", "role", "block", "bucket", "reference_argmax", "ref_nll", "confident", "cluster"):
        if not np.array_equal(da[k], db[k]):
            raise SystemExit(f"row metadata differ between arms: {k}")      # fidelity.rs:309-310
    ma, mb = metrics_from(da), metrics_from(db)

    def fn(mask, ci):
        if not ci:
            s = C.paired_metrics(ma, mb, da["cluster"], mask, None)
            return {k: (v["B_minus_A"] if isinstance(v, dict) else v) for k, v in s.items()}
        return C.paired_metrics(ma, mb, da["cluster"], mask, spec)
    out = grouped(da, spec, fn)
    out["cuteafd_compare"] = cuteafd_compare(da, db, spec.iters, spec.seed)
    out["engine_argmax_agreement_gen"] = float((da["argmax"] == db["argmax"])[da["role"] == "gen"].mean())
    return out


def cmd_score(a) -> int:
    t0 = time.time()
    ref = load_reference(a.reference, verify_hashes=not a.skip_hashes)
    ids = [w["id"] for w in ref["windows"]]
    wins = ref["windows"] if not a.windows else [w for w in ref["windows"] if w["id"] in set(a.windows.split(","))]
    layout = a.layout
    if layout == "auto":
        layout = "cuteafd-dump" if os.path.isdir(os.path.join(a.engine, "window-000")) or \
            os.path.isdir(os.path.join(a.engine, "window-decode-000")) or \
            os.path.isdir(os.path.join(a.engine, "window-prefill-000")) else "files"
    if layout == "cuteafd-dump" and a.cli_order.startswith("standard"):
        lst = STANDARD_DECODE if a.cli_order == "standard-decode" else STANDARD_PREFILL
        wins = [w for w in wins if w["id"] in lst]
    if layout == "cuteafd-dump" and a.cli_order == "quick":
        wins = [w for w in wins if w["id"] in QUICK_WINDOWS]
    srcs = {w["id"]: (cli_leaf(a.engine, w["id"], a.cli_order, ids) if layout == "cuteafd-dump"
                      else os.path.join(a.engine, f"{w['id']}.safetensors")) for w in wins}
    jobs = [(w, srcs[w["id"]], ref["vocab"], a.block, a.sum_order == "rust") for w in wins]
    if a.jobs == 1:
        res = {r["id"]: r for r in map(score_window, jobs)}
    else:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            res = {r["id"]: r for r in ex.map(score_window, jobs)}
    sub = dict(ref)
    sub["windows"] = wins
    d = build_rows(sub, res)
    spec = C.BootSpec(a.iters, a.seed, "splitmix")
    os.makedirs(a.out, exist_ok=True)
    save_rows(os.path.join(a.out, f"pb-{a.arm}.rows.npz"), d)
    with open(os.path.join(a.out, f"pb-{a.arm}.records.json"), "w") as f:
        json.dump(records(d), f)
    errors = [f"{wid}: alignment check failed {r['align']}" for wid, r in res.items() if not r["align"]["aligned"]]
    errors += [f"{w['id']}: bucket label {w['bucket']} != bucket(score_from={w['score_from']})"
               for w in wins if not w["bucket_check"]]
    summ = {"schema": "engine-compare.pb-score/1", "arm": a.arm, "engine": a.engine, "layout": layout,
            "cli_order": a.cli_order if layout == "cuteafd-dump" else None,
            "reference": {"root": ref["root"], "set_sha256": ref["set_sha256"],
                          "manifest_sha256": C.sha256_file(os.path.join(ref["root"], "manifest.json"))},
            "kl_kind": "qualified-top1024-plus-tail (tpurtell coarse KL; not full-vocabulary)",
            "sum_order": a.sum_order, "bootstrap": vars(spec), "windows": len(wins), "positions": int(len(d["kl"])),
            "reference_top1_ties": int(d["ref_top1_tie"].sum()),
            "clamped_negative_kl": int((d["kl_unclamped"] < 0).sum()),
            "min_unclamped_kl": float(d["kl_unclamped"].min()),
            "cuteafd_verdict_gen": cuteafd_verdict(d, ref["expect"]) if (d["role"] == "gen").any() else None,
            "summary": summarize(d, spec),
            "alignment": {wid: r["align"] for wid, r in res.items()},
            "sources": {wid: r["source"] for wid, r in res.items()},
            "errors": errors, "seconds": round(time.time() - t0, 1)}
    C.dump_json(os.path.join(a.out, f"pb-{a.arm}.json"), summ)
    gen = summ["summary"].get("gen", {}).get("overall")
    if gen:
        print(f"[pb] {a.arm}: gen rows {gen['rows']}  KL {gen['kl']['value']:.6g} {gen['kl']['ci95']}  "
              f"top1 {gen['top1']['value']:.5f}  conf-top1 {gen['confident_top1']['value']}  "
              f"top3 {gen['top3']['value']:.5f}  NLL {gen['nll']['value']:.5f}")
    if errors:
        print("ERRORS:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 2
    return 0


def cmd_pair(a) -> int:
    spec = C.BootSpec(a.iters, a.seed, "splitmix")
    res = paired(load_rows(a.a), load_rows(a.b), spec)
    res.update({"schema": "engine-compare.pb-paired/1", "A": a.a, "B": a.b, "bootstrap": vars(spec)})
    C.dump_json(a.out, res)
    g = res["gen"]["overall"]
    print(f"[pb] paired B-A gen: dKL {g['kl']['B_minus_A']:.6g} {g['kl']['ci95']}  "
          f"dtop1 {g['top1']['B_minus_A']:.5f} {g['top1']['ci95']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("--reference", default=PB_ROOT)
    s.add_argument("--engine", required=True)
    s.add_argument("--layout", choices=("auto", "files", "cuteafd-dump"), default="auto")
    s.add_argument("--cli-order", choices=("full", "quick", "standard-decode", "standard-prefill"), default="full")
    s.add_argument("--arm", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--windows", default="")
    s.add_argument("--jobs", type=int, default=8)
    s.add_argument("--block", type=int, default=128)
    s.add_argument("--sum-order", choices=("rust", "numpy"), default="rust")
    s.add_argument("--iters", type=int, default=5000)
    s.add_argument("--seed", type=int, default=20260829)
    s.add_argument("--skip-hashes", action="store_true", help="skip re-hashing the 64 reference files")
    p = sub.add_parser("pair")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--iters", type=int, default=5000)
    p.add_argument("--seed", type=int, default=20260829)
    a = ap.parse_args()
    return cmd_score(a) if a.cmd == "score" else cmd_pair(a)


if __name__ == "__main__":
    sys.exit(main())
