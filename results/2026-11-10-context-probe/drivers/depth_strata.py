#!/usr/bin/env python3
"""Layer 1, exploratory reading: exact KL between every pair of N arm-captures on the same rows, split by how
sure the model is of the given token (PROTOCOL-DRAFT section 11). Standard library and numpy.

  depth_strata.py --arms anchor/a0 core-fp8/a0 hqa/a0 --path prefill [--workers 12]
  depth_strata.py --arms anchor/a0:prefill anchor/a0:decode hqa/a0:prefill      (a `:path` suffix overrides --path:
                                                    the two paths of one launch, on the positions both recorded)

Each row's full-vocabulary dump is read once per arm. Strata use the lowest probability any of the arms gives the
given token: sure (>= 0.9), fair (0.5 to 0.9), unsure (< 0.5 in every arm), mixed (the arms straddle 0.5).
Output: depth/compare/strata-<arms>.<path>.json (one line per row) and a printed table per stratum and depth band.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics as st
import sys
from multiprocessing import Pool
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import depth_profile as D  # noqa: E402
import probelib as P  # noqa: E402


def one(job):
    import numpy as np
    text, label, p, files = job
    lps = [P.read_logprob_row(f) for f in files]
    kl = {}
    for i, j in itertools.combinations(range(len(lps)), 2):
        pa = np.exp(lps[i])
        keep = pa > 0
        kl[f"{i}|{j}"] = float(np.sum(pa[keep] * (lps[i][keep] - lps[j][keep])))
    return text, label, p, kl


def stratum(probs) -> str:
    lo, hi = min(probs), max(probs)
    return "sure" if lo >= 0.9 else "fair" if lo >= 0.5 else "unsure" if hi < 0.5 else "mixed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--path", default="prefill", choices=["prefill", "decode"])
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    caps = []                                      # per capture: {(text, position): (row, dump file)}
    for spec in a.arms:
        tag, _, path = spec.partition(":")
        flat, ids = {}, {}
        for (text, _label), cap in D.load_rows(tag, path or a.path).items():
            dump = P.dump_index(cap["meta"].get("dump"))
            ids.setdefault(text, set()).add(cap["meta"]["ids_sha256"])
            flat.update({(text, p): (r, dump[p]) for p, r in cap["rows"].items() if p in dump})
        caps.append((flat, ids))
    for text in set.intersection(*(set(i) for _, i in caps)):
        if len(set.union(*(i[text] for _, i in caps))) != 1:
            sys.exit(f"{text}: the captures did not score the same token ids")
    jobs, info = [], {}
    for text, p in sorted(set.intersection(*(set(f) for f, _ in caps))):
        jobs.append((text, "", p, [str(f[(text, p)][1]) for f, _ in caps]))
        info[(text, "", p)] = [f[(text, p)][0] for f, _ in caps]
    print(f"{len(jobs)} rows, {len(a.arms)} arms, path {a.path}", flush=True)
    with Pool(a.workers) as pool:
        res = pool.map(one, jobs, chunksize=64)
    pairs = [f"{i}|{j}" for i, j in itertools.combinations(range(len(a.arms)), 2)]
    name = lambda k: " | ".join(a.arms[int(x)] for x in k.split("|"))  # noqa: E731
    out = []
    for text, label, p, kl in res:
        rows = info[(text, label, p)]
        probs = [math.exp(r["tok_lp"]) for r in rows]
        out.append({"t": text, "p": p, "band": D.band_of(p), "stratum": stratum(probs), "kl": kl,
                    "lp": [r["tok_lp"] for r in rows], "am": [r["argmax"] for r in rows],
                    "heq": {k: rows[int(k[0])]["hash"] == rows[int(k[-1])]["hash"] for k in pairs}})
    dest = D.OUT / "compare" / f"strata-{'__'.join(t.replace('/', '-').replace(':', '-') for t in a.arms)}.{a.path}.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in out) + "\n")

    def table(title, rows):
        if not rows:
            return
        print(f"\n{title} (n = {len(rows)})")
        for k in pairs:
            v = sorted(r["kl"][k] for r in rows)
            i, j = (int(x) for x in k.split("|"))
            flip = st.fmean(r["am"][i] != r["am"][j] for r in rows)
            print(f"  {name(k):28} KL mean {st.fmean(v):.5f} median {v[len(v) // 2]:.6f} p95 {v[int(.95 * len(v))]:.4f}"
                  f"  top-1 differs {flip:.4f}  hash-equal {st.fmean(r['heq'][k] for r in rows):.3f}")

    table("all rows", out)
    for s in ("sure", "fair", "unsure", "mixed"):
        table(f"stratum {s}", [r for r in out if r["stratum"] == s])
    for b in [f"{lo // 1024}-{hi // 1024}K" for lo, hi in D.BANDS]:
        table(f"sure rows, depth {b}", [r for r in out if r["stratum"] == "sure" and r["band"] == b])
    for t in sorted({r["t"] for r in out}):
        table(f"sure rows, text {t}", [r for r in out if r["stratum"] == "sure" and r["t"] == t])
    return 0


if __name__ == "__main__":
    sys.exit(main())
