#!/usr/bin/env python3
"""Write capture plans for both engines, from one source of token ids per panel.

For every panel it writes three files into --out:

  <panel>.cuteafd-plan.json   exactly the format of <cuteafd>/scripts/bench/glmf-teacher-kl.py
                              (docstring lines 28-30): {"vocab": V, "windows": [{"window_id", "tokens",
                              "tokens_sha256" (sha256 of the ids as LE u32), "positions": [rows]}]}
                              where row r is the distribution after tokens[0..r], predicting tokens[r+1].
  <panel>.vllm-registry.json  the same windows for our vLLM plugin: {"schema", "panel", "vocab",
                              "windows": [{"window_id", "tokens", "rows"}]}; rows use the same convention.
  <panel>.meta.json           per-window metadata the scorers need (score_from, roles, block, bucket,
                              doc_id, doc_type, length bucket, token hashes) plus the input provenance.

Panels
  pa   brandonmusic BF16 teacher panel: 25 windows x 2048 tokens, rows 0..2046 (all 2,047).
       Tokens: <teacher>/calibration/panel-v1/arrays/final-%04d.tokens.npy, checked against
       dataset-manifest.json token_ids_sha256 (sha256 of the .npy file, PLAN.md §1).
  pb   tpurtell cuteafd-fidelity glm5_flash-v2_20261005_bf16root: 64 windows; each scores the
       predicted positions score_from..n-1 (fidelity_dataset.rs:353-354), i.e. rows score_from-1..n-2
       (512 per window). windows.json is checked against manifest.json windows_sha256.
  q2   generic long windows: --q2-input JSON, a list (or {"windows": [...]}) of
       {"window_id", "doc_id", "doc_type": "prose"|"code", "length_bucket": "32K"|"64K"|"128K",
        "tokens": [ids] or "tokens_npy": path, "n_score": 4096 (default)}; rows are the last n_score
       rows, n-1-n_score .. n-2 (they predict the last n_score tokens).

CAUTION for P-B on CuteAFD: glmf-teacher-kl.py always sends score_from=1 (line 62), so the whole
window from token 1 on runs through the scoring path; tpurtell's CLI sends score_from=window.score_from
(fidelity_cli.rs:300), so the context is an ordinary prefix prefill and only the 512 scored rows run on
the scoring path (shared/probe.rs:322-335). The two captures are different engine geometries. The
README recommends taking CuteAFD's P-B rows from the CLI's own --dump-dir instead.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import ast
import struct

# Standard library only, so it runs with the host's plain python3 (no numpy there).
VOCAB = 154880


def sha256_file(path: str, chunk: int = 32 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb", buffering=0) as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def tokens_sha256(tokens) -> str:
    """sha256 of the ids as little-endian u32 (glmf-teacher-kl.py:55-57)."""
    return hashlib.sha256(struct.pack(f"<{len(tokens)}I", *[int(t) for t in tokens])).hexdigest()


def dump_json(path: str, obj) -> None:
    with open(path + ".partial", "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(path + ".partial", path)


def load_npy_ints(path: str) -> list:
    """Minimal .npy reader for 1-D little-endian int32/int64/uint32 arrays (stdlib only)."""
    with open(path, "rb") as f:
        if f.read(6) != b"\x93NUMPY":
            raise ValueError(f"{path}: not a .npy file")
        major = f.read(2)[0]
        hlen = struct.unpack("<H" if major == 1 else "<I", f.read(2 if major == 1 else 4))[0]
        head = ast.literal_eval(f.read(hlen).decode("latin1"))
        fmt = {"<i4": "i", "<i8": "q", "<u4": "I"}.get(head["descr"])
        if fmt is None or head["fortran_order"] or len(head["shape"]) != 1:
            raise ValueError(f"{path}: unsupported npy {head}")
        n = head["shape"][0]
        data = f.read(n * struct.calcsize(fmt))
    return list(struct.unpack(f"<{n}{fmt}", data))

TEACHER = "<datasets>/glm53-flash-teacher-logits"
PB_ROOT = "<datasets>/2026-10-26-engine-compare/cuteafd-fidelity/glm5_flash-v2_20261005_bf16root"


def _write(out: str, panel: str, windows: list, meta: dict) -> dict:
    plan = {"vocab": VOCAB, "windows": [{"window_id": w["window_id"], "tokens": w["tokens"],
                                         "tokens_sha256": tokens_sha256(w["tokens"]),
                                         "positions": w["rows"]} for w in windows]}
    reg = {"schema": "engine-compare.vllm-registry/1", "panel": panel, "vocab": VOCAB,
           "row_convention": "row r = distribution after tokens[0..r], predicting tokens[r+1]",
           "windows": [{"window_id": w["window_id"], "tokens": w["tokens"], "rows": w["rows"]} for w in windows]}
    for w in windows:
        rows = w["rows"]
        assert rows == sorted(set(rows)), w["window_id"]
        assert rows[0] >= 0 and rows[-1] + 1 < len(w["tokens"]), w["window_id"]   # glmf-teacher-kl.py:139-140
        assert all(0 <= t < VOCAB for t in w["tokens"]), w["window_id"]
    paths = {}
    for kind, obj in (("cuteafd-plan", plan), ("vllm-registry", reg)):
        p = os.path.join(out, f"{panel}.{kind}.json")
        with open(p + ".partial", "w") as f:
            json.dump(obj, f, separators=(",", ":"))
        os.replace(p + ".partial", p)
        paths[kind] = {"path": p, "sha256": sha256_file(p)}
    meta = dict(meta)
    meta["files"] = paths
    meta["windows"] = [{k: v for k, v in w.items() if k not in ("tokens",)} | {
        "n_tokens": len(w["tokens"]), "tokens_sha256": tokens_sha256(w["tokens"]),
        "first_row": w["rows"][0], "last_row": w["rows"][-1], "n_rows": len(w["rows"])} for w in windows]
    for m in meta["windows"]:
        m.pop("rows", None)
    mp = os.path.join(out, f"{panel}.meta.json")
    dump_json(mp, meta)
    paths["meta"] = {"path": mp, "sha256": sha256_file(mp)}
    return paths


def build_pa(teacher: str = TEACHER) -> tuple[list, dict]:
    man = json.load(open(os.path.join(teacher, "dataset-manifest.json")))
    files = man["logit_files"]
    windows = []
    for i, e in enumerate(files):
        wid = e["window_id"]
        assert wid == f"final-{i:04d}" and e["path"] == f"logits/window-{i:04d}.safetensors", e
        npy = os.path.join(teacher, "calibration/panel-v1/arrays", f"{wid}.tokens.npy")
        got = sha256_file(npy)
        if got != e["token_ids_sha256"]:
            raise SystemExit(f"{npy}: sha256 {got} differs from dataset-manifest.json {e['token_ids_sha256']}")
        tok = load_npy_ints(npy)
        assert len(tok) == 2048, len(tok)
        windows.append({"window_id": wid, "tokens": [int(t) for t in tok], "rows": list(range(2047)),
                        "teacher_file": e["path"], "doc_id": e.get("document_id"), "domain": e.get("domain")})
    meta = {"panel": "pa", "source": teacher, "dataset_manifest_sha256": sha256_file(os.path.join(teacher, "dataset-manifest.json")),
            "teacher_revision_note": "zai-org/GLM-5.3-Flash-BF16 @ " + man.get("model_revision", "?")}
    return windows, meta


def build_pb(root: str = PB_ROOT) -> tuple[list, dict]:
    man = json.load(open(os.path.join(root, "manifest.json")))
    wpath = os.path.join(root, "windows.json")
    got = sha256_file(wpath)
    if got != man["windows_sha256"]:
        raise SystemExit(f"windows.json sha256 {got} differs from manifest windows_sha256 {man['windows_sha256']}")
    panel = json.load(open(wpath))
    windows = []
    for w in panel["windows"]:
        n, s = len(w["tokens"]), w["score_from"]
        assert n - s == 512, w["id"]                                   # fidelity_dataset.rs:353-354
        windows.append({"window_id": w["id"], "tokens": [int(t) for t in w["tokens"]],
                        "rows": list(range(s - 1, n - 1)), "score_from": s, "block": w["block"],
                        "bucket": w["bucket"],
                        "gen_rows": sum(1 for p in range(s, n) if w["roles"][p] == "gen")})
    meta = {"panel": "pb", "source": root, "manifest_sha256": sha256_file(os.path.join(root, "manifest.json")),
            "windows_sha256": got, "set_sha256": panel["set_sha256"],
            "note": "CuteAFD CLI window order (full tier) is this list's order: dump leaf window-%03d = index"}
    return windows, meta


def build_q2(path: str) -> tuple[list, dict]:
    raw = json.load(open(path))
    items = raw["windows"] if isinstance(raw, dict) else raw
    windows, seen = [], set()
    for it in items:
        wid = it["window_id"]
        if wid in seen:
            raise SystemExit(f"duplicate window_id {wid}")
        seen.add(wid)
        if "tokens" in it:
            tok = [int(t) for t in it["tokens"]]
        else:
            tok = [int(t) for t in load_npy_ints(it["tokens_npy"])]
        k = int(it.get("n_score", 4096))
        n = len(tok)
        if n < k + 1:
            raise SystemExit(f"{wid}: {n} tokens cannot score the last {k}")
        if it.get("doc_type") not in ("prose", "code"):
            raise SystemExit(f"{wid}: doc_type must be prose or code")
        windows.append({"window_id": wid, "tokens": tok, "rows": list(range(n - 1 - k, n - 1)),
                        "doc_id": it.get("doc_id", wid), "doc_type": it["doc_type"],
                        "length_bucket": it.get("length_bucket", f"{n}"), "n_score": k,
                        "source": it.get("source")})
    meta = {"panel": "q2", "source": os.path.abspath(path), "source_sha256": sha256_file(path)}
    return windows, meta


def build_q2_index(qdir: str) -> tuple[list, dict]:
    """Q2 windows from the prompt set's index.json (stage0/prompts/q2/).

    Those files use tpurtell's POSITION convention: "row" p is the position whose prediction of
    token p is scored (it has seen tokens 0..p-1), p in L-4096..L-1. Plans and registries use ROW
    r = after tokens[0..r], predicting tokens[r+1]; so r = p - 1, rows L-4097..L-2, the same
    conversion for both engines."""
    idx_path = os.path.join(qdir, "index.json")
    idx = json.load(open(idx_path))
    base = os.path.dirname(os.path.abspath(qdir.rstrip("/")))
    windows, seen = [], set()
    files = {}
    for e in idx["windows"]:
        path = os.path.join(base, e["file"])
        if not os.path.exists(path):
            path = os.path.join(qdir, os.path.basename(e["file"]))
        w = json.load(open(path))
        wid = w["window_id"]
        if wid != e["window_id"] or wid in seen:
            raise SystemExit(f"{path}: window id {wid} vs index {e['window_id']} (or duplicate)")
        seen.add(wid)
        tok = [int(t) for t in w["tokens"]]
        L = len(tok)
        positions = [int(p) for p in w["rows"]]
        if L != w["length"] or L != e["length"]:
            raise SystemExit(f"{wid}: length {L} vs declared {w['length']}/{e['length']}")
        if positions != sorted(set(positions)) or positions[0] < 1 or positions[-1] > L - 1:
            raise SystemExit(f"{wid}: positions must be increasing, unique, in [1, L-1]")
        if positions[0] != e["first_row"] or positions[-1] != e["last_row"]:
            raise SystemExit(f"{wid}: positions differ from index first_row/last_row")
        rows = [p - 1 for p in positions]                                  # position p -> row p-1
        assert rows[-1] <= L - 2, (wid, rows[-1], L)
        assert all(tok[r + 1] == tok[p] for r, p in zip(rows, positions)), wid   # scored next id = tokens[r+1]
        if w["kind"] not in ("prose", "code"):
            raise SystemExit(f"{wid}: kind {w['kind']}")
        lb = {32768: "32K", 65536: "64K", 131072: "128K"}.get(L, str(L))
        windows.append({"window_id": wid, "tokens": tok, "rows": rows, "doc_id": w.get("source", {}).get("document", e["document"]),
                        "doc_type": w["kind"], "length_bucket": lb, "n_score": len(rows),
                        "first_position": positions[0], "last_position": positions[-1],
                        "source_file": path, "source_sha256": sha256_file(path),
                        "tokenization": w.get("tokenization")})
        files[wid] = windows[-1]["source_sha256"]
    meta = {"panel": "q2", "source": os.path.abspath(qdir), "index_sha256": sha256_file(idx_path),
            "index_rule": idx.get("rule"),
            "conversion": "source positions p (tpurtell convention) -> plan rows r = p - 1 (row r predicts tokens[r+1])"}
    return windows, meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--panels", default="pa,pb", help="comma list of pa,pb,q2")
    ap.add_argument("--teacher", default=TEACHER)
    ap.add_argument("--pb-root", default=PB_ROOT)
    ap.add_argument("--q2-input", help="q2 window list in ROW convention (see module docstring)")
    ap.add_argument("--q2-dir", help="prompt-set dir with index.json; files use the POSITION convention, converted p -> p-1")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    report = {}
    for panel in filter(None, a.panels.split(",")):
        if panel == "pa":
            w, m = build_pa(a.teacher)
        elif panel == "pb":
            w, m = build_pb(a.pb_root)
        elif panel == "q2":
            if a.q2_dir:
                w, m = build_q2_index(a.q2_dir)
            elif a.q2_input:
                w, m = build_q2(a.q2_input)
            else:
                ap.error("q2 needs --q2-dir or --q2-input")
        else:
            ap.error(f"unknown panel {panel}")
        report[panel] = _write(a.out, panel, w, m)
        print(f"{panel}: {len(w)} windows, {sum(len(x['rows']) for x in w)} rows, "
              f"{sum(len(x['tokens']) for x in w)} tokens")
        for k, v in report[panel].items():
            print(f"  {k:14s} {v['sha256']}  {v['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
