#!/usr/bin/env python3
"""Derived checkpoint for the CuteAFD core swap: K4-Core-K6's experts, MTP block and every other tensor unchanged, its
316 six-bit EXL3 core matrices (trellis/suh/svh/mcg) replaced by the original BF16 tensors (zai-org/GLM-5.3-Flash-BF16
@ f9fed3bb, the ranged copy in core.safetensors). Standard library only; no network.

    python3 build_derived.py --src <K4-Core-K6 snapshot> --core <core.safetensors> --hub <HF hub dir> --out <manifest.json>

- Shards holding core tensors are rewritten without them (CuteAFD requires each shard header to list exactly the index's
  tensors); every kept tensor's bytes are copied verbatim and hashed, then re-read from the new file and compared.
- Shards without core tensors and all non-shard files are hardlinked (same filesystem; zero bytes). quantization-errors/
  (evidence only) is not linked.
- core.safetensors is hardlinked in as model-core-bf16.safetensors.
- Index: core EXL3 entries removed, the 316 `.weight` entries added. config.json quantization_config: core_bits removed,
  head_bits 16. quantize_config.json: core_bits removed, head_bits 16, lm_head false, the 316 core modules removed from
  tensor_storage, a note under meta. Refuses to overwrite an existing snapshot directory.
"""
import argparse, hashlib, json, os, struct, sys

MODEL = "derived/GLM-5.3-Flash-EXL3-K4-Core-K6-BF16core"
SUFFIXES = (".trellis", ".suh", ".svh", ".mcg")


def header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return 8 + n, json.loads(f.read(n))


def copy_range(fi, fo, a, b, h):
    fi.seek(a); left = b - a
    while left:
        chunk = fi.read(min(left, 64 << 20)); fo.write(chunk); h.update(chunk); left -= len(chunk)


def sha_range(path, a, b):
    h = hashlib.sha256(); left = b - a
    with open(path, "rb") as f:
        f.seek(a)
        while left:
            chunk = f.read(min(left, 64 << 20)); h.update(chunk); left -= len(chunk)
    return h.hexdigest()


def rewrite(src, dst, drop):
    base, h = header(src)
    meta = h.pop("__metadata__", None)
    keep = sorted((k for k in h if k not in drop), key=lambda k: h[k]["data_offsets"][0])
    new, off = {}, 0
    for k in keep:
        a, b = h[k]["data_offsets"]
        new[k] = {"dtype": h[k]["dtype"], "shape": h[k]["shape"], "data_offsets": [off, off + b - a]}; off += b - a
    if meta is not None:
        new = {"__metadata__": meta, **new}
    hj = json.dumps(new, separators=(",", ":")).encode()
    hj += b" " * (-len(hj) % 8)
    digests = {}
    with open(src, "rb") as fi, open(dst, "xb") as fo:
        fo.write(struct.pack("<Q", len(hj))); fo.write(hj)
        for k in keep:
            a, b = h[k]["data_offsets"]; d = hashlib.sha256()
            copy_range(fi, fo, base + a, base + b, d); digests[k] = d.hexdigest()
    nb, nh = header(dst)
    bad = [k for k in keep if sha_range(dst, nb + nh[k]["data_offsets"][0], nb + nh[k]["data_offsets"][1]) != digests[k]]
    if bad or set(nh) - {"__metadata__"} != set(keep):
        raise SystemExit(f"verify failed for {dst}: {bad[:3]}")
    return {"kept": len(keep), "dropped": len(drop & set(h)), "bytes": os.path.getsize(dst)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--core", required=True)
    ap.add_argument("--hub", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    src_rev = os.path.basename(os.path.normpath(a.src))
    rev = hashlib.sha1(f"{src_rev}+bf16core:f9fed3bb:{os.path.getsize(a.core)}".encode()).hexdigest()
    root = os.path.join(a.hub, "models--" + MODEL.replace("/", "--"))
    snap = os.path.join(root, "snapshots", rev)
    if os.path.exists(snap):
        raise SystemExit(f"exists: {snap}")
    idx = json.load(open(os.path.join(a.src, "model.safetensors.index.json")))
    wm = idx["weight_map"]
    _, ch = header(a.core)
    owners = sorted(k[:-len(".weight")] for k in ch if k != "__metadata__")
    drop = {o + s for o in owners for s in SUFFIXES}
    missing = sorted(d for d in drop if d not in wm)
    if missing or len(owners) != 316:
        raise SystemExit(f"core inventory mismatch: {len(owners)} owners, missing {missing[:4]}")
    os.makedirs(snap)
    shards = sorted(set(wm.values()))
    touched = {wm[d] for d in drop}
    rep = {"model_id": MODEL, "revision": rev, "source": a.src, "core_file": a.core, "shards": {}, "linked": []}
    for name in sorted(os.listdir(a.src)):
        p = os.path.join(a.src, name)
        if os.path.isdir(p) or name in ("config.json", "quantize_config.json", "model.safetensors.index.json"):
            continue
        if name in touched:
            rep["shards"][name] = rewrite(os.path.realpath(p), os.path.join(snap, name), drop)
            print("rewrote", name, rep["shards"][name], flush=True)
        else:
            os.link(os.path.realpath(p), os.path.join(snap, name)); rep["linked"].append(name)
    os.link(a.core, os.path.join(snap, "model-core-bf16.safetensors"))
    wm2 = {k: v for k, v in wm.items() if k not in drop}
    for o in owners:
        wm2[o + ".weight"] = "model-core-bf16.safetensors"
    total = sum(os.path.getsize(os.path.join(snap, s)) for s in set(wm2.values()))
    idx2 = {**idx, "metadata": {**idx.get("metadata", {}), "total_size": total}, "weight_map": dict(sorted(wm2.items()))}
    json.dump(idx2, open(os.path.join(snap, "model.safetensors.index.json"), "x"), indent=2)
    cfg = json.load(open(os.path.join(a.src, "config.json")))
    qc = cfg["quantization_config"]; qc.pop("core_bits"); qc["head_bits"] = 16
    json.dump(cfg, open(os.path.join(snap, "config.json"), "x"), indent=2)
    q = json.load(open(os.path.join(a.src, "quantize_config.json")))
    q.pop("core_bits"); q["head_bits"] = 16; q["lm_head"] = False
    for o in owners:
        del q["tensor_storage"][o]
    q["meta"]["derived"] = ("Local derived checkpoint (not a producer release): wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6 "
                            f"@ {src_rev} with its 316 core matrices replaced by the BF16 originals from "
                            "zai-org/GLM-5.3-Flash-BF16 @ f9fed3bb; experts and MTP unchanged.")
    json.dump(q, open(os.path.join(snap, "quantize_config.json"), "x"), indent=2)
    # header/index agreement, as CuteAFD checks it
    for s in set(wm2.values()):
        _, h = header(os.path.join(snap, s))
        names = {k for k, v in wm2.items() if v == s}
        if set(h) - {"__metadata__"} != names:
            raise SystemExit(f"index/header mismatch in {s}")
    rep.update({"snapshot": snap, "tensors": len(wm2), "removed": len(drop), "added": len(owners), "total_size": total})
    json.dump(rep, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("shards", "linked")}, indent=1))


if __name__ == "__main__":
    main()
