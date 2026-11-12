#!/usr/bin/env python3
"""Layer 1, exploratory: each arm's assistant-frame capture scored against the text itself (the given token), read
beside a reference arm. Reads the per-row capture files only (depth/<arm>/<tag>/*.json.gz), not the dumps.

  capture_abs.py --arms anchor/a0 hqa/a0 compact/a0 exlr8-k4/a0 [--n 4000] [--seed 20261110] [--out FILE]

Per path (prefill, decode): NLL of the given token and the share of rows whose most likely token is the given one;
the difference to the first-named arm with a 95% interval from resampling runs of consecutive scored positions
within each text (strata_boot.py's unit); top-1 = given by depth band; NLL by text; collapse rows (the arm gives the
given token p < 0.05 where every other arm gives p >= 0.9); and where a mean NLL difference comes from (per-row
difference to the first-named arm: sum, median, the rows that differ by more than 1 nat and what they sum to, the
mean with the top and bottom 1% of rows left out, the share of rows on which the arm is the better predictor, and
the same per text). Rows are matched on (text, file label, position), and the input ids must hash the same in every
arm.
"""
import argparse
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parents[1]
BANDS = (("1-4K", 0, 4096), ("4-16K", 4096, 16384), ("16-32K", 16384, 32768), ("32-64K", 32768, 65536),
         ("64-96K", 65536, 98304), ("96-128K", 98304, 1 << 30))


def band(p):
    return next(b for b, lo, hi in BANDS if lo <= p < hi)


