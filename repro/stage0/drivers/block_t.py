#!/usr/bin/env python3
"""Block T (serving throughput) driver for the CuteAFD v3.0.1 vs vLLM v0.9.2 protocol. Standard library only.

Extends ../../throughput.py's approach (one streaming chat request per stream, own recorded seed, usage via
stream_options, chat_template_kwargs.enable_thinking) to the protocol grid:

  input 1K / 8K / 32K / 128K  x  concurrency 1 / 4 / 8 / 16  x  3 replicates, output max_tokens 1,024
  content prose + code at every input length; reasoning (thinking on) + json at 1K and 8K only
  skipped for cost, declared in the protocol: 128K input at 8 and 16 streams

Prompts: ../prompts/T/<content>/<len>/p<i>.json (hash-checked against ../prompts/T/index.json at start).
Every request gets its own nonce first line (nonce from salt + seed), so no request is served from the prefix
cache, except the one declared cached cell (8K prose prompt 0, one fixed nonce, 1 primer + 3 measured, 1 stream).

Batch shape: at 1 stream a replicate is the 4 prompts sent one after another; at c >= 4 streams a replicate is one
batch of c simultaneous requests (released by a barrier), stream s using prompt s % 4. Every prompt therefore
appears equally often in every cell. Order: replicate (outermost), input length, content, concurrency.
One warm-up batch (1K prose, 4 streams, flagged warmup) runs first.

Seeds (identical for both engines, so requests pair across engines):
  measured  730,000,000 + rep*10,000,000 + length_idx*1,000,000 + content_idx*100,000 + level_idx*10,000 + stream
  warm-up   739,000,000 + stream;   cached cell 738,000,000 + i (i = 0 primer, 1..3 measured)

Per request: seed, nonce, prompt id, t_send/t_first/t_last, TTFT, usage (prompt, completion, cached tokens),
prefill tok/s = prompt_tokens / TTFT (includes any queueing behind other prefills at c > 1), decode tok/s =
(completion_tokens - 1) / (t_last - t_first), finish reason, error, content/reasoning chars, whether content
contained "</think>" (vLLM streams reasoning as content when thinking is off; see ../prompts/README.md).
Per batch: aggregate tok/s = sum(completion tokens) / (last token - first send), as throughput.py;
aggregate prefill tok/s = sum(prompt tokens) / (last first-token - first send).

Usage:
  block_t.py --base-url http://127.0.0.1:8001 --label C1-run1 --out <runs>/.../C1-run1-block-t.json \
             [--api-key-file FILE] [--lengths 1024 8192] [--levels 1 4] [--contents prose code] [--reps 0 1 2]
             [--no-warmup] [--no-cached-cell] [--dry-run]
"""
import os as _os_a2
THINKING_ALL_ON = _os_a2.environ.get("A2_THINKING", "on") == "on"  # amendment A2 (2026-10-26)
import argparse
import hashlib
import json
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import client  # noqa: E402

LENGTHS = [1024, 8192, 32768, 131072]
LEVELS = [1, 4, 8, 16]
CONTENTS = ["prose", "code", "reasoning", "json"]
SHORT_ONLY = {"reasoning", "json"}
SKIPPED = {(131072, 8), (131072, 16)}
REPS = 3
PROMPTS_PER_CONTENT = 4
CACHED_CELL = ("prose", 8192, 0)


def load_cells():
    idx = json.loads((client.PROMPTS / "T" / "index.json").read_text())
    cells = {}
    for c in idx["cells"]:
        f = client.PROMPTS / c["file"]
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h != c["sha256"]:
            sys.exit(f"prompt file changed since the index was written: {c['file']}")
        cells[(c["content"], c["input_length"], c["prompt_index"])] = json.loads(f.read_text()) | {"sha256": h}
    return cells


def plan(a):
    """List of batches: dict(kind, rep, length, content, level, requests=[(prompt_index, seed, stream)])."""
    batches = []
    if not a.no_warmup:
        batches.append({"kind": "warmup", "rep": -1, "length": 1024, "content": "prose", "level": 4,
                        "groups": [[(s % 4, 739_000_000 + s, s) for s in range(4)]]})
    for rep in a.reps:
        for li, L in enumerate(LENGTHS):
            if L not in a.lengths:
                continue
            for ci, c in enumerate(CONTENTS):
                if c not in a.contents or (c in SHORT_ONLY and L > 8192):
                    continue
                for vi, lev in enumerate(LEVELS):
                    if lev not in a.levels or (L, lev) in SKIPPED:
                        continue
                    base = 730_000_000 + rep * 10_000_000 + li * 1_000_000 + ci * 100_000 + vi * 10_000
                    if lev == 1:
                        groups = [[(p, base + p, p)] for p in range(PROMPTS_PER_CONTENT)]
                    else:
                        groups = [[(s % PROMPTS_PER_CONTENT, base + s, s) for s in range(lev)]]
                    batches.append({"kind": "measured", "rep": rep, "length": L, "content": c, "level": lev,
                                    "groups": groups})
    if not a.no_cached_cell:
        c, L, p = CACHED_CELL
        batches.append({"kind": "cached", "rep": 0, "length": L, "content": c, "level": 1,
                        "groups": [[(p, 738_000_000 + i, 0)] for i in range(4)]})
    return batches


