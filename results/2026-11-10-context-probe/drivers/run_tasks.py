#!/usr/bin/env python3
"""Layers 2 and 3 of the context probe: graded exact-match tasks at four context lengths, delivered as one
prompt (`--mode single`) or as the same records split over turns (`--mode turns`). Standard library only.

  run_tasks.py --arm hqa --run-tag r0 --set measured --mode single --rep 0 --concurrency 2 --max-tokens N
  run_tasks.py --arm hqa --run-tag r0 --set measured --mode turns --parts 8 --rep 0 ...
  ... --dry-run            builds every request body, sends nothing

single: one cold request per item (the nonce line makes every prompt new to the prefix cache).
turns:  one session per item. `parts` user messages carry the records in order, each answered by the engine
        (asked for `ACK <k>`); the question is the last user message. Every assistant turn is sent back exactly
        as the engine produced it (content and reasoning_content), so later turns can reuse the engine's cached
        state; whether they did is read from cached_tokens / prefix_cache_source, recorded per turn.

Receipts under ../tasks/<arm>/<run-tag>/<mode>[-p<parts>]-rep<rep>/: requests.jsonl (one line per request),
texts/<unit>.json.gz (reply text of every turn), report.json. A request error stops the run (no retry).
Scoring is tasklib.score on the visible content of the final reply; nothing else is read from the reply.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probelib as P  # noqa: E402
import tasklib as T  # noqa: E402


def load_units(set_dir: Path, lengths, families, limit) -> tuple[list[dict], dict]:
    index = json.loads((set_dir / "index.json").read_text())
    rows = [r for r in index["items"] if r["length"] in lengths and r["family"] in families]
    rows.sort(key=lambda r: (r["index"], P.FAMILY_INDEX[r["family"]], P.LENGTH_INDEX[r["length"]]))
    if limit:
        keep = sorted({r["index"] for r in rows})[:limit]
        rows = [r for r in rows if r["index"] in keep]
    return rows, index


def load_item(set_dir: Path, row: dict) -> dict:
    path = set_dir / row["file"]
    if P.sha256_file(path) != row["file_sha256"]:
        sys.exit(f"item file changed since it was generated: {path}")
    return json.loads(path.read_text())


def run_unit(a, client, model, key, item, unit_id, stop, log, texts_dir) -> bool:
    """One item: a single request, or a session of parts + question. Returns False when a request failed."""
    session = uuid.uuid4().hex[:12]
    users = T.turn_user_contents(item, a.parts) if a.mode == "turns" else [T.single_content(item)]
    seed0 = P.seed_for(a.mode, a.rep, item["family"], item["index"], item["length"])
    nonce = client.nonce_for(f"{P.SALT}:{a.mode}", seed0)
    messages: list[dict] = []
    texts = []
    failed = False
    for turn, user in enumerate(users):
        if stop.is_set():
            failed = True
            break
        final = turn == len(users) - 1
        messages.append({"role": "user", "content": user})
        body = P.chat_body(model, client.with_nonce(messages, nonce), a.max_tokens if final else a.ack_max_tokens,
                           seed0 + turn)
        rec = P.stream_chat(a.base_url, body, key=key, read_timeout=a.timeout, stop_event=stop)
        content, reasoning = rec.pop("content"), rec.pop("reasoning")
        out = {"unit": unit_id, "session": session, "item": item["id"], "family": item["family"],
               "index": item["index"], "length": item["length"], "mode": a.mode, "parts": a.parts if a.mode == "turns" else 0,
               "rep": a.rep, "turn": turn, "final": final, "seed": seed0 + turn, "nonce": nonce,
               "max_tokens": body["max_tokens"], "content_sha256": P.sha256_text(content),
               "content_chars": len(content), "reasoning_chars": len(reasoning), "finish_class": P.finish_class(rec),
               **rec}
        if final:
            out["score"] = T.score(item["answer"], content) if rec["status"] == "ok" else None
        else:
            out["ack_ok"] = content.strip() == f"ACK {turn + 1}"
        log.write(out)
        texts.append({"turn": turn, "content": content, "reasoning": reasoning})
        if rec["status"] != "ok":
            failed = True
            stop.set()
            print(f"  {unit_id} turn {turn}: {rec['status']} {rec['error_kind']} {rec['error']}", flush=True)
            break
        # the engine's own turn, unchanged: the template re-renders reasoning_content when clear_thinking is false
        messages.append({"role": "assistant", "content": content, "reasoning_content": reasoning})
    with gzip.open(texts_dir / f"{unit_id}.{session}.json.gz", "wt") as f:
        json.dump({"unit": unit_id, "session": session, "turns": texts}, f)
    return not failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, help="label of the engine setting being served (e.g. hqa, compact)")
    ap.add_argument("--run-tag", required=True, help="one launch of the arm, e.g. r0")
    ap.add_argument("--set", default="measured", help="item set under ../items (pilot, measured)")
    ap.add_argument("--mode", required=True, choices=["single", "turns"])
    ap.add_argument("--parts", type=int, default=8, help="turns mode: record messages before the question")
    ap.add_argument("--rep", type=int, default=0, help="repeat index: a distinct seed block")
    ap.add_argument("--lengths", nargs="+", default=list(P.LENGTH_INDEX), choices=list(P.LENGTH_INDEX))
    ap.add_argument("--families", nargs="+", default=list(P.FAMILY_INDEX), choices=list(P.FAMILY_INDEX))
    ap.add_argument("--limit", type=int, default=0, help="first N item indices only")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, required=True, help="cap of the answering request")
    ap.add_argument("--ack-max-tokens", type=int, default=4096, help="cap of each part's reply (turns mode)")
    ap.add_argument("--base-url", default=P.BASE_URL)
    ap.add_argument("--api-key-file", default="")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--exploratory", action="store_true", help="pilot: runs without FROZEN.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.mode == "turns" and not 1 <= a.parts <= 62:
        sys.exit("--parts must be 1..62 (64 seed slots per item)")

    set_dir = P.ITEMS / a.set
    rows, index = load_units(set_dir, a.lengths, a.families, a.limit)
    sub = f"{a.mode}{f'-p{a.parts}' if a.mode == 'turns' else ''}-rep{a.rep}"
    out = P.RUN / "tasks" / a.arm / a.run_tag / sub
    per_unit = a.parts + 1 if a.mode == "turns" else 1
    print(f"{a.arm} {a.run_tag} {sub}: {len(rows)} items, {len(rows) * per_unit} requests, "
          f"{sum(r['content_tokens'] for r in rows):,} content tokens, concurrency {a.concurrency}", flush=True)
    if a.dry_run:
        client = P.stage0_client()
        for r in rows[:4]:
            item = load_item(set_dir, r)
            users = T.turn_user_contents(item, a.parts) if a.mode == "turns" else [T.single_content(item)]
            s = P.seed_for(a.mode, a.rep, r["family"], r["index"], r["length"])
            print(f"  {r['id']}-{r['length']}: {len(users)} user messages, {sum(map(len, users)):,} chars, seed {s}, "
                  f"nonce {client.nonce_for(f'{P.SALT}:{a.mode}', s)}")
        seeds = [P.seed_for(a.mode, a.rep, r["family"], r["index"], r["length"]) for r in rows]
        assert len(set(seeds)) == len(seeds), "seed collision"
        return 0
    frozen = P.RUN / "FROZEN.json"
    if not a.exploratory:
        if not frozen.exists():
            sys.exit("FROZEN.json missing: measured requests are not allowed before the freeze (use --exploratory)")
        fz = json.loads(frozen.read_text())["sha256"]
        for f in (__file__, P.__file__, T.__file__, set_dir / "index.json"):
            if fz.get(str(Path(f).resolve())) != P.sha256_file(f):
                sys.exit(f"{f} is not in FROZEN.json or changed since the freeze")

    key = P.read_key(a.api_key_file)
    client = P.stage0_client()
    doc = P.models_doc(a.base_url, key)
    model = doc["data"][0]["id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "texts").mkdir(exist_ok=True)
    done = {r["unit"] for r in P.read_jsonl(out / "requests.jsonl") if r.get("final") and r["status"] == "ok"}
    log = P.JsonlWriter(out / "requests.jsonl")
    report = {"arm": a.arm, "run_tag": a.run_tag, "mode": a.mode, "parts": a.parts if a.mode == "turns" else 0,
              "rep": a.rep, "set": a.set, "exploratory": a.exploratory, "args": vars(a), "model": model,
              "models_doc": doc, "items_index_sha256": P.sha256_file(set_dir / "index.json"),
              "generator_sha256": index["generator_sha256"], "driver_sha256": P.sha256_file(__file__),
              "probelib_sha256": P.sha256_file(P.__file__), "tasklib_sha256": P.sha256_file(T.__file__),
              "settings": {"temperature": P.TEMPERATURE, "top_p": P.TOP_P, "top_k": P.TOP_K,
                           "chat_template_kwargs": P.TEMPLATE_KWARGS, "salt": P.SALT},
              "started": P.now_iso(), "gpu_start": client.gpu_snapshot(), "resumed_units": len(done),
              "complete": False}
    try:
        report["stats_start"] = P.get_json(a.base_url.rstrip("/") + "/v1/stats", key)
    except Exception as e:  # recorded, never fatal
        report["stats_start"] = f"unavailable: {e!r}"
    P.write_json_atomic(out / "report.json", report)

    stop = threading.Event()
    todo = [r for r in rows if f"{r['id']}-{r['length']}" not in done]
    t0 = time.time()
    n_ok = 0
    lock = threading.Lock()

    def work(r):
        nonlocal n_ok
        if stop.is_set():
            return
        unit = f"{r['id']}-{r['length']}"
        ok = run_unit(a, client, model, key, load_item(set_dir, r), unit, stop, log, out / "texts")
        with lock:
            n_ok += ok
            print(f"[{n_ok}/{len(todo)}] {unit} {'ok' if ok else 'FAILED'} ({time.time() - t0:.0f} s)", flush=True)

    try:
        with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
            list(pool.map(work, todo))
    finally:
        log.close()
        report.update(finished=P.now_iso(), wall_s=round(time.time() - t0, 1), units_run=n_ok,
                      units_planned=len(todo), complete=n_ok == len(todo) and not stop.is_set(),
                      gpu_end=client.gpu_snapshot())
        try:
            report["stats_end"] = P.get_json(a.base_url.rstrip("/") + "/v1/stats", key)
        except Exception as e:
            report["stats_end"] = f"unavailable: {e!r}"
        P.write_json_atomic(out / "report.json", report)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