def load(spec, path):
    arm, tag = spec.split("/")
    rows, ids = {}, {}
    for f in sorted((RUN / "depth" / arm / tag).glob(f"*.{path}*.json.gz")):
        d = json.load(gzip.open(f))
        text, label = d["meta"]["text"], d["meta"]["label"]
        ids[(text, label)] = d["meta"]["ids_sha256"]
        for r in d["rows"]:
            rows[(text, label, r["p"])] = (r["tok_lp"], r["argmax"] == r["tok"])
    return rows, ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--out")
    a = ap.parse_args()
    names = [s.split("/")[0] for s in a.arms]
    out = {"arms": a.arms, "interval": f"{a.n} resamples of runs of consecutive positions within each text, seed {a.seed}",
           "collapse_rule": "arm p < 0.05 and every other arm p >= 0.9"}
    for path in ("prefill", "decode"):
        L = [load(s, path) for s in a.arms]
        assert all(x[1] == L[0][1] for x in L), "input ids differ between arms"
        keys = sorted(set.intersection(*(set(x[0]) for x in L)))
        assert all(len(x[0]) == len(keys) for x in L), "row sets differ between arms"
        lp = np.array([[x[0][k][0] for k in keys] for x in L])           # arms x rows
        hit = np.array([[x[0][k][1] for k in keys] for x in L], float)
        cl, prev = [], None
        for k in keys:
            cl.append(cl[-1] if prev and prev[:2] == k[:2] and k[2] == prev[2] + 1 else (cl[-1] + 1 if cl else 0))
            prev = k
        cl = np.array(cl)
        nc = cl.max() + 1
        cnt = np.bincount(cl, minlength=nc).astype(float)
        snll = np.stack([np.bincount(cl, weights=-lp[i], minlength=nc) for i in range(len(L))])
        shit = np.stack([np.bincount(cl, weights=hit[i], minlength=nc) for i in range(len(L))])
        text_of = {}
        for c, k in zip(cl, keys):
            text_of[int(c)] = k[0]
        groups = {}
        for c, t in text_of.items():
            groups.setdefault(t, []).append(c)
        groups = [np.array(g) for g in groups.values()]
        rng = np.random.default_rng(a.seed)
        bn, bh = np.empty((a.n, len(L))), np.empty((a.n, len(L)))
        for b in range(a.n):
            pick = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups])
            n = cnt[pick].sum()
            bn[b], bh[b] = snll[:, pick].sum(1) / n, shit[:, pick].sum(1) / n
        res = {"rows": len(keys), "runs": int(nc), "arms": {}}
        print(f"\n=== {path} path, {len(keys)} rows in {nc} runs: each arm against the text itself (given token)")
        print("  arm        NLL mean   top-1=given   NLL - %s [95%%]              top-1 - %s [95%%]" % (names[0], names[0]))
        for i, nm in enumerate(names):
            dn, dh = bn[:, i] - bn[:, 0], bh[:, i] - bh[:, 0]
            e = {"nll": round(float(-lp[i].mean()), 4), "top1_given": round(float(hit[i].mean()), 4),
                 "nll_minus_ref": [round(float(lp[0].mean() - lp[i].mean()), 4)] + [round(float(v), 4) for v in np.percentile(dn, [2.5, 97.5])],
                 "top1_minus_ref": [round(float(hit[i].mean() - hit[0].mean()), 4)] + [round(float(v), 4) for v in np.percentile(dh, [2.5, 97.5])]}
            bands = np.array([band(k[2]) for k in keys])
            e["top1_given_by_band"] = {b: [round(float(hit[i][bands == b].mean()), 4), int((bands == b).sum())] for b, _, _ in BANDS if (bands == b).any()}
            e["nll_by_band"] = {b: round(float(-lp[i][bands == b].mean()), 4) for b, _, _ in BANDS if (bands == b).any()}
            texts = np.array([k[0] for k in keys])
            e["nll_by_text"] = {t: round(float(-lp[i][texts == t].mean()), 4) for t in sorted(set(texts))}
            others = np.delete(lp, i, axis=0)
            col = (lp[i] < math.log(0.05)) & (others >= math.log(0.9)).all(0)
            e["collapse_rows"] = {"n": int(col.sum()), "by_text": {t: int((col & (texts == t)).sum()) for t in sorted(set(texts)) if (col & (texts == t)).any()},
                                  "by_band": {b: int((col & (bands == b)).sum()) for b, _, _ in BANDS if (col & (bands == b)).any()}}
            if i:
                d = lp[0] - lp[i]                                        # per row: NLL(arm) - NLL(first-named arm)
                big = np.abs(d) > 1.0
                ds = np.sort(d); cut = int(0.01 * len(ds))
                e["nll_difference_rows"] = {
                    "sum": round(float(d.sum()), 2), "mean": round(float(d.mean()), 4), "median": round(float(np.median(d)), 6),
                    "rows_over_1_nat": int(big.sum()), "sum_of_those": round(float(d[big].sum()), 2),
                    "mean_without_those": round(float(d[~big].mean()), 5),
                    "mean_trimmed_1pct_each_side": round(float(ds[cut:len(ds) - cut].mean()), 5),
                    "share_rows_arm_better": round(float((d < 0).mean()), 4), "share_rows_equal": round(float((d == 0).mean()), 4),
                    "by_text": {t: {"rows": int((texts == t).sum()), "sum": round(float(d[texts == t].sum()), 2),
                                    "rows_over_1_nat": int((big & (texts == t)).sum()),
                                    "sum_of_those": round(float(d[big & (texts == t)].sum()), 2),
                                    "mean_without_those": round(float(d[~big & (texts == t)].mean()), 5)} for t in sorted(set(texts))}}
            res["arms"][nm] = e
            f = lambda m: f"{m[0]:+.4f} [{m[1]:+.4f}, {m[2]:+.4f}]"  # noqa: E731
            print(f"  {nm:10} {e['nll']:.4f}   {e['top1_given']:.4f}      {f(e['nll_minus_ref'])}   {f(e['top1_minus_ref'])}")
        for title, key, fmt in (("top-1 = given by depth band", "top1_given_by_band", lambda v: f"{v[0]:.3f}"),
                                ("NLL by depth band", "nll_by_band", lambda v: f"{v:.4f}"), ("NLL by text", "nll_by_text", lambda v: f"{v:.4f}")):
            print(f"  {title}:")
            for b in res["arms"][names[0]][key]:
                n = res["arms"][names[0]]["top1_given_by_band"].get(b, [0, 0])[1]
                print(f"    {b:8}" + (f" n={n:5}" if n else "       ") + "".join(f"  {nm} {fmt(res['arms'][nm][key][b])}" for nm in names))
        print("  collapse rows:", {nm: res["arms"][nm]["collapse_rows"] for nm in names})
        print(f"  where the NLL difference to {names[0]} comes from (per-row difference; rows over 1 nat):")
        for nm in names[1:]:
            h = res["arms"][nm]["nll_difference_rows"]
            print(f"    {nm:10} sum {h['sum']:+.2f} nat  median {h['median']:+.6f}  {h['rows_over_1_nat']} rows over 1 nat sum {h['sum_of_those']:+.2f}"
                  f"  trimmed mean {h['mean_trimmed_1pct_each_side']:+.5f}  arm better on {h['share_rows_arm_better']:.3f} of rows")
            print("       by text: " + "  ".join(f"{t} {v['sum']:+.2f} ({v['rows_over_1_nat']} rows {v['sum_of_those']:+.2f})" for t, v in h["by_text"].items()))
        out[path] = res
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
