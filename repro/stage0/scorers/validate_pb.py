#!/usr/bin/env python3
"""Validate the P-B port (score_pb.py) against tpurtell's own CLI on the GPU day.

Plan (CuteAFD C1, one launch with ENABLE_BENCH=on, API_KEY_FILE, PROBE_DUMP_ROOT, FULL_PREFILL_LOGITS=on):
  1. cuteafd bench fidelity run --tier full --score-path prefill --arm C1 \
       --dataset-config glm5_flash-v2_20261005_bf16root --dataset-revision a7e7d1b4d82329acebe54ca88dc71d47d0d2056d \
       --dump-dir <ROOT>/pb-cli-prefill --out <ROOT>/pb-cli-prefill.json
     The CLI never deletes its dumps (fidelity_cli.rs:295-342), so <ROOT>/pb-cli-prefill/window-%03d/ keeps
     all 64 x 512 full-vocabulary F32 rows it scored.
  2. score_pb.py score --engine <ROOT>/pb-cli-prefill --layout cuteafd-dump --cli-order full --arm C1-cli ...
  3. validate_pb.py records --cli <ROOT>/pb-cli-prefill.json --port OUT/pb-C1-cli.records.json --mode same-dump

Mode same-dump (step 3: both scorers read the same bytes). Expected:
  * identical record keys (window, position), 32,768 of them;
  * identical role, block, bucket, reference_argmax, ref_nll, confident (reference side);
  * identical argmax, agree, top3_contained, agree_text (engine side; same rows, same tie rule);
  * |kl_port - kl_cli| and |nll_port - nll_cli| <= 1e-10 nat per position (expected ~1e-15..1e-13: the port
    uses the same f64 operations in the same left-to-right order; only exp/ln may differ in the last ulp
    between Rust's libm and numpy, and serde_json writes f64 that round-trip exactly);
  * aggregate means equal to <= 1e-12.
Mode separate-capture (rows captured in another request, e.g. glmf-teacher-kl.py or a second CLI run): the
engine itself may differ, so nothing is asserted; the report gives the distribution of differences.

`rows` compares two captures of engine rows (e.g. the CLI dump vs glmf-teacher-kl.py output of the same
engine) row by row: bit-identical fraction, max |delta log p|, KL both ways, argmax agreement.

Mapping his CLI output, fully determined from source:
  * --out JSON for --tier full is a `Run` (schema cuteafd.fidelity.run/2, fidelity.rs:8-35); for --tier standard
    it is a panel record whose "decode"/"prefill" keys hold the Runs (panels/fidelity.rs:73-93). Records are
    run.score.records[], fields window, block, bucket, role, position, agree, confident, top3_contained,
    agree_text, finite, kl, nll, ref_nll, argmax, reference_argmax (reference.rs:320-325); position is the
    predicted position p (our row p-1).
  * --dump-dir DIR: leaf DIR/window-%03d (full/quick) or DIR/window-<path>-%03d (standard), index into the tier's
    window list (fidelity_cli.rs:295-299); each leaf holds manifest.jsonl lines {position, vocab_size, file,
    tensor:"log_probs", dtype:"F32", byte_order:"little"} and row-%08d.safetensors files with one F32 [154880]
    tensor `log_probs` = (f64(logit) - lse) as f32 (probe/rows.rs:59-86, probe.rs:446-456).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import score_pb as PB  # noqa: E402

REF_FIELDS = ("role", "block", "bucket", "reference_argmax", "ref_nll", "confident")
ENGINE_BOOL = ("argmax", "agree", "top3_contained", "agree_text")


def load_cli(path: str, score_path: str) -> dict:
    v = json.load(open(path))
    if v.get("schema") != "cuteafd.fidelity.run/2":
        v = v[score_path]
    if v.get("schema") != "cuteafd.fidelity.run/2":
        raise SystemExit("not a cuteafd.fidelity.run/2 file")
    return v


def stats(x: np.ndarray) -> dict:
    a = np.abs(x)
    return {"max_abs": float(a.max()), "mean_abs": float(a.mean()), "p99_abs": float(np.quantile(a, 0.99)),
            "mean_signed": float(x.mean())}


def cmd_records(a) -> int:
    run = load_cli(a.cli, a.score_path)
    his = {(r["window"], r["position"]): r for r in run["score"]["records"]}
    port_list = json.load(open(a.port))
    ours = {(r["window"], r["position"]): r for r in port_list}
    rep = {"cli": a.cli, "port": a.port, "mode": a.mode, "tol": a.tol,
           "cli_meta": {k: run.get(k) for k in ("arm", "checkpoint", "tier", "path_shape", "kl_kind", "set_sha256",
                                                 "engine", "verify_rows", "seconds")},
           "cli_missing": run["score"].get("missing"), "cli_non_finite": run["score"].get("non_finite")}
    only_his = sorted(set(his) - set(ours))
    only_ours = sorted(set(ours) - set(his))
    rep["records"] = {"cli": len(his), "port": len(ours), "common": len(set(his) & set(ours)),
                      "cli_only": only_his[:10], "port_only": only_ours[:10]}
    keys = sorted(set(his) & set(ours))
    fails = []
    if only_his or only_ours:
        fails.append("record key sets differ")
    mism = {}
    for f in REF_FIELDS + ENGINE_BOOL:
        bad = [k for k in keys if his[k][f] != ours[k][f]]
        mism[f] = {"count": len(bad), "examples": [list(k) for k in bad[:5]]}
    rep["field_mismatches"] = mism
    dkl = np.array([ours[k]["kl"] - his[k]["kl"] for k in keys])
    dnll = np.array([ours[k]["nll"] - his[k]["nll"] for k in keys])
    rep["kl_diff"] = stats(dkl)
    rep["nll_diff"] = stats(dnll)
    agg = {}
    for name, fn in (("kl", lambda r: r["kl"]), ("nll", lambda r: r["nll"]), ("ref_nll", lambda r: r["ref_nll"]),
                     ("top1", lambda r: float(r["agree"])), ("top3_contained", lambda r: float(r["top3_contained"])),
                     ("agree_text", lambda r: float(r["agree_text"]))):
        for role in ("all", "gen"):
            ks = [k for k in keys if role == "all" or his[k]["role"] == role]
            h = float(np.mean([fn(his[k]) for k in ks]))
            o = float(np.mean([fn(ours[k]) for k in ks]))
            agg[f"{name}[{role}]"] = {"cli": h, "port": o, "diff": o - h}
    agg["cli_score_fields"] = {k: run["score"].get(k) for k in ("positions", "kl", "top1", "nll", "ref_nll",
                                                                 "confident_top1", "top3_contained", "agree_text")}
    rep["aggregates"] = agg
    if a.mode == "same-dump":
        for f in REF_FIELDS + ENGINE_BOOL:
            if mism[f]["count"]:
                fails.append(f"{f}: {mism[f]['count']} mismatches")
        if rep["kl_diff"]["max_abs"] > a.tol:
            fails.append(f"kl max |diff| {rep['kl_diff']['max_abs']:.3g} > {a.tol}")
        if rep["nll_diff"]["max_abs"] > a.tol:
            fails.append(f"nll max |diff| {rep['nll_diff']['max_abs']:.3g} > {a.tol}")
        for k, v in agg.items():
            if isinstance(v, dict) and "diff" in v and abs(v["diff"]) > 1e-12:
                fails.append(f"aggregate {k} differs by {v['diff']:.3g}")
        sc = run["score"]
        if abs(sc["kl"] - agg["kl[all]"]["port"]) > 1e-12 or abs(sc["top1"] - agg["top1[all]"]["port"]) > 1e-12:
            fails.append("port aggregate differs from the CLI's score.kl/top1")
    else:
        for f in REF_FIELDS:
            if mism[f]["count"]:
                fails.append(f"reference field {f}: {mism[f]['count']} mismatches (same reference expected)")
    rep["pass"] = not fails
    rep["failures"] = fails
    C.dump_json(a.out, rep)
    print(json.dumps({k: rep[k] for k in ("records", "kl_diff", "nll_diff", "pass", "failures")}, indent=1))
    return 0 if rep["pass"] else 3


def _source(path: str, wid: str, order: str, ids: list) -> str:
    if os.path.isdir(os.path.join(path, "window-000")) or order != "files":
        if order == "files":
            order = "full"
        return PB.cli_leaf(path, wid, order, ids)
    return os.path.join(path, f"{wid}.safetensors")


def cmd_rows(a) -> int:
    ref = PB.load_reference(a.reference, verify_hashes=False)
    ids = [w["id"] for w in ref["windows"]]
    wins = [w for w in ref["windows"] if not a.windows or w["id"] in set(a.windows.split(","))]
    from score_q2 import pair_block
    per = {}
    tot = {"rows": 0, "bit_identical": 0}
    agg = {k: [] for k in ("kl_ab", "kl_ba", "js", "top1_agree", "max_abs_dlogp")}
    for w in wins:
        ra = C.open_rows(_source(a.a, w["id"], a.a_order, ids), ref["vocab"])
        rb = C.open_rows(_source(a.b, w["id"], a.b_order, ids), ref["vocab"])
        want = w["positions"] - 1
        sa, sb = C.select_rows(ra, want, exact=False), C.select_rows(rb, want, exact=False)
        res = {k: [] for k in agg}
        bit = 0
        for s in range(0, len(want), a.block):
            e = min(s + a.block, len(want))
            xa, xb = ra.take(sa[s:e]), rb.take(sb[s:e])
            bit += int((xa == xb).all(axis=1).sum())
            la, lb = C.log_softmax_f64(xa), C.log_softmax_f64(xb)
            pr = pair_block(la, lb)
            for k in ("kl_ab", "kl_ba", "js", "top1_agree"):
                res[k].append(pr[k])
            res["max_abs_dlogp"].append(np.abs(la - lb).max(axis=1))
        res = {k: np.concatenate(v) for k, v in res.items()}
        per[w["id"]] = {"rows": len(want), "bit_identical_rows": bit,
                        **{k: float(v.mean()) for k, v in res.items() if k != "max_abs_dlogp"},
                        "max_abs_dlogp": float(res["max_abs_dlogp"].max())}
        tot["rows"] += len(want)
        tot["bit_identical"] += bit
        for k in agg:
            agg[k].append(res[k])
    agg = {k: float(np.concatenate(v).mean()) if k != "max_abs_dlogp" else float(np.concatenate(v).max())
           for k, v in agg.items()}
    rep = {"a": a.a, "b": a.b, "totals": tot, "means": agg, "per_window": per}
    C.dump_json(a.out, rep)
    print(json.dumps({"totals": tot, "means": agg}, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("records")
    r.add_argument("--cli", required=True, help="the CLI's --out JSON")
    r.add_argument("--score-path", default="prefill", help="for standard-tier panel records")
    r.add_argument("--port", required=True, help="score_pb.py pb-<arm>.records.json")
    r.add_argument("--mode", choices=("same-dump", "separate-capture"), default="same-dump")
    r.add_argument("--tol", type=float, default=1e-10)
    r.add_argument("--out", required=True)
    w = sub.add_parser("rows")
    w.add_argument("--reference", default=PB.PB_ROOT)
    w.add_argument("--a", required=True)
    w.add_argument("--b", required=True)
    w.add_argument("--a-order", default="files", help="files | full | quick | standard-decode | standard-prefill")
    w.add_argument("--b-order", default="files")
    w.add_argument("--windows", default="")
    w.add_argument("--block", type=int, default=128)
    w.add_argument("--out", required=True)
    a = ap.parse_args()
    return cmd_records(a) if a.cmd == "records" else cmd_rows(a)


if __name__ == "__main__":
    sys.exit(main())
