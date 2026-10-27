#!/usr/bin/env python3
"""Compare a local safetensors snapshot with a Core-FP8 stitch-provenance.json.

For every tensor the stitch took from "base", hash the raw tensor bytes in the
local snapshot and compare with the recorded SHA256. Also report base tensors
the stitch dropped and fp8 tensors it added. Read-only; CPU and disk only.
Usage: bytecheck.py SNAPSHOT_DIR PROVENANCE_JSON OUT_JSON [WORKERS]
"""
import hashlib, json, os, struct, sys
from concurrent.futures import ProcessPoolExecutor

def header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        h = json.loads(f.read(n))
    h.pop("__metadata__", None)
    return 8 + n, h

def hash_shard(path):
    base, h = header(path)
    out = {}
    with open(path, "rb") as f:
        for name, t in sorted(h.items(), key=lambda kv: kv[1]["data_offsets"][0]):
            a, b = t["data_offsets"]
            f.seek(base + a)
            m, left = hashlib.sha256(), b - a
            while left:
                chunk = f.read(min(left, 64 << 20))
                if not chunk:
                    raise IOError("short read in %s at %s" % (path, name))
                m.update(chunk); left -= len(chunk)
            out[name] = {"sha256": m.hexdigest(), "bytes": b - a, "dtype": t["dtype"],
                         "shape": t["shape"], "file": os.path.basename(path)}
    return out

def main():
    snap, prov_path, out_path = sys.argv[1:4]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    prov = json.load(open(prov_path))["tensors"]
    shards = sorted(os.path.join(snap, f) for f in os.listdir(snap) if f.endswith(".safetensors"))
    local = {}
    with ProcessPoolExecutor(workers) as ex:
        for part in ex.map(hash_shard, shards):
            local.update(part)
    base_keep = {k: v for k, v in prov.items() if v["source"] == "base"}
    fp8_added = sorted(k for k, v in prov.items() if v["source"] == "fp8")
    match = [k for k in base_keep if k in local and local[k]["sha256"] == base_keep[k]["sha256"]]
    mismatch = [k for k in base_keep if k in local and local[k]["sha256"] != base_keep[k]["sha256"]]
    missing_local = [k for k in base_keep if k not in local]
    dropped = sorted(k for k in local if k not in prov)
    fp8_name_in_local = [k for k in fp8_added if k in local]
    def nbytes(keys): return sum(local[k]["bytes"] for k in keys if k in local)
    report = {
        "snapshot": snap, "provenance": prov_path, "shards_hashed": len(shards),
        "local_tensors": len(local), "local_tensor_bytes": sum(v["bytes"] for v in local.values()),
        "stitch_tensors": len(prov), "stitch_from_base": len(base_keep), "stitch_from_fp8": len(fp8_added),
        "base_identical": len(match), "base_identical_bytes": nbytes(match),
        "base_mismatch": mismatch, "base_missing_locally": missing_local,
        "local_not_in_stitch_count": len(dropped), "local_not_in_stitch_bytes": nbytes(dropped),
        "local_not_in_stitch": [{"name": k, **{x: local[k][x] for x in ("dtype", "shape", "bytes")}} for k in dropped],
        "fp8_names_also_in_local": fp8_name_in_local,
        "fp8_added_sample": fp8_added[:20],
    }
    with open(out_path, "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, indent=1))
    print("mismatch:", len(mismatch), "missing locally:", len(missing_local),
          "fp8 names also present locally:", len(fp8_name_in_local))

if __name__ == "__main__":
    main()
