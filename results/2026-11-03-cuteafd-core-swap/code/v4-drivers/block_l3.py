#!/usr/bin/env python3
"""Block L (long output, staged) for the K4 three-engine comparison. Standard library only.

Reuses the K3.25 Block L driver (stage0/drivers/block_l.py, frozen; imported read-only): prompt set and hash check
(load_prompts), contents, queue order, the per-position rate estimate (bucket_rates) and the receipt layout, so
the K3.25 analyzer (analyze_l.py) reads these receipts unchanged. What differs, and why:
  - caps and concurrency come from GRID.json: 2 concurrent (decision 5) for L1-L3, 1 for L3s; the L3 cap is
    the largest multiple of 1,024 <= 131,072 that fits 2 streams on every engine (grid rule 3);
  - top_k -1 sent on every request; one nonce salt shared by all engines;
  - seeds 840,000,000 + stage_idx*10^6 + content_idx*10^5 + prompt*10^3 + rep (L3s rep 9), so no K4 seed equals a
    Block T seed (the K3.25 740M base overlapped Block T's replicate-1 range).
Gate (unchanged): any HTTP error stops the stage (queued requests recorded as not_started), exit status 2. Run one
stage per invocation so the chain can check logs and memory between stages.

  block_l3.py --arm V --label V-r1 --out l/V-r1-L1.json --stages L1 [--api-key-file F] [--dry-run]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import k4common as K  # noqa: E402

client, _, block_l = K.import_stage0()
CONTENTS = block_l.CONTENTS
STAGE_IDX = block_l.STAGE_IDX


def stages_from_grid(grid):
    return {s["stage"]: (s["cap"], s["concurrency"]) for s in grid["L"]["stages"]}


def stage_queue(stage):
    si = STAGE_IDX[stage]
    b = K.SEED_BASE["L"]
    if stage == "L3s":
        return [(c, 0, 9, b + si * 1_000_000 + ci * 100_000 + 9) for ci, c in enumerate(CONTENTS)]
    return [(c, p, rep, b + si * 1_000_000 + ci * 100_000 + p * 1_000 + rep)
            for rep in range(2) for p in range(4) for ci, c in enumerate(CONTENTS)]


def run_one(a, key, model, prompts, stage, cap, item, salt, text_dir):
    c, p, rep, seed = item
    cell = prompts[(c, p)]
    nonce = client.nonce_for(salt, seed)
    body = K.chat_body(model, client.with_nonce(cell["messages"], nonce), cap, seed)
    rid = f"{a.label}-{stage}-{c}-p{p}-r{rep}"
    rec = client.stream_chat(a.base_url, key, body, keep_text=True, keep_chunks=True, read_timeout=a.read_timeout)
    payload = {k: rec.pop(k) for k in ("content", "reasoning", "chunk_t", "chunk_chars", "chunk_kind")}
    rec.update(request_id=rid, stage=stage, cap=cap, content=c, prompt_index=p, rep=rep, seed=seed, nonce=nonce,
               prompt_id=cell["id"], prompt_sha256=cell["sha256"], thinking=K.THINKING,
               expected_prompt_tokens=cell["prompt_tokens"]["template_with_nonce"])
    u = rec.get("usage") or {}
    rec["completion_tokens"] = u.get("completion_tokens")
    rec["prompt_tokens"] = u.get("prompt_tokens")
    rec["reasoning_tokens"] = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if rec["t_first"] is not None:
        rec["ttft_s"] = rec["t_first"] - rec["t_send"]
        if rec["completion_tokens"] and rec["t_last"] > rec["t_first"]:
            rec["decode_tok_s"] = (rec["completion_tokens"] - 1) / (rec["t_last"] - rec["t_first"])
    rec["hit_cap"] = bool(rec["completion_tokens"] is not None and rec["completion_tokens"] >= cap)
    rec["position_rates"] = block_l.bucket_rates(rec, payload)
    payload["request_id"] = rid
    raw = gzip.compress(json.dumps(payload).encode(), mtime=0)
    f = text_dir / f"{rid}.json.gz"
    f.write_bytes(raw)
    rec["text_file"] = f.name
    rec["text_file_sha256"] = hashlib.sha256(raw).hexdigest()
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, choices=list(K.ENGINES))
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stages", nargs="+", required=True, choices=["L1", "L2", "L3", "L3s"])
    ap.add_argument("--base-url", default=K.BASE_URL)
    ap.add_argument("--api-key-file")
    ap.add_argument("--grid", default=str(K.GRID))
    ap.add_argument("--read-timeout", type=float, default=14400)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    grid = json.loads(Path(a.grid).read_text())
    if grid.get("status") != "FILLED":
        sys.exit("grid not filled")
    caps = stages_from_grid(grid)
    prompts = block_l.load_prompts()
    stages = [s for s in ("L1", "L2", "L3", "L3s") if s in a.stages]
    queues = {s: stage_queue(s) for s in stages}
    all_seeds = [it[3] for s in ("L1", "L2", "L3", "L3s") for it in stage_queue(s)]
    print("plan:", {s: (len(q), "cap", caps[s][0], "x", caps[s][1]) for s, q in queues.items()},
          "seeds distinct over all stages", len(all_seeds) == len(set(all_seeds)), flush=True)
    if a.dry_run:
        for s, q in queues.items():
            worst = sum(caps[s][0] for _ in q)
            print(f"{s}: {len(q)} requests, cap {caps[s][0]}, {caps[s][1]} concurrent; worst case "
                  f"{worst:,} output tokens; largest prompt "
                  f"{max(prompts[(c, p)]['prompt_tokens']['template_with_nonce'] for c, p, _, _ in q)}")
        return 0
    K.require_frozen([__file__, K.__file__])
    key = K.read_key(a.api_key_file)
    model = client.model_id(a.base_url, key)
    salt = K.NONCE_SALT["L"]
    out = Path(a.out)
    text_dir = out.with_name(out.stem + "-texts")
    text_dir.mkdir(parents=True, exist_ok=True)
    report = {"label": a.label, "arm": a.arm, "engine": K.ENGINES[a.arm]["name"], "base_url": a.base_url,
              "model": model, "block": "L", "driver_sha256": K.sha256_file(__file__),
              "k325_block_l_sha256": K.sha256_file(block_l.__file__), "client_sha256": K.sha256_file(client.__file__),
              "l_index_sha256": K.sha256_file(client.PROMPTS / "L" / "index.json"), "grid_sha256": K.sha256_file(a.grid),
              "temperature": K.TEMPERATURE, "top_p": K.TOP_P, "top_k": K.TOP_K, "nonce_salt": salt,
              "text_dir": text_dir.name, "api_key": "file given" if a.api_key_file else "none", "stages": [],
              "started": K.now(), "gpu_before": client.gpu_snapshot()}
    lock = threading.Lock()
    exit_code = 0
    for s in stages:
        cap, conc = caps[s]
        stop = threading.Event()
        st = {"stage": s, "cap": cap, "concurrency": conc, "started": K.now(), "requests": [], "not_started": []}
        report["stages"].append(st)

        def task(item, s=s, st=st, stop=stop, cap=cap):
            if stop.is_set():
                with lock:
                    st["not_started"].append({"content": item[0], "prompt_index": item[1], "rep": item[2],
                                              "seed": item[3], "reason": "gate stop: earlier HTTP error"})
                return
            rec = run_one(a, key, model, prompts, s, cap, item, salt, text_dir)
            with lock:
                if rec["error"]:
                    stop.set()
                st["requests"].append(rec)
                print(f"{a.label} {s} {rec['request_id']:40s} finish {rec['finish_reason']!s:7s} "
                      f"tokens {rec['completion_tokens']!s:>7}  decode {rec.get('decode_tok_s') or float('nan'):6.1f}"
                      f"  error {rec['error']}", flush=True)
                K.write_atomic(out, report)

        with ThreadPoolExecutor(max_workers=conc) as pool:
            list(pool.map(task, queues[s]))
        st["finished"] = K.now()
        st["errors"] = sum(1 for r in st["requests"] if r["error"])
        st["gate"] = "stopped: HTTP error" if stop.is_set() else "passed (0 errors)"
        K.write_atomic(out, report)
        print(f"{a.label} stage {s}: {len(st['requests'])} run, {len(st['not_started'])} not started, "
              f"{st['errors']} errors -> {st['gate']}", flush=True)
        if stop.is_set():
            exit_code = 2
            break
    report["finished"] = K.now()
    report["gpu_after"] = client.gpu_snapshot()
    K.write_atomic(out, report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
