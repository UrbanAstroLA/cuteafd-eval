#!/usr/bin/env python3
"""Layer 3 engine check of the context probe: is a conversation's next-token distribution the same when the
history arrives through the prefix cache (earlier replies written by decode steps and kept as a Turn snapshot) as
when the same token ids are prefilled cold? Upstream's `cache_exact` baseline shows a snapshot restore is
bit-exact against the live state at short length; it does not compare decode-written history with the same tokens
prefilled, and that is what a multi-turn user gets versus a one-shot user.

All requests go through POST /v1/bench/probe (ENABLE_BENCH=on, API key, prefix cache ON: a serving config plus
`--set ENABLE_BENCH=on --set API_KEY_FILE=...`), one at a time (the route is exclusive).

  turn_check.py run --arm hqa --run-tag r0 --item ledger-000-16k --mode single --max-tokens 16384
  turn_check.py run --arm hqa --run-tag r0 --item ledger-000-64k --mode turns --parts 8 --max-tokens 16384
  turn_check.py report --arm hqa --run-tag r0

Legs for one conversation (user messages U0..Un; single mode: the item, then a fixed follow-up; turns mode: the
item's records in `parts` messages, then its question):
  h0..h(n-1)   the history turns, as served (drafts on, the protocol's sampling, distinct seeds); each reply goes
               back verbatim (content + reasoning_content). Per turn: do the re-rendered ids reproduce the previous
               prompt + generated ids (first difference otherwise), and how many tokens the cache restored.
  live         the last user message, drafts off, greedy, the rows the first K tokens are selected from recorded.
  cold-a/b     the live leg's exact prompt ids, cold (no cache lookup), same settings. a vs b is the floor.
  replay-p     cold, `cold_steps` all prefill but cut at every turn frontier (the cut positions alone).
  replay-<w>   cold, `cold_steps` with every earlier reply run as decode steps of w rows (decode-written history,
               deterministic geometry).
Rows are compared pairwise up to the first differing generated token (after it the two legs condition on
different text): equal hashes, top-1, KL (exact from dumps with --dump-root, else a top-20 lower bound).
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probelib as P  # noqa: E402
import tasklib as T  # noqa: E402

OUT = P.RUN / "turncheck"
USER, ASSISTANT, THINK = 154827, 154828, 154841
FOLLOWUP = "Check the result against the records once more, then give the final ANSWER line again."
PAIRS = [("cold-a", "cold-b", "floor: cold twice"), ("cold-a", "replay-p", "prefill cut at turn frontiers"),
         ("replay-p", "replay-{w}", "replies written by {w}-row decode steps"),
         ("replay-{w}", "live", "live cache path vs {w}-row replay"), ("cold-a", "live", "live cache path vs cold")]


def load_item(set_name: str, item_id: str) -> dict:
    index = json.loads((P.ITEMS / set_name / "index.json").read_text())
    for it in index["items"]:
        if f"{it['id']}-{it['length']}" == item_id:
            return json.loads((P.ITEMS / set_name / it["file"]).read_text()) | {"_meta": it}
    sys.exit(f"{item_id} is not in items/{set_name}")


def user_messages(item: dict, mode: str, parts: int) -> list[str]:
    return [T.single_content(item), FOLLOWUP] if mode == "single" else T.turn_user_contents(item, parts)


def reply_spans(ids: list[int]) -> list[tuple[int, int]]:
    """[start, end) of every earlier assistant reply in a rendered prompt: after `<|assistant|>` (and the `<think>`
    the generation prompt carried) up to the next `<|user|>`. The final `<|assistant|>` opens the new turn."""
    marks = [j for j, t in enumerate(ids) if t == ASSISTANT][:-1]
    spans = []
    for j in marks:
        start = j + 2 if ids[j + 1] == THINK else j + 1
        end = next(k for k in range(start, len(ids)) if ids[k] == USER)
        if end > start:
            spans.append((start, end))
    return spans


def cold_steps(n: int, spans, width, prefill_rows: int) -> list[dict]:
    """Prefill in `prefill_rows` chunks, cut at every reply span; the spans themselves as decode steps of `width`
    rows, or as prefill when width is None. Ends with a prefill step at n (the engine requires it)."""
    out, pos = [], 0

    def run(end, rows, decode):
        nonlocal pos
        while pos < end:
            pos = min(pos + rows, end)
            out.append({"end": pos, "decode": decode})
    for s, e in spans:
        run(s, prefill_rows, False)
        run(e, width or prefill_rows, bool(width))
    run(n, prefill_rows, False)
    return out


def common_prefix(a, b) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def call(base, key, body, spec, timeout) -> dict:
    code, raw, dt = P.post_json(base + "/v1/bench/probe", {"body": body, "spec": spec}, key, timeout)
    if code != 200:
        raise RuntimeError(f"HTTP {code}: {raw[:400]!r}")
    reply = json.loads(raw)
    pr = reply.get("probe") or {}
    if pr.get("error") or not pr.get("engine"):
        raise RuntimeError(f"probe not honoured: {pr.get('error')}")
    return {"elapsed_s": round(dt, 3), "timing": reply.get("timing"), "usage": reply.get("usage"),
            "content": reply.get("content") or "", "reasoning": reply.get("reasoning") or "",
            "server": reply.get("server"), "probe": pr}


def leg_record(name, r, keep_ids=False) -> dict:
    pr = r["probe"]
    rec = {"leg": name, "elapsed_s": r["elapsed_s"], "timing": r["timing"], "usage": r["usage"],
           "prompt_tokens": len(pr["prompt_ids"]), "prompt_sha256": P.sha256_text(json.dumps(pr["prompt_ids"])),
           "cached_tokens": pr.get("cached_tokens"), "cold": pr.get("cold"),
           "no_speculation": pr.get("no_speculation"), "last_prefill_units": pr.get("last_prefill_units"),
           "states": pr.get("states"), "cold_steps": len(pr.get("cold_steps") or []),
           "generated": pr.get("generated") or [], "rows": pr.get("rows") or []}
    if keep_ids:
        rec["prompt_ids"] = pr["prompt_ids"]
    return rec


def run(a) -> int:
    item = load_item(a.set, a.item)
    m = item["_meta"]
    users = user_messages(item, a.mode, a.parts)
    name = f"{a.item}.{a.mode}" + (f"-p{a.parts}" if a.mode == "turns" else "")
    seed0 = P.seed_for("turncheck", a.rep, m["family"], m["index"], m["length"])
    print(f"{a.arm} {a.run_tag} {name}: {len(users)} user messages, {sum(map(len, users)):,} chars, seed {seed0}, "
          f"rows {a.rows}, replay widths {a.replay_widths}", flush=True)
    if a.dry_run:
        return 0
    dest = OUT / a.arm / a.run_tag / f"{name}.rep{a.rep}.json.gz"
    if dest.exists():
        sys.exit(f"{dest} exists")
    key = P.read_key(a.api_key_file)
    base = a.base_url.rstrip("/")
    client = P.stage0_client()
    nonce = client.nonce_for(f"{P.SALT}:turncheck", seed0)
    doc = {"arm": a.arm, "run_tag": a.run_tag, "item": a.item, "mode": a.mode, "parts": a.parts, "args": vars(a),
           "seed0": seed0, "nonce": nonce, "models_doc": P.models_doc(base, key), "started": P.now_iso(),
           "driver_sha256": P.sha256_file(__file__), "item_sha256": m["file_sha256"],
           "gpu_start": client.gpu_snapshot(), "turns": [], "legs": [], "skipped": [], "complete": False}
    leaf = lambda leg: f"{a.arm}-{a.run_tag}-{name}-rep{a.rep}-{leg}" if a.dump_root else None  # noqa: E731

    def finish(code: int) -> int:
        doc.update(finished=P.now_iso(), gpu_end=client.gpu_snapshot())
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as f:
            json.dump(doc, f)
        tmp.replace(dest)
        print(f"-> {dest}", flush=True)
        return code

    try:
        # history turns, as served
        messages, prev = [], None
        for i, text in enumerate(users[:-1]):
            messages.append({"role": "user", "content": text})
            sent = client.with_nonce(messages, nonce)
            cap = a.max_tokens if a.mode == "single" else a.ack_max_tokens
            body = P.chat_body("", sent, cap, seed0 + i)
            r = call(base, key, body, {"record_first": True, "top_k": 20, "output_dependent": i > 0}, a.timeout)
            pr = r["probe"]
            fin = (r["timing"] or {}).get("finish_reason")
            turn = {"turn": i, "finish_reason": fin, "finish_detail": (r["usage"] or {}).get("finish_detail"),
                    "prompt_tokens": len(pr["prompt_ids"]), "generated": len(pr["generated"]),
                    "cached_tokens": pr.get("cached_tokens"), "elapsed_s": r["elapsed_s"],
                    "last_generated": pr["generated"][-3:], "content_tail": r["content"][-80:]}
            if prev is not None:
                turn["round_trip"] = round_trip(prev, pr["prompt_ids"])
            doc["turns"].append(turn)
            print(f"  h{i}: prompt {turn['prompt_tokens']:,}, cached {turn['cached_tokens']:,}, generated "
                  f"{turn['generated']:,}, finish {fin}, {r['elapsed_s']:.0f} s", flush=True)
            if fin != "stop":
                doc["error"] = f"history turn {i} finished '{fin}', not 'stop': no natural reply to carry forward"
                return finish(2)
            messages.append({"role": "assistant", "content": r["content"], "reasoning_content": r["reasoning"]})
            prev = pr
        # the recorded turn
        messages.append({"role": "user", "content": users[-1]})
        sent = client.with_nonce(messages, nonce)
        seed = seed0 + len(users) - 1
        body = {"messages": sent, "max_tokens": a.rows, "seed": seed, "chat_template_kwargs": dict(P.TEMPLATE_KWARGS)}
        rec = {"no_speculation": True, "record_rows": a.rows, "top_k": 20, "output_dependent": True}
        if a.record_state:
            rec["record_state"] = True

        def leg(name_, extra, keep_ids=False):
            spec = dict(rec, **extra)
            if leaf(name_):
                spec["dump_rows"] = leaf(name_)
            r_ = call(base, key, body, spec, a.timeout)
            out = leg_record(name_, r_, keep_ids)
            out["dump"] = str(Path(a.dump_root) / leaf(name_)) if leaf(name_) else None
            doc["legs"].append(out)
            print(f"  {name_}: cached {out['cached_tokens']:,}, {len(out['rows'])} rows, {out['elapsed_s']:.0f} s",
                  flush=True)
            return r_["probe"]

        live = leg("live", {}, keep_ids=True)
        ids = live["prompt_ids"]
        doc["live_round_trip"] = round_trip(prev, ids)
        spans = reply_spans(ids)
        doc["reply_spans"] = spans
        print(f"  prompt {len(ids):,} tokens, {len(spans)} earlier replies covering "
              f"{sum(e - s for s, e in spans):,} tokens; round trip {doc['live_round_trip']}", flush=True)
        cold = {"prompt_ids": ids, "cold": True}
        for tag in ("cold-a", "cold-b"):
            got = leg(tag, cold)
            if got["prompt_ids"] != ids or got.get("cached_tokens") != 0 or got.get("cold") is not True:
                doc["error"] = f"{tag}: the engine did not run these ids cold"
                return finish(2)
        leg("replay-p", dict(cold, cold_steps=cold_steps(len(ids), spans, None, a.prefill_rows)))
        for w in a.replay_widths:
            steps = cold_steps(len(ids), spans, w, a.prefill_rows)
            n_decode = sum(s["decode"] for s in steps)
            if n_decode > a.max_replay_steps:
                doc["skipped"].append({"leg": f"replay-{w}", "decode_steps": n_decode})
                print(f"  replay-{w}: skipped, {n_decode:,} decode steps before the first byte", flush=True)
                continue
            leg(f"replay-{w}", dict(cold, cold_steps=steps))
        doc["complete"] = True
        return finish(0)
    except (RuntimeError, OSError, ValueError) as e:
        doc["error"] = repr(e)[:800]
        print(f"  stopped: {doc['error']}", flush=True)
        return finish(2)


def round_trip(prev: dict, ids: list[int]) -> dict:
    """Does the next turn's rendered prompt begin with the previous prompt + everything the engine generated
    (less the final sampled token, which was never run)?"""
    want = prev["prompt_ids"] + prev["generated"]
    cp = common_prefix(want, ids)
    out = {"previous_prompt": len(prev["prompt_ids"]), "previous_generated": len(prev["generated"]),
           "common_prefix": cp, "exact": cp >= len(want) - 1}
    if not out["exact"]:
        out["first_difference"] = {"index": cp, "generated_index": cp - len(prev["prompt_ids"]),
                                   "expected": want[cp:cp + 6], "rendered": ids[cp:cp + 6]}
    return out


# ---- report ----

def compare_legs(x: dict, y: dict) -> dict:
    n = len(x["prompt_ids"]) if "prompt_ids" in x else x["prompt_tokens"]
    rx, ry = ({r["position"]: r for r in leg["rows"]} for leg in (x, y))
    same_tokens = common_prefix(x["generated"], y["generated"])
    dx, dy = P.dump_index(x.get("dump")), P.dump_index(y.get("dump"))
    rows = []
    for j in range(same_tokens + 1):          # row j is selected after j identical generated tokens
        p = n + j
        if p not in rx or p not in ry:
            break
        kl_lb, kept = P.lumped_kl(rx[p]["top"], ry[p]["top"])
        rows.append({"hash_equal": rx[p]["hash"] == ry[p]["hash"], "top1_equal": rx[p]["argmax"] == ry[p]["argmax"],
                     "kl_lower": kl_lb, "kept": kept,
                     "kl": P.exact_kl(dx[p], dy[p]) if p in dx and p in dy else None})
    if not rows:
        return {"rows": 0}
    out = {"rows": len(rows), "recorded": min(len(rx), len(ry)), "tokens_identical": same_tokens,
           "tokens_generated": min(len(x["generated"]), len(y["generated"])),
           "hash_equal": sum(r["hash_equal"] for r in rows), "top1_differs": sum(not r["top1_equal"] for r in rows),
           "kl_lower_mean": statistics.fmean(r["kl_lower"] for r in rows),
           "kl_lower_max": max(r["kl_lower"] for r in rows)}
    if all(r["kl"] is not None for r in rows):
        out.update(kl_mean=statistics.fmean(r["kl"] for r in rows), kl_max=max(r["kl"] for r in rows),
                   kl_first=rows[0]["kl"])
    return out


def report(a) -> int:
    files = sorted((OUT / a.arm / a.run_tag).glob("*.json.gz"))
    if not files:
        sys.exit("no receipts")
    res = []
    for f in files:
        with gzip.open(f, "rt") as fh:
            doc = json.load(fh)
        legs = {leg["leg"]: leg for leg in doc["legs"]}
        widths = sorted(int(k.split("-")[1]) for k in legs if k.startswith("replay-") and k != "replay-p")
        entry = {"file": f.name, "item": doc["item"], "mode": doc["mode"], "parts": doc["parts"],
                 "complete": doc["complete"], "error": doc.get("error"),
                 "turns": [{k: t.get(k) for k in ("turn", "prompt_tokens", "generated", "cached_tokens",
                                                  "finish_reason", "round_trip")} for t in doc["turns"]],
                 "live_round_trip": doc.get("live_round_trip"), "reply_tokens": sum(e - s for s, e in
                                                                                    doc.get("reply_spans") or []),
                 "live_prompt_tokens": legs["live"]["prompt_tokens"] if "live" in legs else None,
                 "live_cached_tokens": legs["live"]["cached_tokens"] if "live" in legs else None, "pairs": []}
        print(f"\n{f.name}: {'complete' if doc['complete'] else 'INCOMPLETE ' + str(doc.get('error'))}")
        for t in doc["turns"]:
            rt = t.get("round_trip")
            print(f"  h{t['turn']}: prompt {t['prompt_tokens']:,}, cached {t['cached_tokens']:,}, generated "
                  f"{t['generated']:,}" + (f", re-render exact: {rt['exact']}" if rt else ""))
        if "live" not in legs:
            res.append(entry)
            continue
        print(f"  live: prompt {entry['live_prompt_tokens']:,}, cached {entry['live_cached_tokens']:,}, earlier "
              f"replies {entry['reply_tokens']:,} tokens, re-render exact: {(entry['live_round_trip'] or {}).get('exact')}")
        for xa, yb, label in PAIRS:
            for w in (widths if "{w}" in xa + yb else [None]):
                x, y = xa.format(w=w), yb.format(w=w)
                if x not in legs or y not in legs:
                    continue
                c = compare_legs(legs[x], legs[y]) | {"a": x, "b": y, "what": label.format(w=w)}
                entry["pairs"].append(c)
                if not c["rows"]:
                    continue
                kl = f"KL mean {c['kl_mean']:.2e} max {c['kl_max']:.2e}" if "kl_mean" in c else \
                    f"KL >= {c['kl_lower_mean']:.2e} (max {c['kl_lower_max']:.2e})"
                print(f"  {x:>10} vs {y:<10} {c['what']:<42} rows {c['rows']:>3}  identical {c['hash_equal']:>3}  "
                      f"top-1 flips {c['top1_differs']:>2}  {kl}  tokens same {c['tokens_identical']}/"
                      f"{c['tokens_generated']}")
        res.append(entry)
    dest = OUT / a.arm / a.run_tag / "report.json"
    P.write_json_atomic(dest, {"arm": a.arm, "run_tag": a.run_tag, "kl_direction": "KL(a || b), nats",
                               "conversations": res})
    print(f"\n-> {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--arm", required=True)
    r.add_argument("--run-tag", required=True)
    r.add_argument("--item", required=True, help="an item id, e.g. ledger-000-16k")
    r.add_argument("--set", default="pilot")
    r.add_argument("--mode", required=True, choices=["single", "turns"])
    r.add_argument("--parts", type=int, default=8)
    r.add_argument("--rep", type=int, default=0)
    r.add_argument("--rows", type=int, default=32, help="K: recorded rows = generated tokens of the last turn")
    r.add_argument("--replay-widths", nargs="*", type=int, default=[64, 1])
    r.add_argument("--max-replay-steps", type=int, default=20000,
                   help="skip a replay with more decode steps (the bench client reads with a 900 s timeout)")
    r.add_argument("--prefill-rows", type=int, default=4096)
    r.add_argument("--max-tokens", type=int, required=True, help="single mode: cap of the history reply")
    r.add_argument("--ack-max-tokens", type=int, default=4096)
    r.add_argument("--record-state", action="store_true")
    r.add_argument("--dump-root", default="", help="the launch's PROBE_DUMP_ROOT: dump rows for exact KL")
    r.add_argument("--api-key-file", default=P.KEY_FILE)
    r.add_argument("--base-url", default=P.BASE_URL)
    r.add_argument("--timeout", type=float, default=3600.0)
    r.add_argument("--dry-run", action="store_true")
    q = sub.add_parser("report")
    q.add_argument("--arm", required=True)
    q.add_argument("--run-tag", required=True)
    a = ap.parse_args()
    return run(a) if a.cmd == "run" else report(a)


if __name__ == "__main__":
    sys.exit(main())
