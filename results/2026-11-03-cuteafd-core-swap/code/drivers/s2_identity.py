#!/usr/bin/env python3
"""Cross-launch bit-identity of CuteAFD scoring: compare the per-row FNV hashes of the raw logits (probe receipts) of two
launches of the same checkpoint. Standard library only.  s2_identity.py <dumps>/runs/C-K6 <dumps>/runs/C-K6r2"""
import glob, json, os, sys
a, b = sys.argv[1:3]
tr = rows = same_rows = same_tr = 0; differ = []
for f in sorted(glob.glob(os.path.join(a, "*", "*.receipt.json"))):
    g = os.path.join(b, os.path.relpath(f, a))
    if not os.path.exists(g):
        continue
    x, y = json.load(open(f))["row_hashes"], json.load(open(g))["row_hashes"]
    n = sum(p == q for p, q in zip(x, y)); tr += 1; rows += len(x); same_rows += n
    if n == len(x) == len(y): same_tr += 1
    else: differ.append({"trace": os.path.basename(f)[:-len(".receipt.json")], "rows": len(x), "identical_rows": n})
print(json.dumps({"traces": tr, "traces_bit_identical": same_tr, "rows": rows, "rows_bit_identical": same_rows,
                  "differing_traces": differ}, indent=1))
