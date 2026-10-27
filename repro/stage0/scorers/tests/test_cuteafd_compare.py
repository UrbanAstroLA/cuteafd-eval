#!/usr/bin/env python3
"""Cross-check score_pb.py's paired statistics (cuteafd_compare: SplitMix64 window-block bootstrap,
McNemar, calibrated tripwires) against tpurtell's own binary, `cuteafd bench fidelity compare`.

CPU only: the CuteAFD v3.0.1 release image runs with --network none, no GPU, only the compare
subcommand on two synthetic Run files. Synthetic records use the real P-B window/role/block/bucket
structure (64 windows, 32,768 positions) with random agree/top3/kl for two arms.

Run:  <venv>/bin/python -B tests/test_cuteafd_compare.py
Writes scorers/tests/cuteafd-compare-check.json; temporary files under scorers/_tmp_compare (removed).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True
import common as C  # noqa: E402
import score_pb as PB  # noqa: E402

IMAGE = "ghcr.io/tpurtell/cuteafd-coordinator@sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a"
TMP = os.path.join(ROOT, "_tmp_compare")


def synth(ref, seed, base=None):
    rng = np.random.default_rng(seed)
    d = PB.build_rows(ref, {w["id"]: {"kl": np.zeros(512), "kl_unclamped": np.zeros(512), "nll": np.zeros(512),
                                      "argmax": w["top_ids"][:, 0].copy(), "agree": np.ones(512, bool),
                                      "confident": np.exp(w["top_lp"][:, 0]) >= 0.5, "top3": np.ones(512, bool),
                                      "agree_text": np.ones(512, bool)} for w in ref["windows"]})
    n = len(d["kl"])
    p_miss = 0.04 + 0.04 * rng.random(n) if base is None else 0.05 + 0.03 * rng.random(n)
    d["agree"] = rng.random(n) > p_miss
    d["top3"] = d["agree"] | (rng.random(n) > 0.6)
    d["kl"] = rng.gamma(0.5, 0.04, size=n) if base is None else base["kl"] * rng.uniform(0.8, 1.4, size=n)
    d["kl_unclamped"] = d["kl"].copy()
    d["nll"] = rng.gamma(1.0, 0.5, size=n)
    d["argmax"] = np.where(d["agree"], d["reference_argmax"], d["reference_argmax"] + 1)
    d["agree_text"] = d["agree"]
    return d


def run_json(d, arm, ref):
    recs = PB.records(d)
    f = C  # noqa: F841
    n = len(recs)
    conf = [r for r in recs if r["confident"]]
    score = {"positions": n, "missing": 0, "non_finite": 0,
             "nll": float(np.mean(d["nll"])), "ref_nll": float(np.mean(d["ref_nll"])), "kl": float(np.mean(d["kl"])),
             "top1": float(np.mean(d["agree"])), "confident_positions": len(conf),
             "confident_top1": sum(r["agree"] for r in conf) / len(conf), "top3_contained": float(np.mean(d["top3"])),
             "agree_text": float(np.mean(d["agree_text"])), "records": recs}
    return {"schema": "cuteafd.fidelity.run/2", "arm": arm, "checkpoint": "zai-org/GLM-5.3-Flash",
            "set_sha256": ref["set_sha256"], "reference_sha256": "synthetic", "tier": "full",
            "path_shape": "prefill-shaped", "kl_kind": "full-vocabulary", "verify_rows": None,
            "engine": "synthetic", "settings": {}, "seconds": 0.0, "score": score,
            "floor_top1": ref["expect"]["top1_min"], "floor_kl": ref["expect"]["kl_max"],
            "tripwire_expect": ref["expect"]["tripwires"]}


def main() -> int:
    os.makedirs(TMP, exist_ok=True)
    try:
        ref = PB.load_reference(verify_hashes=False)
        A = synth(ref, 11)               # baseline
        B = synth(ref, 12, base=A)       # candidate
        json.dump(run_json(A, "baseline", ref), open(os.path.join(TMP, "A.json"), "w"))
        json.dump(run_json(B, "candidate", ref), open(os.path.join(TMP, "B.json"), "w"))
        ours = PB.cuteafd_compare(A, B, 5000, 20260829)
        cmd = ["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
               "-v", f"{TMP}:/w", "--entrypoint", "/opt/cuteafd/bin/cuteafd", IMAGE,
               "bench", "fidelity", "compare", "/w/B.json", "/w/A.json", "--score-path", "prefill",
               "--bootstrap", "5000", "--seed", "20260829", "--out", "/w/his.json"]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if not os.path.exists(os.path.join(TMP, "his.json")):
            print(p.stdout, p.stderr)
            return 1
        his = json.load(open(os.path.join(TMP, "his.json")))
        keys = ["positions", "windows", "baseline_only", "candidate_only", "discordance", "top1_loss", "top1_upper95",
                "top1_se_bootstrap", "kl_delta", "kl_upper95", "kl_se_clustered", "mcnemar_p"]
        cmp = {k: {"cuteafd": his[k], "port": ours[k], "abs_diff": abs(his[k] - ours[k])} for k in keys}
        for m, hk in (("confident_top1", "confident_top1"), ("top3", "top3")):
            for k in ("baseline", "candidate", "loss", "lower95", "upper95"):
                h = his["calibrated_tripwires"][hk][k]
                o = ours[m][k]
                cmp[f"{m}.{k}"] = {"cuteafd": h, "port": o, "abs_diff": abs(h - o)}
        worst = max(v["abs_diff"] for v in cmp.values())
        out = {"image": IMAGE, "command": " ".join(cmd), "exit_code": p.returncode, "compare": cmp,
               "max_abs_diff": worst, "pass": worst <= 1e-12}
        C.dump_json(os.path.join(HERE, "cuteafd-compare-check.json"), out)
        print(json.dumps({"max_abs_diff": worst, "pass": out["pass"],
                          "kl_delta": cmp["kl_delta"], "kl_upper95": cmp["kl_upper95"],
                          "top1_upper95": cmp["top1_upper95"]}, indent=1))
        return 0 if out["pass"] else 1
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
