#!/usr/bin/env python3
"""Layer 1, exploratory: the pair tables of drivers/depth_strata.py as one small JSON file. Standard library only.

  capture_pairs.py --arms anchor/a0 hqa/a0 compact/a0 exlr8-k4/a0 [--out FILE]

Reads the per-row output of depth_strata.py for the same arms (depth/compare/strata-<arms>.<path>.json, one line per
scored position; not published) and writes, for the prefill and the decode path, the statistics that driver prints:
per pair of arms the exact KL between the two next-token distributions (first-named arm as the reference
distribution; mean, median, 95th percentile, in nats) and the share of rows whose most likely token differs, over
all rows, per stratum (how sure the arms are of the given token: sure >= 0.9 in every arm, fair 0.5 to 0.9, unsure
< 0.5 in every arm, mixed when the arms straddle 0.5), and for the sure rows per depth band and per text.
"""
import argparse
import itertools
import json
import statistics as st
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parents[1]
BANDS = ("1-4K", "4-16K", "16-32K", "32-64K", "64-96K", "96-128K")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    names = [s.split("/")[0] for s in a.arms]
    pairs = [(i, j) for i, j in itertools.combinations(range(len(names)), 2)]
    out = {"arms": a.arms, "kl": "KL(first-named || second-named), nats, exact over the full vocabulary",
           "strata": "by the lowest probability any arm gives the given token: sure >= 0.9, fair 0.5 to 0.9, unsure < 0.5 in "
                     "every arm, mixed = the arms straddle 0.5"}
    for path in ("prefill", "decode"):
        src = RUN / "depth" / "compare" / f"strata-{'__'.join(s.replace('/', '-') for s in a.arms)}.{path}.json"
        rows = [json.loads(line) for line in open(src)]

        def table(sel):
            if not sel:
                return None
            t = {"rows": len(sel), "pairs": {}}
            for i, j in pairs:
                v = sorted(r["kl"][f"{i}|{j}"] for r in sel)
                t["pairs"][f"{names[i]} | {names[j]}"] = {
                    "kl_mean": round(st.fmean(v), 5), "kl_median": round(v[len(v) // 2], 6), "kl_p95": round(v[int(.95 * len(v))], 4),
                    "top1_differs": round(st.fmean(r["am"][i] != r["am"][j] for r in sel), 4)}
            return t

        res = {"rows": len(rows), "all": table(rows),
               "by_stratum": {s: table([r for r in rows if r["stratum"] == s]) for s in ("sure", "fair", "unsure", "mixed")},
               "sure_by_band": {b: table([r for r in rows if r["stratum"] == "sure" and r["band"] == b]) for b in BANDS},
               "sure_by_text": {t: table([r for r in rows if r["stratum"] == "sure" and r["t"] == t]) for t in sorted({r["t"] for r in rows})}}
        res["sure_by_band"] = {k: v for k, v in res["sure_by_band"].items() if v}
        out[path] = res
        print(f"\n=== {path} path, {len(rows)} rows")
        for title, t in [("all rows", res["all"])] + [(f"stratum {s}", v) for s, v in res["by_stratum"].items() if v]:
            print(f"  {title} (n = {t['rows']})")
            for k, v in t["pairs"].items():
                print(f"    {k:22} KL mean {v['kl_mean']:.5f} median {v['kl_median']:.6f} p95 {v['kl_p95']:.4f}  top-1 differs {v['top1_differs']:.4f}")
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
