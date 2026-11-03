#!/usr/bin/env python3
"""G1b: on-policy reasoning traces on the knife-edge GPQA questions (PLAN.md). Standard library only; host python3.

    python3 gen_traces.py --out <dir> --budget-s 9000 [--docs 186,12,81,120,86,74,13] [--n 8]

Sends each question (lm-eval's own GPQA rendering, one user message) to the server on 127.0.0.1:8001 as a streamed chat
completion: temperature 1.0, top_p 0.95 (model defaults, as GPQA protocol v1), max_tokens 327,680, thinking on, a
distinct request seed per sample (--seed-base + 100 * doc + rep, recorded; default 40000 = G1b). --concurrency in flight (default 4: the
route-b K4-Core-K6 pool, 1.37M tokens, holds ~4 requests at the cap; GPQA protocol v1's rule for such configurations). Requests run in a fixed shuffled
order (Random(7), rep-major so every question gets early samples). When the wall budget ends, requests still running are
closed and kept as 'unfinished_at_cut' with the text received so far.
Per sample: doc<d>_rep<r>.json (+ .reasoning.txt), the looping probes' format; class as theirs: ok = finish stop;
loop = finish length and last-30K-char zlib ratio < 0.15; exhaust = finish length otherwise.
"""
import argparse, json, os, random, threading, time, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor

SAMPLES = ("<runs>/gpqa/glm53-flash-exl3-k3.25@tpurtell__pass1/wrldsuksgo2mars__GLM-5.3-Flash-EXL3-K3.25-v1/"
           "samples_gpqa_diamond_thinking_2026-09-29T10-34-37.597068.jsonl")
BASE = "http://127.0.0.1:8001"


def messages(docs):
    out = {}
    for line in open(SAMPLES):
        d = json.loads(line)
        if d["doc_id"] in docs:
            a = d["arguments"]["gen_args_0"]["arg_0"]
            out[d["doc_id"]] = json.loads(a[0] if isinstance(a, list) else a)
    assert set(out) == set(docs), sorted(out)
    return out


def classify(finish, reasoning):
    if finish == "stop":
        return "ok"
    if finish == "length":
        tail = reasoning[-30000:].encode()
        return "loop" if tail and len(zlib.compress(tail)) / len(tail) < 0.15 else "exhaust"
    return finish or "unfinished_at_cut"


def one(job, model, deadline, out, stop, seed_base=40000):
    doc, rep, msgs = job
    seed = seed_base + 100 * doc + rep
    body = {"model": model, "messages": msgs, "temperature": 1.0, "top_p": 0.95, "max_tokens": 327680, "seed": seed,
            "stream": True, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": True}}
    rec = {"doc": doc, "rep": rep, "seed": seed, "finish_reason": None, "usage": None, "t_start": time.time()}
    reasoning, content, chunks = [], [], 0
    if stop.is_set() or time.time() > deadline:
        return None
    req = urllib.request.Request(BASE + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                if time.time() > deadline:
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                ev = json.loads(data)
                if ev.get("usage"):
                    rec["usage"] = ev["usage"]
                for ch in ev.get("choices") or []:
                    dl = ch.get("delta") or {}
                    if dl.get("reasoning_content") or dl.get("reasoning"):
                        reasoning.append(dl.get("reasoning_content") or dl.get("reasoning"))
                    if dl.get("content"):
                        content.append(dl["content"])
                    if ch.get("finish_reason"):
                        rec["finish_reason"] = ch["finish_reason"]
                    chunks += 1
    except Exception as exc:  # recorded, not retried: the sample stays in the record as an error
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rtext, ctext = "".join(reasoning), "".join(content)
    rec.update({"secs": round(time.time() - rec["t_start"], 1), "chunks": chunks, "reasoning_chars": len(rtext),
                "content_chars": len(ctext), "content": ctext, "cls": classify(rec["finish_reason"], rtext)})
    if rec["finish_reason"] is None:
        rec["cls"] = "unfinished_at_cut" if "error" not in rec else "error"
    base = os.path.join(out, f"doc{doc}_rep{rep}")
    open(base + ".reasoning.txt", "w").write(rtext)
    json.dump(rec, open(base + ".json", "w"), indent=1)
    print(f"{time.strftime('%H:%M:%S')} doc {doc} rep {rep} {rec['cls']} "
          f"{(rec['usage'] or {}).get('completion_tokens')} tok {rec['secs']} s", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget-s", type=float, required=True)
    ap.add_argument("--docs", default="186,12,81,120,86,74,13")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=40000)
    a = ap.parse_args()
    docs = [int(x) for x in a.docs.split(",")]
    os.makedirs(a.out, exist_ok=True)
    model = json.load(urllib.request.urlopen(BASE + "/v1/models", timeout=30))["data"][0]["id"]
    msgs = messages(docs)
    jobs = [(d, r, msgs[d]) for r in range(1, a.n + 1) for d in random.Random(7).sample(docs, len(docs))]
    deadline, stop = time.time() + a.budget_s, threading.Event()
    json.dump({"model": model, "docs": docs, "n": a.n, "budget_s": a.budget_s, "order": [(d, r) for d, r, _ in jobs],
               "concurrency": a.concurrency, "seed_base": a.seed_base, "started": time.time()}, open(os.path.join(a.out, "plan.json"), "w"), indent=1)
    with ThreadPoolExecutor(a.concurrency) as ex:
        res = [f.result() for f in [ex.submit(one, j, model, deadline, a.out, stop, a.seed_base) for j in jobs]]
    done = [r for r in res if r]
    summary = {"requested": len(jobs), "sent": len(done), "by_class": {}}
    for r in done:
        summary["by_class"][r["cls"]] = summary["by_class"].get(r["cls"], 0) + 1
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
