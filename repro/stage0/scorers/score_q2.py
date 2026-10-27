#!/usr/bin/env python3
"""Q2: teacher-free comparison of two engines on the same long windows (32K / 64K / 128K).

There is no reference distribution, so nothing here says which engine is closer to BF16. It
measures (a) how well each engine predicts the actual human-written next tokens and (b) how much the
two engines disagree, read against (c) how much each engine disagrees with itself on a repeat.

Per row r (predicts tokens[r+1]); log p = float64 log-softmax of the stored full-vocabulary row:
  nll_A, nll_B   -log p(tokens[r+1]) per engine;  dnll = nll_B - nll_A (paired)
  kl_ab          KL(A || B) = sum_v p_A (log p_A - log p_B), all 154,880 ids
  kl_ba          KL(B || A)
  js             0.5 KL(A || M) + 0.5 KL(B || M), M = (p_A + p_B) / 2   (bounded by ln 2)
  top1_agree     argmax_A == argmax_B (ties -> lower id)
Noise floor (--a-repeat / --b-repeat, a second capture of the same engine; may cover a subset):
  the same pairwise quantities between A and A' (and B and B'), plus dnll = nll_A' - nll_A.
Groups: overall, per length bucket, per document type, per bucket x type, per window. Intervals:
bootstrap over documents (doc_id clusters; a document's windows move together), numpy default_rng,
20,000 replicates, seed 20260929. dnll uses the paired form (same resampled documents for A and B).

  score_q2.py --plans PLANDIR --a C1=DIR --b V1=DIR [--a-repeat DIR] [--b-repeat DIR] --out OUT
PLANDIR holds q2.vllm-registry.json and q2.meta.json from plans.py. NLL is per-tokenizer and per-text:
not comparable to P-A or P-B numbers, nor across model families.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

PAIR_KEYS = ("kl_ab", "kl_ba", "js", "top1_agree")


def pair_block(lpa: np.ndarray, lpb: np.ndarray) -> dict:
    return {"kl_ab": C.kl_from_logprobs(lpa, lpb), "kl_ba": C.kl_from_logprobs(lpb, lpa),
            "js": C.js_from_logprobs(lpa, lpb),
            "top1_agree": (C.argmax_lowid(lpa) == C.argmax_lowid(lpb)).astype(float)}


def score_window(args) -> dict:
    wid, tokens, rows, srcs, block = args
    tokens = np.asarray(tokens, dtype=np.int64)
    rows = np.asarray(rows, dtype=np.int64)
    nxt = tokens[rows + 1]
    eng, info = {}, {}
    for k, path in srcs.items():
        r = C.open_rows(path, C.VOCAB, rows)
        mk = C.check_tokens_meta(r, tokens) if r.meta else None
        eng[k] = (r, C.select_rows(r, rows, exact=False))
        info[k] = {"path": path, "dtype": r.dtype, "layout": r.layout, "rows_source": r.rows_source,
                   "token_meta_checked": mk}
    n = len(rows)
    out = {"window_id": wid, "sources": info, "nonfinite": {k: 0 for k in srcs}}
    for k in srcs:
        out[f"nll_{k}"] = np.empty(n)
    pairs = [("A", "B")] + [(x, x + "2") for x in ("A", "B") if x + "2" in srcs]
    for p in pairs:
        for key in PAIR_KEYS:
            out[f"{key}_{p[0]}{p[1]}"] = np.empty(n)
    align = {k: {-1: (0.0, 0), 0: (0.0, 0), 1: (0.0, 0)} for k in srcs}
    for s in range(0, n, block):
        e = min(s + block, n)
        lp = {}
        for k, (r, sel) in eng.items():
            z = r.take(sel[s:e])
            out["nonfinite"][k] += int((~np.isfinite(z)).any(axis=-1).sum())
            lp[k] = C.log_softmax_f64(z)
            out[f"nll_{k}"][s:e] = -lp[k][np.arange(e - s), nxt[s:e]]
            align[k] = C.merge_alignment(align[k], C.alignment_nll(lp[k], tokens, rows[s:e]))
        for x, y in pairs:
            res = pair_block(lp[x], lp[y])
            for key in PAIR_KEYS:
                out[f"{key}_{x}{y}"][s:e] = res[key]
    out["align"] = {k: C.alignment_verdict(v) for k, v in align.items()}
    return out


def group_masks(meta_rows: dict) -> dict:
    """name -> mask over rows."""
    n = len(meta_rows["doc_type"])
    g = {"overall": np.ones(n, bool)}
    for b in sorted(set(meta_rows["length_bucket"].tolist()), key=lambda s: (len(s), s)):
        g[f"length={b}"] = meta_rows["length_bucket"] == b
    for t in sorted(set(meta_rows["doc_type"].tolist())):
        g[f"type={t}"] = meta_rows["doc_type"] == t
    for b in sorted(set(meta_rows["length_bucket"].tolist()), key=lambda s: (len(s), s)):
        for t in sorted(set(meta_rows["doc_type"].tolist())):
            m = (meta_rows["length_bucket"] == b) & (meta_rows["doc_type"] == t)
            if m.any():
                g[f"length={b},type={t}"] = m
    return g


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plans", required=True, help="dir with q2.vllm-registry.json and q2.meta.json")
    ap.add_argument("--panel", default="q2")
    ap.add_argument("--a", required=True, help="NAME=DIR of <window_id>.safetensors")
    ap.add_argument("--b", required=True, help="NAME=DIR")
    ap.add_argument("--a-repeat", help="DIR: second capture of engine A (any subset of windows)")
    ap.add_argument("--b-repeat", help="DIR: second capture of engine B")
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20260929)
    a = ap.parse_args()
    t0 = time.time()
    reg = json.load(open(os.path.join(a.plans, f"{a.panel}.vllm-registry.json")))
    meta = {w["window_id"]: w for w in json.load(open(os.path.join(a.plans, f"{a.panel}.meta.json")))["windows"]}
    na, da = a.a.split("=", 1)
    nb, db = a.b.split("=", 1)
    jobs = []
    for w in reg["windows"]:
        wid = w["window_id"]
        srcs = {"A": os.path.join(da, f"{wid}.safetensors"), "B": os.path.join(db, f"{wid}.safetensors")}
        for key, d in (("A2", a.a_repeat), ("B2", a.b_repeat)):
            if d and os.path.exists(os.path.join(d, f"{wid}.safetensors")):
                srcs[key] = os.path.join(d, f"{wid}.safetensors")
        jobs.append((wid, w["tokens"], w["rows"], srcs, a.block))
    if a.jobs == 1:
        results = list(map(score_window, jobs))
    else:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            results = list(ex.map(score_window, jobs))
    # flatten
    docs = sorted({meta[r["window_id"]]["doc_id"] for r in results})
    dcode = {d: i for i, d in enumerate(docs)}
    m_rows = {"window": [], "doc": [], "doc_type": [], "length_bucket": []}
    keys = sorted({k for r in results for k, v in r.items() if isinstance(v, np.ndarray)})
    cols: dict = {k: [] for k in keys}
    for r in results:
        m = meta[r["window_id"]]
        n = len(r["nll_A"])
        m_rows["window"] += [r["window_id"]] * n
        m_rows["doc"].append(np.full(n, dcode[m["doc_id"]]))
        m_rows["doc_type"] += [m["doc_type"]] * n
        m_rows["length_bucket"] += [m["length_bucket"]] * n
        for k in keys:
            cols[k].append(r[k] if k in r else np.full(n, np.nan))   # NaN = no repeat for this window
    m_rows = {k: (np.concatenate(v) if k == "doc" else np.array(v)) for k, v in m_rows.items()}
    cols = {k: np.concatenate(v) for k, v in cols.items()}
    spec = C.BootSpec(a.iters, a.seed, "numpy")
    groups = group_masks(m_rows)
    one = np.ones(len(m_rows["window"]))
    out = {"schema": "engine-compare.q2-score/1", "A": na, "B": nb, "A_dir": da, "B_dir": db,
           "A_repeat": a.a_repeat, "B_repeat": a.b_repeat, "bootstrap": vars(spec), "cluster": "doc_id",
           "documents": docs, "rows": int(len(one)), "windows": len(results), "groups": {}, "per_window": {},
           "not_a_result": "which engine is closer to BF16 beyond 14K (no teacher here)"}
    for gname, gm in groups.items():
        g = {}
        g["nll_paired"] = C.paired_metrics({"nll": (cols["nll_A"], one)}, {"nll": (cols["nll_B"], one)},
                                           m_rows["doc"], gm, spec)["nll"]
        g["between_engines"] = C.summarize_metrics({k: (cols[f"{k}_AB"], one) for k in PAIR_KEYS},
                                                   m_rows["doc"], gm, spec)
        for x in ("A", "B"):
            key = f"kl_ab_{x}{x}2"
            if key in cols:
                rm = gm & np.isfinite(cols[key])
                if rm.any():
                    fl = C.summarize_metrics({k: (np.nan_to_num(cols[f"{k}_{x}{x}2"]), one) for k in PAIR_KEYS},
                                             m_rows["doc"], rm, spec)
                    fl["dnll_repeat"] = C.paired_metrics({"nll": (np.nan_to_num(cols[f"nll_{x}"]), one)},
                                                         {"nll": (np.nan_to_num(cols.get(f"nll_{x}2", cols[f"nll_{x}"])), one)},
                                                         m_rows["doc"], rm, spec)["nll"]
                    fl["between_engines_same_rows"] = {k: C.summarize_metrics({k: (cols[f"{k}_AB"], one)},
                                                                              m_rows["doc"], rm, None)[k]["value"]
                                                       for k in PAIR_KEYS}
                    g[f"noise_floor_{x}"] = fl
        out["groups"][gname] = g
    for r in results:
        wm = m_rows["window"] == r["window_id"]
        out["per_window"][r["window_id"]] = {
            "doc_id": meta[r["window_id"]]["doc_id"], "doc_type": meta[r["window_id"]]["doc_type"],
            "length_bucket": meta[r["window_id"]]["length_bucket"], "rows": int(wm.sum()),
            "nll_A": float(cols["nll_A"][wm].mean()), "nll_B": float(cols["nll_B"][wm].mean()),
            **{k: float(cols[f"{k}_AB"][wm].mean()) for k in PAIR_KEYS},
            **{f"{k}_{x}{x}2": float(cols[f"{k}_{x}{x}2"][wm].mean()) for x in ("A", "B") for k in PAIR_KEYS
               if f"{k}_{x}{x}2" in cols and np.isfinite(cols[f"{k}_{x}{x}2"][wm]).all()},
            "alignment": r["align"], "sources": r["sources"], "nonfinite_rows": r["nonfinite"]}
    errors = [f"{r['window_id']} {k}: alignment check failed {v}" for r in results for k, v in r["align"].items()
              if not v["aligned"]]
    errors += [f"{r['window_id']} {k}: {v} non-finite rows" for r in results for k, v in r["nonfinite"].items() if v]
    out["errors"] = errors
    out["seconds"] = round(time.time() - t0, 1)
    os.makedirs(a.out, exist_ok=True)
    C.dump_json(os.path.join(a.out, f"q2-{na}-vs-{nb}.json"), out)
    np.savez_compressed(os.path.join(a.out, f"q2-{na}-vs-{nb}.rows.npz"), **m_rows, **cols)
    o = out["groups"]["overall"]
    print(f"[q2] {nb} - {na}: dNLL {o['nll_paired']['B_minus_A']:.5f} {o['nll_paired']['ci95']}  "
          f"KL(A||B) {o['between_engines']['kl_ab']['value']:.5g}  JS {o['between_engines']['js']['value']:.5g}  "
          f"top1 agree {o['between_engines']['top1_agree']['value']:.5f}")
    if errors:
        print("ERRORS:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
