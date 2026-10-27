#!/usr/bin/env python3
"""Block L (long output, staged) driver for the CuteAFD v3.0.1 vs vLLM v0.9.2 protocol. Standard library only.

Stages (max_tokens caps): L1 8,192 / L2 32,768 / L3 131,072, plus L3s, the 1-stream subset at the L3 cap.
  L1, L2, L3: 32 requests each = 4 contents x 4 prompts x 2 seeds, queued through a semaphore of 8
              (8 worker threads; a request starts when a slot frees). Queue order: seed rep 0 then 1; within a
              rep prompt 0..3; within a prompt prose, code, reasoning, json.
  L3s:        prompt 0 of each content, one request at a time (4 requests).
Prompts: ../prompts/L/<content>/p<i>.json (hash-checked against ../prompts/L/index.json). Thinking on for
reasoning, off otherwise (chat_template_kwargs.enable_thinking). Every request gets its own nonce first line.

Gate: any HTTP error (non-200 status, connection error, or an error event in the stream) stops the stage: no
further queued request starts (they are recorded as not_started), requests in flight run to completion, and no
later stage runs. The process then exits with status 2. The protocol's other gates (logs clean, no memory
warnings) are the maintainer's check between invocations: run one stage per invocation to apply them.

Seeds (identical for both engines): 740,000,000 + stage_idx*1,000,000 + content_idx*100,000 + prompt*1,000 + rep
(stage_idx L1=0, L2=1, L3=2, L3s=3; L3s uses rep 9).

Per request (receipt JSON): seed, nonce, prompt id, cap, finish reason, usage (completion tokens), reasoning and
content character counts, TTFT, overall decode tok/s, decode tok/s per 2,048-token position bucket estimated
from chunk timestamps (position = cumulative characters x completion_tokens / total characters; analyze_l.py
recomputes it exactly by re-tokenizing), error. Full text (reasoning, content, chunk timestamps and sizes) is
saved gzip-compressed to <out stem>-texts/<request id>.json.gz with its SHA256 in the receipt.

Usage:
  block_l.py --base-url http://127.0.0.1:8001 --label C1 --out <runs>/.../C1-block-l.json \
             --stages L1 [L2 L3 L3s] [--api-key-file FILE] [--dry-run]
"""
import os as _os_a2
THINKING_ALL_ON = _os_a2.environ.get("A2_THINKING", "on") == "on"  # amendment A2 (2026-10-26)
import argparse
import gzip
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import client  # noqa: E402

STAGES = {"L1": 8192, "L2": 32768, "L3": 131072, "L3s": 131072}
STAGE_IDX = {"L1": 0, "L2": 1, "L3": 2, "L3s": 3}
CONTENTS = ["prose", "code", "reasoning", "json"]
CONCURRENCY = 8
BUCKET = 2048


def load_prompts():
    idx = json.loads((client.PROMPTS / "L" / "index.json").read_text())
    out = {}
    for c in idx["prompts"]:
        f = client.PROMPTS / c["file"]
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h != c["sha256"]:
            sys.exit(f"prompt file changed since the index was written: {c['file']}")
        out[(c["content"], c["prompt_index"])] = json.loads(f.read_text()) | {"sha256": h}
    return out


def stage_queue(stage):
    si = STAGE_IDX[stage]
    if stage == "L3s":
        return [(c, 0, 9, 740_000_000 + si * 1_000_000 + ci * 100_000 + 9) for ci, c in enumerate(CONTENTS)]
    q = []
    for rep in range(2):
        for p in range(4):
            for ci, c in enumerate(CONTENTS):
                q.append((c, p, rep, 740_000_000 + si * 1_000_000 + ci * 100_000 + p * 1_000 + rep))
    return q


