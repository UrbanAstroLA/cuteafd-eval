#!/usr/bin/env python3
"""Cross-check the registry against the source data (host, numpy only).

P-B: for every window, registered rows + 1 == reference `positions`
     (= score_from .. n-1), tokens[rows+1] == reference `next_token_ids`,
     and roles in windows.json == reference `roles` (ctx=0, gen=1).
P-A: registered tokens == panel .npy tokens, rows == 0..2046, and the .npy
     file hash == dataset-manifest token_ids_sha256.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "plugin"))
from glm53_capture_plugin import core  # noqa: E402

REG = os.path.join(HERE, "registry")
PB = "<datasets>/2026-10-26-engine-compare/cuteafd-fidelity/glm5_flash-v2_20261005_bf16root"


def main():
    bad = 0
    wj = {w["id"]: w for w in json.load(open(os.path.join(PB, "windows.json")))["windows"]}
    gen = 0
    for p in sorted(os.listdir(os.path.join(REG, "pb"))):
        if not p.endswith(".json") or p.startswith("."):
            continue
        e, toks = core.load_entry(os.path.join(REG, "pb", p), REG, keep_tokens=True)
        ref, _ = core.read_safetensors(os.path.join(PB, f"{e.window_id}.safetensors"))
        pos = ref["positions"].astype(np.int64)
        roles = np.array([{"ctx": 0, "gen": 1}[r] for r in wj[e.window_id]["roles"]])
        ok = (np.array_equal(e.rows.astype(np.int64) + 1, pos)
              and np.array_equal(toks[e.rows.astype(np.int64) + 1], ref["next_token_ids"].astype(np.int64))
              and np.array_equal(roles[pos], ref["roles"].astype(np.int64))
              and np.array_equal(toks, np.asarray(wj[e.window_id]["tokens"])))
        gen += int((ref["roles"] == 1).sum())
        if not ok:
            bad += 1
            print("P-B MISMATCH", e.window_id)
    print(f"P-B: 64 windows checked against reference safetensors, {bad} mismatches, "
          f"{gen} gen rows")
    man = json.load(open("<datasets>/glm53-flash-teacher-logits/dataset-manifest.json"))
    pa_bad = 0
    for m in man["logit_files"]:
        e, toks = core.load_entry(os.path.join(REG, "pa", f"{m['window_id']}.json"), REG,
                                  keep_tokens=True)
        npy = np.load(f"<runs>/kld/panel-final/{m['window_id']}.tokens.npy").astype(np.int64)
        if not (np.array_equal(toks, npy) and np.array_equal(e.rows, np.arange(2047))
                and e.meta.get("npy_sha256") == m["token_ids_sha256"]):
            pa_bad += 1
            print("P-A MISMATCH", m["window_id"])
    print(f"P-A: 25 windows checked against panel + dataset manifest, {pa_bad} mismatches")
    sys.exit(1 if bad or pa_bad else 0)


if __name__ == "__main__":
    main()
