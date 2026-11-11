#!/usr/bin/env python3
"""Layer 1 of the context probe: a deterministic depth profile. Teacher-forced scoring of fixed long texts through
CuteAFD's bench probe (POST /v1/bench/probe; scoring launch: ENABLE_BENCH=on, API_KEY_FILE, FULL_PREFILL_LOGITS=on,
PROBE_DUMP_ROOT for full-vocabulary rows), so two engine settings can be compared row by row at each context depth
with no sampling in the way. There is no teacher this deep: every reading is setting against setting.

  depth_profile.py build                                  tokenize the five texts once (needs `tokenizers`)
  depth_profile.py capture --arm hqa --run-tag r0 --path prefill [--dump-root DIR] [--texts NAME ...]
  depth_profile.py capture --arm hqa --run-tag r0 --path decode  [--dump-root DIR]
  depth_profile.py compare --a hqa/r0 --b compact/r0 [--path prefill]

Geometry. prefill: one request per text scores it from token 4,096 on in the engine's 4,096-row prefill units
(`score_from` a multiple of 4,096, so unit cuts fall on the same tokens in every setting); 64 rows are recorded per
unit starting at depth D: the 32 predicted positions D+1..D+32 and 32 spread through the unit (D+64+128k). A second
short request records 64 rows between 1,024 and 4,096. decode: one request per depth D prefills [0, D) and runs the
next 64 tokens as one decode-shaped step (the kernels a generated token goes through), recording D+1..D+64; the
first 32 are the same positions as the prefill path's.

Each returned row carries the top 20 [id, log-prob] (f64 log-softmax of the f32 logits over the full vocabulary),
the log-prob of the given next token, the argmax and an FNV hash of the raw row (equal hash = byte-identical
row). With --dump-root every recorded row is also written by the engine as a full-vocabulary log-prob vector, from
which `compare` computes exact KL; without dumps it reports top-1 agreement, the given token's NLL and hash
equality only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probelib as P  # noqa: E402
import tasklib as T  # noqa: E402

OUT = P.RUN / "depth"
TEXTS = OUT / "texts"
UNIT = 4096
MAX_TOKENS = 126_978            # room for the unit starting at 122,880
TOKENIZER = Path("<hf-hub>/models--brandonmusic--GLM-5.3-Flash-tr3-4bpw/snapshots/"
                 "a5fee929cf4888b1824323e33e8a19b60129e025/tokenizer.json")
TOKENIZER_SHA256 = "19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d"
HEAD = "[gMASK]<sop><|system|>Reasoning Effort: Max<|user|>"   # the template's opening, close enough for scoring
# Frames. "user": the text is the body of a user turn (the first captures; next-token rows there turned out unstable
# under any numerical change, see PROTOCOL-DRAFT section 11). "asst": the same text as the visible content of an
# assistant turn, rendered as the checkpoint's template renders one after the last user message.
ASK = "Write out the document in full, exactly as it is."
THINK = ("The user wants the document written out in full. I will write it out exactly, from the first line to the "
         "last, with nothing added.")
FRAMES = {"user": HEAD, "asst": HEAD + ASK + "<|assistant|><think>" + THINK + "</think>"}
T128 = Path("<run>/stage0/prompts/T")
SOURCES = {  # name -> (kind, path)
    "prose": ("blockT", T128 / "prose/128k/p0.json"),
    "code": ("blockT", T128 / "code/128k/p0.json"),
    "ledger": ("item", P.ITEMS / "depth/ledger/ledger-900-128k.json"),
    "join": ("item", P.ITEMS / "depth/join/join-900-128k.json"),
    "trace": ("item", P.ITEMS / "depth/trace/trace-900-128k.json"),
}
DECODE_DEPTHS = [4096, 16384, 32768, 65536, 98304, 122880]
BANDS = [(1024, 4096), (4096, 16384), (16384, 32768), (32768, 65536), (65536, 98304), (98304, 131072)]


def build(frame: str = "user") -> int:
    from tokenizers import Tokenizer
    if P.sha256_file(TOKENIZER) != TOKENIZER_SHA256:
        sys.exit("tokenizer.json differs from the one earlier runs recorded")
    tok = Tokenizer.from_file(str(TOKENIZER))
    TEXTS.mkdir(parents=True, exist_ok=True)
    for name, (kind, path) in SOURCES.items():
        doc = json.loads(path.read_text())
        content = doc["messages"][0]["content"] if kind == "blockT" else T.single_content(doc)
        content = content.strip() if frame == "asst" else content      # the template strips assistant content
        ids = tok.encode(FRAMES[frame] + content, add_special_tokens=False).ids[:MAX_TOKENS]
        rec = {"name": name, "source": str(path), "source_sha256": P.sha256_file(path), "head": FRAMES[frame],
               "frame": frame,
               "n_tokens": len(ids), "ids_sha256": P.sha256_text(json.dumps(ids)), "ids": ids}
        text_file(name, frame).write_text(json.dumps(rec) + "\n")
        print(f"{name}: {len(ids):,} tokens, units to depth {max(depths(len(ids))):,}", flush=True)
    return 0


def text_file(name: str, frame: str = "user") -> Path:
    return TEXTS / (f"{name}.json" if frame == "user" else f"{name}.{frame}.json")


def load_text(name: str, frame: str = "user") -> dict:
    return json.loads(text_file(name, frame).read_text())


def depths(n: int) -> list[int]:
    """Starts of the 4,096-row units that fit entirely before the last token."""
    return list(range(UNIT, n - 1 - UNIT + 1, UNIT))


def unit_positions(d: int) -> list[int]:
    return list(range(d + 1, d + 33)) + [d + 64 + 128 * k for k in range(32)]


def requests_for(text: dict, path: str, decode_depths) -> list[dict]:
    """[{label, prompt_ids, score_from, positions}] for one text."""
    ids = text["ids"]
    if path == "prefill":
        deep = [p for d in depths(len(ids)) for p in unit_positions(d)]
        shallow = list(range(1025, 1057)) + [1088 + 96 * k for k in range(32)]
        return [{"label": "prefill-shallow", "prompt_ids": ids[:UNIT + 1], "score_from": 1024, "positions": shallow},
                {"label": "prefill", "prompt_ids": ids, "score_from": UNIT, "positions": deep}]
    return [{"label": f"decode-{d:06d}", "prompt_ids": ids[:d + 65], "score_from": d,
             "positions": list(range(d + 1, d + 65))} for d in decode_depths if d + 65 <= len(ids)]


def probe_payload(req: dict, path: str, seed: int, dump_leaf, verify_rows) -> dict:
    ids = req["prompt_ids"]
    spec = {"prompt_ids": ids, "cold": True, "no_speculation": True, "score_from": req["score_from"],
            "score_path": path, "score_positions": req["positions"], "top_k": 20,
            "want": {str(p): [ids[p]] for p in req["positions"]}}
    if dump_leaf:
        spec["dump_rows"] = dump_leaf
    if verify_rows and path == "decode":
        spec["verify_rows"] = verify_rows
    body = {"messages": [{"role": "user", "content": "score"}], "max_tokens": 1, "temperature": P.TEMPERATURE,
            "top_p": P.TOP_P, "top_k": P.TOP_K, "seed": int(seed)}
    return {"body": body, "spec": spec}


def parse_reply(reply: dict, req: dict, path: str) -> tuple[list[dict], dict]:
    pr = reply.get("probe") or {}
    if pr.get("error"):
        raise ValueError(f"probe error: {pr['error']}")
    ids = req["prompt_ids"]
    checks = {"engine": pr.get("engine"), "cold": pr.get("cold"), "no_speculation": pr.get("no_speculation"),
              "cached_tokens": pr.get("cached_tokens"), "score_path": pr.get("score_path"),
              "scored": pr.get("scored"), "scored_prefill_chunks": pr.get("scored_prefill_chunks"),
              "prompt_ids_match": pr.get("prompt_ids") == ids}
    if not (checks["engine"] and checks["cold"] is True and checks["no_speculation"] is True
            and checks["cached_tokens"] == 0 and checks["prompt_ids_match"] and checks["score_path"] == path):
        raise ValueError(f"engine did not honour cold, drafts-off, {path} scoring of these ids: {checks}")
    want = set(req["positions"])
    rows, seen = [], set()
    for row in pr.get("rows") or []:
        p = int(row["position"])
        if p not in want or p in seen:
            continue
        seen.add(p)
        wanted = {int(i): lp for i, lp in row.get("wanted") or []}
        if ids[p] not in wanted:
            raise ValueError(f"position {p}: the given token is not in `wanted`")
        rows.append({"p": p, "tok": ids[p], "tok_lp": wanted[ids[p]], "argmax": row.get("argmax"),
                     "top": [[int(i), lp] for i, lp in row["top"]], "hash": row.get("hash"),
                     "finite": row.get("finite")})
    if seen != want:
        raise ValueError(f"{len(want - seen)} of {len(want)} scored positions missing from the reply")
    rows.sort(key=lambda r: r["p"])
    return rows, {"probe_checks": checks, "server": reply.get("server") or {}}


def capture(a) -> int:
    base = a.base_url.rstrip("/")
    names = a.texts or list(SOURCES)
    plan = [(n, r) for n in names for r in requests_for(load_text(n, a.frame), a.path, a.depths)]
    print(f"{a.arm} {a.run_tag} {a.path}: {len(plan)} requests, {sum(len(r['positions']) for _, r in plan):,} rows, "
          f"dumps {'on' if a.dump_root else 'off'}", flush=True)
    if a.dry_run:
        for n, r in plan[:4]:
            print(f"  {n} {r['label']}: prompt_ids {len(r['prompt_ids']):,}, score_from {r['score_from']:,}, "
                  f"{len(r['positions'])} positions {r['positions'][0]}..{r['positions'][-1]}")
        return 0
    key = P.read_key(a.api_key_file)
    status = P.get_json(base + "/v1/bench/status", key)
    if a.path == "prefill" and status.get("full_prefill_logits") is not True:
        print("the server was not launched with FULL_PREFILL_LOGITS=on (scoring launch required)", flush=True)
        return 2
    out = OUT / a.arm / a.run_tag
    out.mkdir(parents=True, exist_ok=True)
    client = P.stage0_client()
    log = {"arm": a.arm, "run_tag": a.run_tag, "path": a.path, "args": vars(a), "bench_status": status,
           "models_doc": P.models_doc(base, key), "driver_sha256": P.sha256_file(__file__),
           "started": P.now_iso(), "gpu_start": client.gpu_snapshot(), "requests": [], "complete": False}
    t_all = time.time()
    for i, (name, req) in enumerate(plan):
        dest = out / f"{name}.{req['label']}.json.gz"
        if dest.exists():
            continue
        text = load_text(name, a.frame)
        seed = P.SEED_BASE["depth"] + list(SOURCES).index(name) * 1000 + i
        leaf = f"{a.arm}-{a.run_tag}-{name}-{req['label']}" if a.dump_root else None
        code, raw, dt = P.post_json(base + "/v1/bench/probe", probe_payload(req, a.path, seed, leaf, a.verify_rows),
                                    key, a.timeout)
        if code != 200:
            print(f"[{i + 1}/{len(plan)}] {name} {req['label']}: HTTP {code} {raw[:300]!r}", flush=True)
            log["error"] = f"{name} {req['label']}: HTTP {code}"
            break
        try:
            rows, eng = parse_reply(json.loads(raw), req, a.path)
        except ValueError as e:
            print(f"[{i + 1}/{len(plan)}] {name} {req['label']}: bad reply: {e}", flush=True)
            log["error"] = f"{name} {req['label']}: {e}"
            break
        meta = {"text": name, "frame": a.frame, "label": req["label"], "arm": a.arm, "run_tag": a.run_tag, "path": a.path,
                "ids_sha256": text["ids_sha256"], "prompt_tokens": len(req["prompt_ids"]),
                "score_from": req["score_from"], "seed": seed, "elapsed_s": round(dt, 3), "engine": eng,
                "dump": str(Path(a.dump_root) / leaf) if leaf else None, "captured_at": P.now_iso(),
                "all_finite": all(r["finite"] for r in rows)}
        tmp = dest.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as f:
            json.dump({"meta": meta, "rows": rows}, f)
        tmp.replace(dest)
        log["requests"].append({k: meta[k] for k in ("text", "label", "seed", "elapsed_s", "dump", "all_finite")})
        print(f"[{i + 1}/{len(plan)}] {name} {req['label']}: {len(rows)} rows, {dt:.1f} s "
              f"({time.time() - t_all:.0f} s)", flush=True)
    else:
        log["complete"] = True
    log.update(finished=P.now_iso(), gpu_end=client.gpu_snapshot())
    P.write_json_atomic(out / f"capture-{a.path}-{time.strftime('%Y%m%dT%H%M%S')}.json", log)
    return 0 if log["complete"] else 2


# ---- compare ----

def load_rows(arm_tag: str, path: str) -> dict:
    """{(text, label): {"meta":..., "rows": {p: row}}} for one arm/run-tag."""
    out = {}
    for f in sorted((OUT / arm_tag).glob("*.json.gz")):
        with gzip.open(f, "rt") as fh:
            doc = json.load(fh)
        if doc["meta"]["path"] == path:
            out[(doc["meta"]["text"], doc["meta"]["label"])] = {"meta": doc["meta"],
                                                              "rows": {r["p"]: r for r in doc["rows"]}}
    return out


def band_of(p: int) -> str:
    for lo, hi in BANDS:
        if lo <= p - 1 < hi:
            return f"{lo // 1024}-{hi // 1024}K"
    return "other"


def mean_ci(values_by_unit: dict, n_boot=2000, seed=11) -> tuple[float, float, float]:
    """Mean over rows with a 95% interval from resampling units ((text, 4,096-row unit) clusters of rows)."""
    units = list(values_by_unit.values())
    flat = [v for u in units for v in u]
    if not flat:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        pick = [units[rng.randrange(len(units))] for _ in units]
        tot = sum(len(u) for u in pick)
        boots.append(sum(sum(u) for u in pick) / tot)
    boots.sort()
    return statistics.fmean(flat), boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot) - 1]


def compare(a) -> int:
    A, B = load_rows(a.a, a.path), load_rows(a.b, a.path)
    keys = sorted(set(A) & set(B))
    if not keys:
        sys.exit("no (text, request) captured under both")
    per_row = []
    for key in keys:
        ma, mb = A[key]["meta"], B[key]["meta"]
        if ma["ids_sha256"] != mb["ids_sha256"]:
            sys.exit(f"{key}: the two captures scored different token ids")
        da, db = P.dump_index(ma.get("dump")), P.dump_index(mb.get("dump"))
        for p in sorted(set(A[key]["rows"]) & set(B[key]["rows"])):
            ra, rb = A[key]["rows"][p], B[key]["rows"][p]
            kl = P.exact_kl(da[p], db[p]) if p in da and p in db else None
            per_row.append({"text": key[0], "label": key[1], "p": p, "unit": (p - 1) // UNIT,
                            "start_block": (p - 1) % UNIT < 64 if a.path == "prefill" else True,
                            "band": band_of(p), "kl": kl, "top1_differs": ra["argmax"] != rb["argmax"],
                            "dnll": rb["tok_lp"] * -1 - ra["tok_lp"] * -1, "hash_equal": ra["hash"] == rb["hash"]})
    have_kl = all(r["kl"] is not None for r in per_row)

    def table(rows, by):
        groups = {}
        for r in rows:
            groups.setdefault(by(r), []).append(r)
        out = {}
        for g, rs in groups.items():
            def units(field):
                u = {}
                for r in rs:
                    u.setdefault((r["text"], r["unit"]), []).append(float(r[field]))
                return u
            row = {"rows": len(rs), "units": len({(r["text"], r["unit"]) for r in rs}),
                   "top1_differs": mean_ci(units("top1_differs")), "dnll_b_minus_a": mean_ci(units("dnll")),
                   "hash_equal": statistics.fmean(float(r["hash_equal"]) for r in rs)}
            if have_kl:
                kls = sorted(r["kl"] for r in rs)
                row.update(kl_mean=mean_ci(units("kl")), kl_median=statistics.median(kls),
                           kl_p95=kls[int(0.95 * (len(kls) - 1))])
            out[g] = row
        return out

    order = [f"{lo // 1024}-{hi // 1024}K" for lo, hi in BANDS]
    res = {"a": a.a, "b": a.b, "path": a.path, "requests": [list(k) for k in keys], "rows": len(per_row),
           "exact_kl": have_kl, "kl_direction": "KL(a || b), nats", "by_band": table(per_row, lambda r: r["band"]),
           "by_band_text": table(per_row, lambda r: f"{r['band']} {r['text']}"),
           "by_band_block": table(per_row, lambda r: f"{r['band']} {'unit start' if r['start_block'] else 'spread'}")}
    dest = OUT / "compare" / f"{a.a.replace('/', '-')}__{a.b.replace('/', '-')}.{a.path}.json"
    P.write_json_atomic(dest, res)
    print(f"{a.a} vs {a.b} ({a.path}): {len(per_row):,} rows over {len(keys)} requests; exact KL "
          f"{'yes' if have_kl else 'no (dumps missing)'}")
    print(f"{'depth':>9} {'rows':>6} {'KL mean [95%]':>30} {'KL med':>9} {'top-1 differs':>22} "
          f"{'dNLL b-a':>24} {'hash=':>6}")
    for g in order:
        r = res["by_band"].get(g)
        if not r:
            continue
        kl = "{:.5f} [{:.5f}, {:.5f}]".format(*r["kl_mean"]) if have_kl else "n/a"
        med = f"{r['kl_median']:.5f}" if have_kl else "n/a"
        print(f"{g:>9} {r['rows']:>6} {kl:>30} {med:>9} {'{:.4f} [{:.4f}, {:.4f}]'.format(*r['top1_differs']):>22} "
              f"{'{:+.5f} [{:+.5f}, {:+.5f}]'.format(*r['dnll_b_minus_a']):>24} {r['hash_equal']:>6.3f}")
    print(f"-> {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--frame", default="user", choices=list(FRAMES))
    c = sub.add_parser("capture")
    c.add_argument("--arm", required=True)
    c.add_argument("--run-tag", required=True)
    c.add_argument("--path", required=True, choices=["prefill", "decode"])
    c.add_argument("--frame", default="user", choices=list(FRAMES), help="where the text sits in the chat")
    c.add_argument("--texts", nargs="+", choices=list(SOURCES))
    c.add_argument("--depths", nargs="+", type=int, default=DECODE_DEPTHS, help="decode path: context depths")
    c.add_argument("--verify-rows", type=int, default=0, help="decode path: step width (0 = the engine's default)")
    c.add_argument("--dump-root", default="", help="the launch's PROBE_DUMP_ROOT: also dump full-vocabulary rows")
    c.add_argument("--api-key-file", default=P.KEY_FILE)
    c.add_argument("--base-url", default=P.BASE_URL)
    c.add_argument("--timeout", type=float, default=3600.0)
    c.add_argument("--dry-run", action="store_true")
    m = sub.add_parser("compare")
    m.add_argument("--a", required=True, help="reference, as arm/run-tag")
    m.add_argument("--b", required=True)
    m.add_argument("--path", default="prefill", choices=["prefill", "decode"])
    a = ap.parse_args()
    return {"build": lambda: build(a.frame), "capture": lambda: capture(a), "compare": lambda: compare(a)}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