def bucket_rates(rec, payload):
    """Approximate decode tok/s per BUCKET-token position bucket (char-proportional positions)."""
    n = (rec.get("usage") or {}).get("completion_tokens")
    total = sum(payload.get("chunk_chars") or [])
    if not n or not total or not payload.get("chunk_t"):
        return None
    scale, cum, t_at = n / total, 0, []
    for t, c in zip(payload["chunk_t"], payload["chunk_chars"]):
        cum += c
        pos = cum * scale
        b = int(pos // BUCKET)
        while len(t_at) <= b:
            t_at.append(t)  # t_at[k]: time the stream first reached position k * BUCKET (t_at[0]: first chunk)
    out = []
    for k in range(1, len(t_at)):
        dt = t_at[k] - t_at[k - 1]
        out.append({"start": (k - 1) * BUCKET, "tok_s": round(BUCKET / dt, 2) if dt > 0 else None})
    return {"bucket_tokens": BUCKET, "method": "char-proportional estimate", "buckets": out}


def run_one(a, key, model, prompts, stage, item, salt, text_dir):
    c, p, rep, seed = item
    cell = prompts[(c, p)]
    nonce = client.nonce_for(salt, seed)
    body = {"model": model, "messages": client.with_nonce(cell["messages"], nonce), "max_tokens": STAGES[stage],
            "temperature": a.temperature, "top_p": a.top_p, "seed": seed, "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": (True if THINKING_ALL_ON else bool(cell["thinking"]))}}
    rid = f"{a.label}-{stage}-{c}-p{p}-r{rep}"
    rec = client.stream_chat(a.base_url, key, body, keep_text=True, keep_chunks=True, read_timeout=a.read_timeout)
    # move the text out first: the receipt's "content" field is the content type
    payload = {k: rec.pop(k) for k in ("content", "reasoning", "chunk_t", "chunk_chars", "chunk_kind")}
    rec.update(request_id=rid, stage=stage, cap=STAGES[stage], content=c, prompt_index=p, rep=rep, seed=seed,
               nonce=nonce, prompt_id=cell["id"], prompt_sha256=cell["sha256"], thinking=(True if THINKING_ALL_ON else bool(cell["thinking"])))
    u = rec.get("usage") or {}
    rec["completion_tokens"] = u.get("completion_tokens")
    rec["prompt_tokens"] = u.get("prompt_tokens")
    if rec["t_first"] is not None:
        rec["ttft_s"] = rec["t_first"] - rec["t_send"]
        if rec["completion_tokens"] and rec["t_last"] > rec["t_first"]:
            rec["decode_tok_s"] = (rec["completion_tokens"] - 1) / (rec["t_last"] - rec["t_first"])
    rec["hit_cap"] = bool(rec["completion_tokens"] is not None and rec["completion_tokens"] >= STAGES[stage])
    rec["position_rates"] = bucket_rates(rec, payload)
    payload["request_id"] = rid
    raw = gzip.compress(json.dumps(payload).encode(), mtime=0)
    f = text_dir / f"{rid}.json.gz"
    f.write_bytes(raw)
    rec["text_file"] = f.name
    rec["text_file_sha256"] = hashlib.sha256(raw).hexdigest()
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--label", required=True)
    ap.add_argument("--api-key-file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stages", nargs="+", required=True, choices=list(STAGES))
    ap.add_argument("--temperature", type=float, default=client.DEFAULT_TEMPERATURE)
    ap.add_argument("--top-p", type=float, default=client.DEFAULT_TOP_P)
    ap.add_argument("--read-timeout", type=float, default=1800, help="seconds without a byte before giving up")
    ap.add_argument("--nonce-salt", help="default: label + start time")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    prompts = load_prompts()
    stages = [s for s in STAGES if s in a.stages]
    queues = {s: stage_queue(s) for s in stages}
    print("plan:", {s: len(q) for s, q in queues.items()}, "total", sum(map(len, queues.values())), flush=True)
    if a.dry_run:
        for s, q in queues.items():
            print(s, "cap", STAGES[s], "concurrency", 1 if s == "L3s" else CONCURRENCY)
            for it in q:
                print("  ", it, prompts[(it[0], it[1])]["id"], "prompt tokens",
                      prompts[(it[0], it[1])]["prompt_tokens"]["template_with_nonce"])
        seeds = [it[3] for q in queues.values() for it in q]
        print("seeds unique:", len(seeds) == len(set(seeds)))
        return

    key = client.read_key(a.api_key_file)
    model = client.model_id(a.base_url, key)
    salt = a.nonce_salt or f"{a.label}:{time.time_ns()}"
    out = Path(a.out)
    text_dir = out.with_name(out.stem + "-texts")
    text_dir.mkdir(parents=True, exist_ok=True)
    report = {"label": a.label, "base_url": a.base_url, "model": model, "block": "L",
              "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "client_sha256": hashlib.sha256((Path(__file__).parent / "client.py").read_bytes()).hexdigest(),
              "l_index_sha256": hashlib.sha256((client.PROMPTS / "L" / "index.json").read_bytes()).hexdigest(),
              "temperature": a.temperature, "top_p": a.top_p, "nonce_salt": salt, "text_dir": text_dir.name,
              "api_key": "file given" if a.api_key_file else "none", "stages": [],
              "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "gpu_before": client.gpu_snapshot()}
    lock = threading.Lock()
    exit_code = 0
    for s in stages:
        stop = threading.Event()
        st = {"stage": s, "cap": STAGES[s], "concurrency": 1 if s == "L3s" else CONCURRENCY,
              "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "requests": [], "not_started": []}
        report["stages"].append(st)

        def task(item, s=s, st=st, stop=stop):
            if stop.is_set():
                with lock:
                    st["not_started"].append({"content": item[0], "prompt_index": item[1], "rep": item[2],
                                              "seed": item[3], "reason": "gate stop: earlier HTTP error"})
                return
            rec = run_one(a, key, model, prompts, s, item, salt, text_dir)
            with lock:
                if rec["error"]:
                    stop.set()
                st["requests"].append(rec)
                print(f"{a.label} {s} {rec['request_id']:40s} finish {rec['finish_reason']!s:7s} "
                      f"tokens {rec['completion_tokens']!s:>7}  reasoning chars {rec['reasoning_chars']:>7}  "
                      f"decode {rec.get('decode_tok_s') or float('nan'):6.1f}  error {rec['error']}", flush=True)
                client.write_atomic(out, report)

        with ThreadPoolExecutor(max_workers=st["concurrency"]) as pool:
            list(pool.map(task, queues[s]))
        st["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        st["errors"] = sum(1 for r in st["requests"] if r["error"])
        st["gate"] = "stopped: HTTP error" if stop.is_set() else "passed (0 errors)"
        client.write_atomic(out, report)
        print(f"{a.label} stage {s}: {len(st['requests'])} run, {len(st['not_started'])} not started, "
              f"{st['errors']} errors -> {st['gate']}", flush=True)
        if stop.is_set():
            exit_code = 2
            break
    report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    report["gpu_after"] = client.gpu_snapshot()
    client.write_atomic(out, report)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
