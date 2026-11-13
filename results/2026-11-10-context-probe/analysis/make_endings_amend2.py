#!/usr/bin/env python3
"""The counts of make_endings.py for the four passes of `k325-fp8` (amendment 2). Reads the saved reply texts (not
published) and the items; writes endings-amend2.csv in the columns of endings.csv (counts only, no text).

  make_endings_amend2.py <run folder> <out.csv>

Every definition is make_endings.py's: its `describe` is imported and called as it stands (that file is not edited;
amendment 2 names its sha256, f570a28d…, as the definitions fixed before this arm's data).
"""
import csv, glob, gzip, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_endings import describe


def main(run, out):
    rows = [r for r in csv.DictReader(open(f"{run}/analysis/samples-amend2.csv", newline="")) if r["cell"] == "single" and r["final"] == "1"]
    items, w = {}, None
    with open(out, "w", newline="") as fh:
        for r in rows:
            k = (r["item"], r["length"])
            if k not in items:
                items[k] = json.load(open(f"{run}/items/measured/{r['family']}/{r['item']}-{r['length']}.json"))
            g = glob.glob(f"{run}/tasks/{r['arm']}/m0/{r['pass']}/texts/{r['item']}-{r['length']}.*.json.gz")
            assert len(g) == 1, g
            t = json.load(gzip.open(g[0], "rt"))["turns"][0]
            assert len(t["reasoning"]) == int(r["reasoning_chars"]) and len(t["content"]) == int(r["content_chars"])
            row = {"arm": r["arm"], "pass": r["pass"], "item": r["item"], "family": r["family"], "length": r["length"],
                   "seed": r["seed"]}
            row.update(describe(items[k], t["reasoning"]))
            if w is None:
                w = csv.DictWriter(fh, fieldnames=list(row), lineterminator="\n")
                w.writeheader()
            w.writerow(row)
    print(len(rows), "rows")


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
