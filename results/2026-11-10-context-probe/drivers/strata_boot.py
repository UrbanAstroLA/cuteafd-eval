#!/usr/bin/env python3
"""Layer 1, exploratory: bootstrap intervals for the tables depth_strata.py prints (PROTOCOL-DRAFT section 11a).

  strata_boot.py depth/compare/strata-<...>.json [--names anchor core-fp8 hqa] [--n 4000] [--seed 20261110]

The resampling unit is a run of consecutive scored positions in one text (a 32-row window or a single row), drawn
within each text, so rows of one window stay together. Prints, for all rows and per stratum, each pair's mean KL
and top-1-differs rate with a 95% interval, and the difference between every two pairs' mean KL on the same
resamples (an interval that excludes 0 separates the two pairs). Five texts is too few to resample texts.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys

import numpy as np

sys.dont_write_bytecode = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20261110)
    a = ap.parse_args()
    rows = [json.loads(line) for line in open(a.file)]
    rows.sort(key=lambda r: (r["t"], r["p"]))
    pairs = list(rows[0]["kl"])
    names = a.names or [str(i) for i in range(len(rows[0]["lp"]))]
    label = lambda k: "|".join(names[int(x)] for x in k.split("|"))  # noqa: E731
    cl, prev = [], None                      # cluster index per row
    for r in rows:
        if prev is None or r["t"] != prev["t"] or r["p"] != prev["p"] + 1:
            cl.append((cl[-1] + 1) if cl else 0)
        else:
            cl.append(cl[-1])
        prev = r
    cl = np.array(cl)
    text_of = {}
    for c, r in zip(cl, rows):
        text_of[int(c)] = r["t"]
    rng = np.random.default_rng(a.seed)

    def block(title, mask):
        idx = np.flatnonzero(mask)
        if len(idx) < 20:
            return
        cs = np.unique(cl[idx])
        # per cluster: row count and per-pair sums of KL and of top-1 differences
        pos = {int(c): i for i, c in enumerate(cs)}
        cnt = np.zeros(len(cs))
        skl = np.zeros((len(cs), len(pairs)))
        sfl = np.zeros((len(cs), len(pairs)))
        for i in idx:
            r, c = rows[i], pos[int(cl[i])]
            cnt[c] += 1
            for j, k in enumerate(pairs):
                x, y = (int(v) for v in k.split("|"))
                skl[c, j] += r["kl"][k]
                sfl[c, j] += r["am"][x] != r["am"][y]
        groups = {}
        for c, i in pos.items():
            groups.setdefault(text_of[c], []).append(i)
        groups = [np.array(g) for g in groups.values()]
        mk, mf = np.empty((a.n, len(pairs))), np.empty((a.n, len(pairs)))
        for b in range(a.n):
            pick = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups])
            n = cnt[pick].sum()
            mk[b], mf[b] = skl[pick].sum(0) / n, sfl[pick].sum(0) / n
        ci = lambda v: tuple(np.percentile(v, [2.5, 97.5]))  # noqa: E731
        print(f"\n{title}: {len(idx)} rows in {len(cs)} runs")
        for j, k in enumerate(pairs):
            lo, hi = ci(mk[:, j])
            flo, fhi = ci(mf[:, j])
            print(f"  {label(k):34} KL mean {skl[:, j].sum() / cnt.sum():.5f} [{lo:.5f}, {hi:.5f}]"
                  f"   top-1 differs {sfl[:, j].sum() / cnt.sum():.4f} [{flo:.4f}, {fhi:.4f}]")
        for i, j in itertools.combinations(range(len(pairs)), 2):
            d = mk[:, i] - mk[:, j]
            lo, hi = ci(d)
            mark = "" if lo <= 0 <= hi else "  *"
            print(f"    ({label(pairs[i])}) - ({label(pairs[j])}): {(skl[:, i].sum() - skl[:, j].sum()) / cnt.sum():+.5f}"
                  f" [{lo:+.5f}, {hi:+.5f}]{mark}")

    st = np.array([r["stratum"] for r in rows])
    block("all rows", np.ones(len(rows), bool))
    for s in ("sure", "fair", "unsure", "mixed"):
        block(f"stratum {s}", st == s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
