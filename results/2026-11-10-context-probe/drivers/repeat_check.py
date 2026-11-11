#!/usr/bin/env python3
"""Repeat check: is greedy output the same when the engine decodes it alone and in a batch? Standard library only.

  repeat_check.py run --arm hqa --run-tag r0 [--item trace-000-16k] [--serial 4] [--repeats 256]
                      [--concurrency 8] [--max-tokens 768] [--api-key-file ...]
  repeat_check.py report --arm hqa --run-tag r0

One byte-identical prompt (a pilot item, no nonce), temperature 0 (greedy on this engine and on vLLM), thinking
on. First `serial` requests one at a time: the reference, and the single-stream repeat floor. Then `repeats`
requests at `concurrency`. Every reply is cut at `max_tokens`; its reasoning and content are hashed. The report
counts distinct outputs, and for every reply that differs from the reference the character offset of the first
difference. The other bit-identity checks in this probe (depth profile, turn check) are single-stream; this one
puts the same request in a decode batch with seven copies of itself.

Receipts under ../repeat/<arm>/<run-tag>/: requests.jsonl, texts/<sha256>.json.gz (one per distinct output),
report.json. Exploratory: no FROZEN.json check. A request error is recorded and counted, never retried.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probelib as P  # noqa: E402
import tasklib as T  # noqa: E402

KEEP = ("status", "error_kind", "error", "finish_reason", "finish_detail", "prompt_tokens", "completion_tokens",
        "reasoning_tokens", "cached_tokens", "prefix_cache_source", "ttft_s", "dur_s", "decode_tok_s", "wall_start")


def out_dir(a) -> Path:
    return P.RUN / "repeat" / a.arm / a.run_tag


def load_item(name: str) -> dict:
    ident, length = name.rsplit("-", 1)
    index = json.loads((P.ITEMS / "pilot" / "index.json").read_text())
    row = next(r for r in index["items"] if r["id"] == ident and r["length"] == length)
    path = P.ITEMS / "pilot" / row["file"]
    if P.sha256_file(path) != row["file_sha256"]:
        sys.exit(f"item file changed since it was generated: {path}")
    return json.loads(path.read_text())


def run(a) -> int:
    out = out_dir(a)
    if (out / "requests.jsonl").exists():
        sys.exit(f"{out} already holds a run: use another --run-tag")
    key = P.read_key(a.api_key_file)
    client = P.stage0_client()
    doc = P.models_doc(a.base_url, key)
    model = doc["data"][0]["id"]
    messages = T.single_messages(load_item(a.item))
    body = P.chat_body(model, messages, a.max_tokens, 0)
    body.update(temperature=0.0, top_p=1.0)           # greedy; the seed is sent but unused
    (out / "texts").mkdir(parents=True, exist_ok=True)
    report = {"arm": a.arm, "run_tag": a.run_tag, "exploratory": True, "args": vars(a), "model": model,
              "models_doc": doc, "driver_sha256": P.sha256_file(__file__), "probelib_sha256": P.sha256_file(P.__file__),
              "prompt_sha256": P.sha256_text(json.dumps(messages, sort_keys=True)),
              "settings": {k: body[k] for k in ("temperature", "top_p", "top_k", "seed", "chat_template_kwargs")},
              "started": P.now_iso(), "gpu_start": client.gpu_snapshot(), "complete": False}
    P.write_json_atomic(out / "report.json", report)
    log = P.JsonlWriter(out / "requests.jsonl")
    seen: set[str] = set()

    def one(phase: str, i: int) -> None:
        rec = P.stream_chat(a.base_url, body, key=key, read_timeout=a.timeout)
        text = json.dumps({"reasoning": rec.get("reasoning", ""), "content": rec.get("content", "")})
        h = P.sha256_text(text)
        if h not in seen:                              # a rare double write of the same file is harmless
            seen.add(h)
            with gzip.open(out / "texts" / f"{h}.json.gz", "wt") as f:
                f.write(text)
        log.write({"phase": phase, "i": i, "sha256": h, **{k: rec.get(k) for k in KEEP}})

    t0 = time.time()
    try:
        for i in range(a.serial):
            one("serial", i)
        print(f"serial done ({time.time() - t0:.0f} s)", flush=True)
        with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
            list(pool.map(lambda i: one("batch", i), range(a.repeats)))
    finally:
        log.close()
        report.update(finished=P.now_iso(), wall_s=round(time.time() - t0, 1), gpu_end=client.gpu_snapshot(),
                      complete=len(P.read_jsonl(out / "requests.jsonl")) == a.serial + a.repeats)
        P.write_json_atomic(out / "report.json", report)
    return summarize(a)


def first_diff(x: str, y: str) -> int:
    n = min(len(x), len(y))
    return next((k for k in range(n) if x[k] != y[k]), n)


def summarize(a) -> int:
    out = out_dir(a)
    rows = P.read_jsonl(out / "requests.jsonl")
    ok = [r for r in rows if r["status"] == "ok"]
    serial = [r for r in ok if r["phase"] == "serial"]
    batch = [r for r in ok if r["phase"] == "batch"]
    if not serial:
        sys.exit("no completed serial request: nothing to compare against")
    ref = serial[0]["sha256"]

    def text(h):
        d = json.loads(gzip.open(out / "texts" / f"{h}.json.gz", "rt").read())
        return d["reasoning"] + "\x00" + d["content"]

    ref_text = text(ref)
    variants = Counter(r["sha256"] for r in ok)
    diff_at = {h: first_diff(ref_text, text(h)) for h in variants if h != ref}
    speeds = sorted(r["decode_tok_s"] for r in batch if r.get("decode_tok_s"))
    s = {"requests": len(rows), "errors": len(rows) - len(ok), "error_kinds": dict(Counter(
             r.get("error_kind") or r["status"] for r in rows if r["status"] != "ok")),
         "reference_sha256": ref, "reference_chars": len(ref_text),
         "serial": {"n": len(serial), "equal_reference": sum(r["sha256"] == ref for r in serial)},
         "batch": {"n": len(batch), "equal_reference": sum(r["sha256"] == ref for r in batch),
                   "distinct_outputs": len({r["sha256"] for r in batch}),
                   "decode_tok_s_median_per_stream": speeds[len(speeds) // 2] if speeds else None},
         "variants": [{"sha256": h, "count": c, "first_difference_char": diff_at.get(h)}
                      for h, c in variants.most_common()],
         "finish": dict(Counter(P.finish_class(r) for r in ok)),
         "completion_tokens": dict(Counter(r["completion_tokens"] for r in ok)),
         "cached_tokens": dict(Counter(str(r["cached_tokens"]) for r in ok))}
    report = json.loads((out / "report.json").read_text())
    report["summary"] = s
    P.write_json_atomic(out / "report.json", report)
    print(json.dumps(s, indent=1))
    return 0 if report.get("complete") and not s["errors"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "report"):
        s = sub.add_parser(name)
        s.add_argument("--arm", required=True)
        s.add_argument("--run-tag", required=True)
        if name == "run":
            s.add_argument("--item", default="trace-000-16k", help="pilot item id and length")
            s.add_argument("--serial", type=int, default=4)
            s.add_argument("--repeats", type=int, default=256)
            s.add_argument("--concurrency", type=int, default=8)
            s.add_argument("--max-tokens", type=int, default=768)
            s.add_argument("--base-url", default=P.BASE_URL)
            s.add_argument("--api-key-file", default="")
            s.add_argument("--timeout", type=float, default=1800.0)
    a = ap.parse_args()
    return run(a) if a.cmd == "run" else summarize(a)


if __name__ == "__main__":
    sys.exit(main())
