#!/usr/bin/env python3
"""P-A: score engine rows against the brandonmusic BF16 teacher (25 x 2,047 rows, full vocabulary, fp64).

Per row r of window w (row r predicts tokens[r+1]; teacher row i = logits/window-%04d row i):
  kl          = sum_v p_t(v) (log p_t(v) - log p_e(v))      KL(teacher || engine), all 154,880 ids
  nll         = -log p_e(tokens[r+1])                        engine NLL of the actual next token
  teacher_nll = -log p_t(tokens[r+1])
  dnll        = nll - teacher_nll
  top1        = argmax p_e == argmax p_t                     ties -> lower id, both sides
  confident   = max p_t >= 0.5;  confident_top1 = top1 over confident rows only
  top3        = argmax p_e in the teacher's top 3            teacher top 3 ordered by (-p, id)
  agree_text  = argmax p_e == tokens[r+1]
log p is the float64 log-softmax of the stored row (teacher F32 logits; engine logits or log-probs in
F32/BF16/F16), exactly kld_score.py:58-90. Aggregates are position-weighted means (ratio of sums);
95% intervals resample windows with replacement (kld_score.py:138-178: numpy default_rng, 20,000
replicates, seed 20260929). Paired mode resamples the same windows for both arms and reports B - A.

Engine rows per arm directory: <window_id>.safetensors (glmf-teacher-kl.py or our plugin), or the
legacy plugin's window-%04d.safetensors (single `logits` tensor, rows 0..2046 implied by its count).
The teacher's own logits directory is a valid arm: KL must be 0 and nll == teacher_nll exactly.

  score_pa.py score --arm C1=/path/rows --arm V1=/path/rows --out OUT [--jobs 6]
  score_pa.py pair  --a OUT/pa-C1.rows.npz --b OUT/pa-V1.rows.npz --out OUT/pa-pair-C1-V1.json
NLL and KL here are per-tokenizer, per-panel numbers: not comparable with P-B, Q2 or other model families.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
from plans import build_pa, TEACHER  # noqa: E402

ROWS = 2047


def engine_file(d: str, wid: str, i: int) -> str:
    for name in (f"{wid}.safetensors", f"window-{i:04d}.safetensors"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"{d}: neither {wid}.safetensors nor window-{i:04d}.safetensors")


def score_window(args) -> dict:
    i, wid, tokens, teacher_dir, arms, block = args
    tokens = np.asarray(tokens, dtype=np.int64)
    rows = np.arange(ROWS, dtype=np.int64)
    nxt = tokens[rows + 1]
    teacher = C.WindowRows(os.path.join(teacher_dir, f"window-{i:04d}.safetensors"), C.VOCAB, rows)
    t_sel = C.select_rows(teacher, rows)
    eng = {}
    for name, d in arms.items():
        r = C.open_rows(engine_file(d, wid, i), C.VOCAB, rows)
        meta_key = C.check_tokens_meta(r, tokens) if hasattr(r, "meta") else None
        eng[name] = (r, C.select_rows(r, rows), meta_key)
    T = {k: np.empty(ROWS) for k in ("teacher_nll", "teacher_p1")}
    T["teacher_argmax"] = np.empty(ROWS, dtype=np.int64)
    T["teacher_top1_tie"] = np.zeros(ROWS, dtype=bool)
    A = {n: {"kl": np.empty(ROWS), "nll": np.empty(ROWS), "argmax": np.empty(ROWS, dtype=np.int64),
             "top3": np.zeros(ROWS, dtype=bool), "nonfinite": 0} for n in arms}
    align = {n: {-1: (0.0, 0), 0: (0.0, 0), 1: (0.0, 0)} for n in list(arms) + ["__teacher__"]}
    for s in range(0, ROWS, block):
        e = min(s + block, ROWS)
        sl = np.arange(s, e)
        lpt = C.log_softmax_f64(teacher.take(t_sel[s:e]))
        pt = np.exp(lpt)
        ta = C.argmax_lowid(lpt)
        top2 = np.partition(lpt, -2, axis=-1)[:, -2:]
        T["teacher_top1_tie"][s:e] = top2[:, 0] == top2[:, 1]
        T["teacher_argmax"][s:e] = ta
        T["teacher_p1"][s:e] = np.exp(lpt[np.arange(e - s), ta])
        T["teacher_nll"][s:e] = -lpt[np.arange(e - s), nxt[s:e]]
        top3 = C.top3_lowid(lpt)
        align["__teacher__"] = C.merge_alignment(align["__teacher__"], C.alignment_nll(lpt, tokens, sl))
        for n, (r, sel, _) in eng.items():
            z = r.take(sel[s:e])
            A[n]["nonfinite"] += int((~np.isfinite(z)).any(axis=-1).sum())
            lpc = C.log_softmax_f64(z)
            A[n]["kl"][s:e] = (pt * (lpt - lpc)).sum(axis=-1)       # == kl_rows_f64(zt, zc), same ops
            A[n]["nll"][s:e] = -lpc[np.arange(e - s), nxt[s:e]]
            ea = C.argmax_lowid(lpc)
            A[n]["argmax"][s:e] = ea
            A[n]["top3"][s:e] = (top3 == ea[:, None]).any(axis=-1)
            align[n] = C.merge_alignment(align[n], C.alignment_nll(lpc, tokens, sl))
    return {"i": i, "window_id": wid, "next": nxt, "T": T, "A": A,
            "align": {n: C.alignment_verdict(v) for n, v in align.items()},
            "sources": {n: {"path": r.path, "layout": r.layout, "dtype": r.dtype, "rows_source": r.rows_source,
                            "values_tensor": getattr(r, "values_name", "log_probs"), "token_meta_checked": mk}
                        for n, (r, _, mk) in eng.items()}}


def metrics_from(d: dict) -> dict:
    """name -> (numerator, denominator) per row."""
    one = np.ones_like(d["kl"])
    conf = d["teacher_p1"] >= 0.5
    agree = d["argmax"] == d["teacher_argmax"]
    return {"kl": (d["kl"], one), "nll": (d["nll"], one), "teacher_nll": (d["teacher_nll"], one),
            "dnll": (d["nll"] - d["teacher_nll"], one), "top1": (agree.astype(float), one),
            "confident_top1": ((agree & conf).astype(float), conf.astype(float)),
            "confident_fraction": (conf.astype(float), one), "top3": (d["top3"].astype(float), one),
            "agree_text": ((d["argmax"] == d["next"]).astype(float), one)}


def summarize(d: dict, spec: C.BootSpec) -> dict:
    m = metrics_from(d)
    cl = d["window_index"]
    out = {"overall": C.summarize_metrics(m, cl, np.ones(len(cl), bool), spec)}
    per = {}
    for g, wid in enumerate(d["window_ids"]):
        s = C.summarize_metrics(m, cl, cl == g, None)
        per[str(wid)] = {k: (v["value"] if isinstance(v, dict) else v) for k, v in s.items()}
    out["per_window"] = per
    return out


def save_rows(path: str, d: dict) -> None:
    np.savez_compressed(path, **{k: (np.asarray(v) if not isinstance(v, list) else np.array(v)) for k, v in d.items()})


def load_rows(path: str) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def paired(da: dict, db: dict, spec: C.BootSpec) -> dict:
    for k in ("window_ids", "window_index", "row", "next", "teacher_argmax", "teacher_p1", "teacher_nll"):
        if not np.array_equal(da[k], db[k]):
            raise SystemExit(f"paired arms differ in {k}: not the same panel rows/teacher")
    ma, mb = metrics_from(da), metrics_from(db)
    cl = da["window_index"]
    out = {"overall": C.paired_metrics(ma, mb, cl, np.ones(len(cl), bool), spec)}
    agree_a = da["argmax"] == da["teacher_argmax"]
    agree_b = db["argmax"] == db["teacher_argmax"]
    out["top1_discordance"] = {"A_only": int((agree_a & ~agree_b).sum()), "B_only": int((~agree_a & agree_b).sum()),
                               "engine_argmax_agreement": float((da["argmax"] == db["argmax"]).mean())}
    return out


def cmd_score(a) -> int:
    windows, meta = build_pa(a.teacher)
    if a.windows:
        keep = set(a.windows.split(","))
        windows = [w for w in windows if w["window_id"] in keep]
    arms = dict(x.split("=", 1) for x in a.arm)
    os.makedirs(a.out, exist_ok=True)
    spec = C.BootSpec(a.iters, a.seed, "numpy")
    jobs = [(int(w["window_id"].split("-")[1]), w["window_id"], w["tokens"], os.path.join(a.teacher, "logits"),
             arms, a.block) for w in windows]
    t0 = time.time()
    if a.jobs == 1:
        results = list(map(score_window, jobs))
    else:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            results = list(ex.map(score_window, jobs))
    results.sort(key=lambda r: r["i"])
    bad = []
    data = {}
    for n in arms:
        d = {"window_ids": np.array([r["window_id"] for r in results]),
             "window_index": np.concatenate([np.full(ROWS, g) for g in range(len(results))]),
             "row": np.concatenate([np.arange(ROWS)] * len(results)),
             "next": np.concatenate([r["next"] for r in results])}
        for k in ("teacher_nll", "teacher_p1", "teacher_argmax", "teacher_top1_tie"):
            d[k] = np.concatenate([r["T"][k] for r in results])
        for k in ("kl", "nll", "argmax", "top3"):
            d[k] = np.concatenate([r["A"][n][k] for r in results])
        nonfinite = sum(r["A"][n]["nonfinite"] for r in results)
        if nonfinite or not np.isfinite(d["kl"]).all():
            bad.append(f"{n}: {nonfinite} rows with non-finite values")
        for r in results:
            for who in (n, "__teacher__"):
                if not r["align"][who]["aligned"]:
                    bad.append(f"{who} window {r['window_id']}: alignment check failed {r['align'][who]}")
        data[n] = d
        save_rows(os.path.join(a.out, f"pa-{n}.rows.npz"), d)
        summ = summarize(d, spec)
        summ.update({"schema": "engine-compare.pa-score/1", "arm": n, "engine_dir": arms[n],
                     "teacher": a.teacher, "panel": meta, "windows": len(results), "rows": int(len(d["kl"])),
                     "teacher_top1_ties": int(d["teacher_top1_tie"].sum()),
                     "estimator": "full_vocabulary_fp64 KL(teacher||engine), nats; kld_score.py:58-90",
                     "bootstrap": vars(spec), "sources": {r["window_id"]: r["sources"][n] for r in results},
                     "alignment": {r["window_id"]: {"engine": r["align"][n], "teacher": r["align"]["__teacher__"]}
                                   for r in results},
                     "errors": [b for b in bad if b.startswith(n) or b.startswith("__teacher__")],
                     "seconds": round(time.time() - t0, 1)})
        C.dump_json(os.path.join(a.out, f"pa-{n}.json"), summ)
        o = summ["overall"]
        print(f"[pa] {n}: rows {o['rows']}  KL {o['kl']['value']:.9g} {o['kl']['ci95']}  NLL {o['nll']['value']:.6f} "
              f"(teacher {o['teacher_nll']['value']:.6f})  top1 {o['top1']['value']:.5f}  conf-top1 "
              f"{o['confident_top1']['value']:.5f}  top3 {o['top3']['value']:.5f}")
    pairs = [p.split(",") for p in a.pair] if a.pair else (list(itertools.combinations(arms, 2)) if len(arms) > 1 else [])
    for pa_, pb_ in pairs:
        res = paired(data[pa_], data[pb_], spec)
        res.update({"schema": "engine-compare.pa-paired/1", "A": pa_, "B": pb_, "bootstrap": vars(spec)})
        C.dump_json(os.path.join(a.out, f"pa-pair-{pa_}-vs-{pb_}.json"), res)
        k = res["overall"]["kl"]
        print(f"[pa] paired {pb_} - {pa_}: dKL {k['B_minus_A']:.6g} {k['ci95']}")
    if bad:
        print("ERRORS:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 2
    return 0


def cmd_pair(a) -> int:
    spec = C.BootSpec(a.iters, a.seed, "numpy")
    res = paired(load_rows(a.a), load_rows(a.b), spec)
    res.update({"schema": "engine-compare.pa-paired/1", "A": a.a, "B": a.b, "bootstrap": vars(spec)})
    C.dump_json(a.out, res)
    print(json.dumps(res["overall"]["kl"], indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("--teacher", default=TEACHER)
    s.add_argument("--arm", action="append", required=True, help="NAME=DIR (repeatable)")
    s.add_argument("--pair", action="append", help="A,B (default: every pair of arms, in order)")
    s.add_argument("--out", required=True)
    s.add_argument("--windows", default="", help="comma list of window ids (default all 25)")
    s.add_argument("--jobs", type=int, default=6)
    s.add_argument("--block", type=int, default=128)
    s.add_argument("--iters", type=int, default=20000)
    s.add_argument("--seed", type=int, default=20260929)
    p = sub.add_parser("pair")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--iters", type=int, default=20000)
    p.add_argument("--seed", type=int, default=20260929)
    a = ap.parse_args()
    return cmd_score(a) if a.cmd == "score" else cmd_pair(a)


if __name__ == "__main__":
    sys.exit(main())