def run_group(a, key, model, cells, batch, group, salt, fixed_nonce=None):
    out = [None] * len(group)
    barrier = threading.Barrier(len(group))

    def one(i, p, seed, stream):
        cell = cells[(batch["content"], batch["length"], p)]
        nonce = fixed_nonce or client.nonce_for(salt, seed)
        body = {"model": model, "messages": client.with_nonce(cell["messages"], nonce),
                "max_tokens": a.max_tokens, "temperature": a.temperature, "top_p": a.top_p, "seed": seed,
                "stream": True, "stream_options": {"include_usage": True},
                "chat_template_kwargs": {"enable_thinking": (True if THINKING_ALL_ON else bool(cell["thinking"]))}}
        barrier.wait()
        rec = client.stream_chat(a.base_url, key, body)
        rec.update(prompt_id=cell["id"], prompt_sha256=cell["sha256"], prompt_index=p, seed=seed, nonce=nonce,
                   stream=stream, thinking=(True if THINKING_ALL_ON else bool(cell["thinking"])),
                   expected_prompt_tokens=cell["prompt_tokens"]["template_with_nonce"])
        u = rec.get("usage") or {}
        rec["prompt_tokens"] = u.get("prompt_tokens")
        rec["completion_tokens"] = u.get("completion_tokens")
        rec["cached_tokens"] = (u.get("prompt_tokens_details") or {}).get("cached_tokens",
                                                                         u.get("prompt_cache_hit_tokens"))
        if rec["t_first"] is not None:
            rec["ttft_s"] = rec["t_first"] - rec["t_send"]
            if rec["prompt_tokens"] and rec["ttft_s"] > 0:
                rec["prefill_tok_s"] = rec["prompt_tokens"] / rec["ttft_s"]
            if rec["completion_tokens"] and rec["t_last"] > rec["t_first"]:
                rec["decode_tok_s"] = (rec["completion_tokens"] - 1) / (rec["t_last"] - rec["t_first"])
        out[i] = rec

    threads = [threading.Thread(target=one, args=(i, *g)) for i, g in enumerate(group)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def summarize(groups):
    """Summary of one replicate: per group aggregates, then medians over the replicate's requests."""
    reqs = [r for g in groups for r in g]
    ok = [r for r in reqs if not r["error"] and r.get("t_first") and r.get("completion_tokens")]
    s = {"requests": len(reqs), "errors": len(reqs) - len(ok),
         "finish_reasons": sorted({str(r["finish_reason"]) for r in reqs}),
         "content_has_think_close": sum(bool(r.get("content_has_think_close")) for r in reqs)}
    if not ok:
        return s
    med = statistics.median
    s["ttft_median_s"] = med(r["ttft_s"] for r in ok)
    s["prefill_tok_s_median"] = med(r["prefill_tok_s"] for r in ok if r.get("prefill_tok_s"))
    ds = [r["decode_tok_s"] for r in ok if r.get("decode_tok_s")]
    s["decode_tok_s_per_stream_median"] = med(ds) if ds else None
    s["completion_tokens"] = [r["completion_tokens"] for r in ok]
    s["prompt_tokens"] = sorted({r["prompt_tokens"] for r in ok})
    s["cached_tokens"] = sorted({r["cached_tokens"] for r in ok if r["cached_tokens"] is not None})
    agg = []
    for g in groups:
        gok = [r for r in g if r in ok]
        if len(gok) == len(g):
            t0 = min(r["t_send"] for r in g)
            agg.append({"aggregate_tok_s": sum(r["completion_tokens"] for r in g) / (max(r["t_last"] for r in g) - t0),
                        "aggregate_prefill_tok_s": sum(r["prompt_tokens"] for r in g) /
                        (max(r["t_first"] for r in g) - t0)})
    if agg:
        s["aggregate_tok_s"] = med(x["aggregate_tok_s"] for x in agg)
        s["aggregate_prefill_tok_s"] = med(x["aggregate_prefill_tok_s"] for x in agg)
        s["aggregate_note"] = ("one batch" if len(groups) == 1 else
                               f"median over {len(agg)} sequential single-request batches")
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--label", required=True)
    ap.add_argument("--api-key-file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lengths", nargs="+", type=int, default=LENGTHS, choices=LENGTHS)
    ap.add_argument("--levels", nargs="+", type=int, default=LEVELS, choices=LEVELS)
    ap.add_argument("--contents", nargs="+", default=CONTENTS, choices=CONTENTS)
    ap.add_argument("--reps", nargs="+", type=int, default=list(range(REPS)), choices=list(range(REPS)))
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=client.DEFAULT_TEMPERATURE)
    ap.add_argument("--top-p", type=float, default=client.DEFAULT_TOP_P)
    ap.add_argument("--nonce-salt", help="default: label + start time (so a repeated run never hits the cache)")
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--no-cached-cell", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and request counts; send nothing")
    a = ap.parse_args()

    cells = load_cells()
    batches = plan(a)
    n_req = {k: sum(len(g) for b in batches if b["kind"] == k for g in b["groups"])
             for k in ("warmup", "measured", "cached")}
    prompt_tok = sum(cells[(b["content"], b["length"], p)]["prompt_tokens"]["template_with_nonce"]
                     for b in batches for g in b["groups"] for p, _, _ in g)
    print(f"plan: {len(batches)} batches; requests {n_req}; prompt tokens {prompt_tok:,}", flush=True)
    if a.dry_run:
        per = {}
        for b in batches:
            if b["kind"] == "measured":
                k = (b["length"], b["content"], b["level"])
                per[k] = per.get(k, 0) + sum(len(g) for g in b["groups"])
        for k in sorted(per):
            print(f"  {k[0]:>6} {k[1]:9s} c{k[2]:<2d} {per[k]:3d} requests")
        seeds = [s for b in batches for g in b["groups"] for _, s, _ in g]
        print(f"seeds unique: {len(seeds) == len(set(seeds)) or 'cached cell reuses none'}; "
              f"distinct {len(set(seeds))} of {len(seeds)}")
        return

    key = client.read_key(a.api_key_file)
    model = client.model_id(a.base_url, key)
    salt = a.nonce_salt or f"{a.label}:{time.time_ns()}"
    report = {"label": a.label, "base_url": a.base_url, "model": model, "block": "T",
              "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "client_sha256": hashlib.sha256((Path(__file__).parent / "client.py").read_bytes()).hexdigest(),
              "t_index_sha256": hashlib.sha256((client.PROMPTS / "T" / "index.json").read_bytes()).hexdigest(),
              "max_tokens": a.max_tokens, "temperature": a.temperature, "top_p": a.top_p, "nonce_salt": salt,
              "api_key": "file given" if a.api_key_file else "none", "args": {k: v for k, v in vars(a).items()
                                                                              if k != "api_key_file"},
              "plan_requests": n_req, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "gpu_before": client.gpu_snapshot(), "batches": []}
    cached_nonce = client.nonce_for(salt, "cached-cell")
    for b in batches:
        groups = [run_group(a, key, model, cells, b, g, salt,
                            fixed_nonce=cached_nonce if b["kind"] == "cached" else None) for g in b["groups"]]
        if b["kind"] == "cached":
            primer, groups = groups[0], groups[1:]
        res = {k: b[k] for k in ("kind", "rep", "length", "content", "level")}
        res["summary"] = summarize(groups)
        res["groups"] = groups
        if b["kind"] == "cached":
            res["primer"] = primer
        report["batches"].append(res)
        s = res["summary"]
        print(f"{a.label} {b['kind']:8s} rep{b['rep']:>2} {b['length']:>6} {b['content']:9s} c{b['level']:<2d} "
              f"agg {s.get('aggregate_tok_s', float('nan')):7.1f}  per-stream "
              f"{s.get('decode_tok_s_per_stream_median') or float('nan'):6.1f}  ttft "
              f"{s.get('ttft_median_s', float('nan')):7.3f}s  prefill {s.get('prefill_tok_s_median', float('nan')):8.0f}"
              f"  finish {s['finish_reasons']}  errors {s['errors']}", flush=True)
        client.write_atomic(a.out, report)
    report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    report["gpu_after"] = client.gpu_snapshot()
    report["errors_total"] = sum(b["summary"]["errors"] for b in report["batches"])
    client.write_atomic(a.out, report)


if __name__ == "__main__":
    main()
