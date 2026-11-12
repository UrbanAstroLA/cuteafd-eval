#!/usr/bin/env python3
"""Bits per weight of each configuration's checkpoint, by component, from the safetensors headers alone.

  bpw.py ARM=SNAPSHOT_DIR [ARM=SNAPSHOT_DIR ...]      prints the table and writes BPW.json beside this file

Reads only the JSON header of every .safetensors file (names, dtypes, shapes, byte ranges); no weight is loaded.
Standard library only.

Unit
  bits per weight = stored bits / weights
  stored bits     every tensor the checkpoint holds for a matrix: the quantized payload and its scale and sign
                  vectors. Container bookkeeping (alignment padding, checksums, index records) is left out and
                  reported as `bookkeeping_bytes`.
  weights         the size of the matrix the tensors stand for: rows x columns of the original weight. For an
                  EXL3 or EXLR8 trellis this is len(suh) x len(svh) (the two scale vectors run along the two sides).
  relative        bits per weight / 16. BF16, the format the model was released in, is 1.00.

What is counted: the language model as stored in the checkpoint the configuration loads. The vision tower
(`model.visual.*`) is left out; every configuration here ran with vision off. This is a property of the files, not
of the running engine: what each launch held in GPU memory is in RESULTS.md section 13.

Components: the rows cover the model's main layers (config.json `num_hidden_layers`). The checkpoint also carries a
multi-token-prediction block after them (layer index `num_hidden_layers`), with its own attention, experts and
projection; it is one row of its own and is part of the whole-model figure.

Arms
  anchor      the BF16-core checkpoint
  hqa         the HQA checkpoint; where a matrix is stored twice (EXL3 and BF16) the BF16 copy is counted
  compact     the same checkpoint; where a matrix is stored twice the EXL3 copy is counted
  exlr8-k4    the EXLR8 repository's dense files and its K4 expert files (the K2 and K3 widths are not counted)
  k325-fp8    the K3.25-Core-FP8 checkpoint
"""
import json
import os
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BITS = {"BF16": 16, "F16": 16, "I16": 16, "F32": 32, "I32": 32, "U8": 8, "I8": 8, "F8_E4M3": 8, "I64": 64, "U64": 64}
BOOK = ("__pad", "checksum", "record", "index")           # container bookkeeping, not counted
PAYLOAD = ("weight", "fp8", "bf16")                       # a tensor that is the matrix itself
MTP = "multi-token-prediction block"
COMPONENTS = ("routed experts", "shared experts", "dense MLP (layers 0-2)", "attention: o_proj and q_b_proj",
              "attention: other projections", "output head", "embedding", "other", MTP)


