#!/usr/bin/env python3
"""Are K4's BF16 core tensors byte-identical to the BF16 core file (zai-org/GLM-5.3-Flash-BF16 @ f9fed3bb, ranged copy)?
sha256 of each tensor's raw bytes in both, with dtype and shape. Standard library only; reads ~30 GiB.
    python3 hash_core.py <core.safetensors> <K4 snapshot dir> <out.json>"""
import hashlib, json, os, struct, sys

def header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return 8 + n, json.loads(f.read(n))

def digest(path, base, off):
    h = hashlib.sha256(); a, b = off; left = b - a
    with open(path, "rb") as f:
        f.seek(base + a)
        while left:
            chunk = f.read(min(left, 64 << 20)); h.update(chunk); left -= len(chunk)
    return h.hexdigest()

core, snap, out = sys.argv[1:4]
cb, ch = header(core)
idx = json.load(open(os.path.join(snap, "model.safetensors.index.json")))["weight_map"]
heads = {}
res = {}
for name in sorted(k for k in ch if k != "__metadata__"):
    shard = os.path.join(snap, idx[name])
    if shard not in heads: heads[shard] = header(shard)
    kb, kh = heads[shard]
    a, b = ch[name], kh[name]
    same_meta = a["dtype"] == b["dtype"] and a["shape"] == b["shape"]
    da = digest(core, cb, a["data_offsets"]); db = digest(shard, kb, b["data_offsets"]) if same_meta else None
    res[name] = {"dtype": a["dtype"], "shape": a["shape"], "k4_dtype": b["dtype"], "k4_shape": b["shape"],
                 "sha256_core": da, "sha256_k4": db, "identical": da == db}
    print(name, res[name]["identical"], flush=True)
s = {"tensors": len(res), "identical": sum(v["identical"] for v in res.values()),
     "differ": sorted(k for k, v in res.items() if not v["identical"])}
json.dump({"summary": s, "per_tensor": res}, open(out, "w"), indent=1)
print(json.dumps(s))