def header(path):
    with open(path, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        h = json.loads(fh.read(n))
    meta = h.pop("__metadata__", None) or {}
    return h, meta


def component(name):
    if "experts." in name and "shared_experts" not in name or name.startswith(("trellis.", "k4.")):
        return "routed experts"
    if "shared_experts" in name or name.startswith("shared."):
        return "shared experts"
    if re.search(r"(^|\.)mlp\.(gate|up|down)_proj$", name):
        return "dense MLP (layers 0-2)"
    if name.endswith(("self_attn.o_proj", "self_attn.q_b_proj")):
        return "attention: o_proj and q_b_proj"
    if "self_attn" in name:
        return "attention: other projections"
    if name.endswith("lm_head"):
        return "output head"
    if name.endswith("embed_tokens"):
        return "embedding"
    return "other"


def prod(shape):
    p = 1
    for s in shape:
        p *= s
    return p


def scan(arm, root):
    """-> {component: [weights, bits]}, routed-expert width histogram, bookkeeping bytes, counts"""
    cfg = json.load(open(os.path.join(root, "config.json")))
    mtp = str(cfg.get("text_config", cfg)["num_hidden_layers"])        # the block stored after the main layers
    comp = defaultdict(lambda: [0, 0])
    widths, fmt = defaultdict(int), defaultdict(lambda: defaultdict(int))
    book = vision = files = 0
    groups, exp = defaultdict(dict), []               # groups[(file scope, matrix name)][suffix] = (dtype, shape, bytes)
    for dp, _, fns in sorted(os.walk(root, followlinks=True)):
        for fn in sorted(fns):
            if not fn.endswith(".safetensors"):
                continue
            if arm == "exlr8-k4" and re.search(r"\.k[23]\.safetensors$", fn):
                continue
            h, meta = header(os.path.join(dp, fn))
            if meta.get("format", "").endswith("index-slice"):
                continue                              # the expert index again, regrouped per GPU rank
            files += 1
            # EXLR8 names carry no layer number (one file per layer); HF-style names do, and a matrix's tensors
            # may sit in different shards
            scope = fn if meta.get("format", "").startswith("exlr8") or "exlr8" in fn else ""
            in_mtp = meta.get("layer") == mtp
            layer_file = meta.get("contents") in ("trellis", "index")
            for k, v in h.items():
                nbytes = v["data_offsets"][1] - v["data_offsets"][0]
                if k.startswith("model.visual."):
                    vision += nbytes
                    continue
                pre, _, suf = k.rpartition(".")
                if suf in BOOK or pre == "__pad" or pre.endswith("__pad"):
                    book += nbytes
                    continue
                if layer_file:
                    if re.match(r"(shared\.)?k[23]\.", k):
                        continue                      # index entries of the widths this arm does not load
                    exp.append((k, nbytes, meta))
                    continue
                groups[(scope, pre, in_mtp or f".layers.{mtp}." in k)][suf] = (v["dtype"], v["shape"], nbytes)
    # EXLR8 expert files: one tensor per kind for all experts of a layer; sizes come from the file metadata
    for name, nbytes, meta in exp:
        n, hid, mid = int(meta["routed_experts"]), int(meta["hidden_size"]), int(meta["moe_intermediate_size"])
        routed = not name.startswith("shared.")
        c = MTP if meta["layer"] == mtp else "routed experts" if routed else "shared experts"
        comp[c][1] += nbytes * 8
        if name.rpartition(".")[0] in ("trellis", "shared.trellis"):
            w = (n if routed else 1) * hid * mid
            comp[c][0] += w
            if c == "routed experts":
                widths[round(nbytes * 8 / w, 2)] += n
            fmt[c][f"EXLR8 trellis, {round(nbytes * 8 / w, 2):g} bits"] += w
    for (_, pre, in_mtp), d in groups.items():
        c = MTP if in_mtp else component(pre)
        if "trellis" in d and "weight" in d:          # stored twice: the arm decides which copy it reads
            d = {"weight": d["weight"]} if arm != "compact" else {s: x for s, x in d.items() if s != "weight"}
        bits = sum(x[2] * 8 for x in d.values())
        pay = [s for s in PAYLOAD if s in d and len(d[s][1]) >= 2]
        if "trellis" in d:
            w = d["suh"][1][0] * d["svh"][1][0]
            t = d["trellis"]
            if t[0] == "I16":                         # EXL3: [tiles, tiles, 16 x K] of int16, 16 x 16 weights a tile
                assert 256 * t[1][0] * t[1][1] == w, (pre, t[1], w)
            k = round(t[2] * 8 / w, 2)
            if c == "routed experts":
                widths[k] += 1
            fmt[c][f"{'EXL3' if t[0] == 'I16' else 'EXLR8'} trellis, {k:g} bits"] += w
        elif pay:
            w = prod(d[pay[0]][1])
            dt = d[pay[0]][0]
            fmt[c]["FP8" if dt in ("F8_E4M3", "U8") else dt] += w
        else:                                         # vectors and small tables stored on their own
            w = sum(prod(x[1]) for x in d.values())
            fmt[c]["vectors and small tables, as stored"] += w
        comp[c][0] += w
        comp[c][1] += bits
    return comp, widths, fmt, book, vision, files


def main(argv):
    arms = dict(a.split("=", 1) for a in argv)
    out = {"unit": "bits per weight = stored bits / weights; relative = bits per weight / 16 (BF16 = 1.00)",
           "counted": "language model as stored in the checkpoint; vision tower and container bookkeeping left out",
           "components": list(COMPONENTS), "arms": {}}
    for arm, root in arms.items():
        m = re.search(r"models--([^/]+)--([^/]+)/snapshots/([0-9a-f]{40})", root)
        comp, widths, fmt, book, vision, files = scan(arm, root)
        W, B = sum(v[0] for v in comp.values()), sum(v[1] for v in comp.values())
        rec = {"checkpoint": f"{m.group(1)}/{m.group(2)}" if m else None, "revision": m.group(3) if m else None,
               "files": files, "weights": W, "stored_bytes": B // 8, "bits_per_weight": round(B / W, 4),
               "relative_to_bf16": round(B / W / 16, 4), "bookkeeping_bytes": book, "vision_bytes_not_counted": vision,
               "by_component": {}, "routed_expert_widths": {f"{k:g}": n for k, n in sorted(widths.items())}}
        for c in COMPONENTS:
            w, b = comp.get(c, (0, 0))
            rec["by_component"][c] = {"weights": w, "stored_bytes": b // 8, "share_of_weights": round(w / W, 4),
                                      "bits_per_weight": round(b / w, 4) if w else None,
                                      "relative_to_bf16": round(b / w / 16, 4) if w else None,
                                      "formats": {k: round(n / w, 4) for k, n in sorted(fmt[c].items(), key=lambda x: -x[1])}}
        ow, ob = (sum(comp.get(c, (0, 0))[i] for c in COMPONENTS if c not in ("routed experts", MTP)) for i in (0, 1))
        rec["outside_routed_experts"] = {"what": "main layers, every component but the routed experts", "weights": ow,
                                         "stored_bytes": ob // 8, "share_of_weights": round(ow / W, 4),
                                         "bits_per_weight": round(ob / ow, 4), "relative_to_bf16": round(ob / ow / 16, 4)}
        out["arms"][arm] = rec
    (HERE / "BPW.json").write_text(json.dumps(out, indent=1) + "\n")
    names = list(out["arms"])
    print(f"{'component':34s}" + "".join(f"{a:>12s}" for a in names))
    for c in COMPONENTS:
        print(f"{c:34s}" + "".join(f"{out['arms'][a]['by_component'][c]['bits_per_weight'] or 0:12.2f}" for a in names))
    print(f"{'outside the routed experts':34s}" + "".join(f"{out['arms'][a]['outside_routed_experts']['bits_per_weight']:12.2f}" for a in names))
    print(f"{'whole language model':34s}" + "".join(f"{out['arms'][a]['bits_per_weight']:12.2f}" for a in names))
    print(f"{'relative to BF16':34s}" + "".join(f"{out['arms'][a]['relative_to_bf16']:12.3f}" for a in names))
    print(f"{'stored GiB':34s}" + "".join(f"{out['arms'][a]['stored_bytes'] / 2**30:12.1f}" for a in names))
    print(f"{'weights, billions':34s}" + "".join(f"{out['arms'][a]['weights'] / 1e9:12.3f}" for a in names))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
