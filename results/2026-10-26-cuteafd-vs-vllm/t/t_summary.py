#!/usr/bin/env python3
"""Block T summary: per (input length, content, concurrency) cell, the median over the 3 replicates of each
replicate's batch metrics, with the min-max range; and engine A vs B ratios on the same cells.
Usage: t_summary.py A.json [B.json] > SUMMARY.md     (standard library only)"""
import json
import statistics
import sys


def cells(path):
    d = json.load(open(path))
    out = {}
    for b in d["batches"]:
        if b["kind"] != "measured":
            continue
        s = b["summary"]
        out.setdefault((b["length"], b["content"], b["level"]), []).append(s)
    return d["label"], out, d


def med(xs):
    xs = [x for x in xs if x is not None]
    return (statistics.median(xs), min(xs), max(xs)) if xs else (None, None, None)


def fmt(t, nd=1):
    m, lo, hi = t
    return "n/a" if m is None else f"{m:.{nd}f} ({lo:.{nd}f}-{hi:.{nd}f})"


def errs(rows):
    return sum(r["errors"] for r in rows)


A = cells(sys.argv[1])
B = cells(sys.argv[2]) if len(sys.argv) > 2 else None
arms = [A] + ([B] if B else [])
keys = sorted(set().union(*[set(a[1]) for a in arms]))
print("Median of 3 replicates (min-max). Decode = per-stream tok/s (median stream); aggregate = completion tok/s "
      "of the batch; TTFT median seconds; prefill = prompt tok/s of the batch (sum prompt tokens / time to last "
      "first token). Thinking on, temperature 1.0, top_p 0.95, 1,024 output tokens.\n")
metrics = [("decode", "decode_tok_s_per_stream_median", 1), ("aggregate", "aggregate_tok_s", 1),
           ("TTFT s", "ttft_median_s", 2), ("prefill tok/s", "aggregate_prefill_tok_s", 0)]
for name, key, nd in metrics:
    print(f"### {name}\n")
    head = "| Input | Content | Streams | " + " | ".join(a[0] for a in arms) + (" | ratio " + B[0] + "/" + A[0] if B else "") + " |"
    print(head)
    print("|" + "---|" * (3 + len(arms) + (1 if B else 0)))
    for k in keys:
        vals = [med([s.get(key) for s in a[1].get(k, [])]) for a in arms]
        row = [f"{k[0] // 1024}K", k[1], str(k[2])] + [fmt(v, nd) for v in vals]
        if B:
            row.append("n/a" if None in (vals[0][0], vals[1][0]) else f"{vals[1][0] / vals[0][0]:.2f}")
        print("| " + " | ".join(row) + " |")
    print()
for a in arms:
    rows = [s for v in a[1].values() for s in v]
    fr = sorted({f for s in rows for f in s["finish_reasons"]})
    think_close = sum(s.get("content_has_think_close", 0) for s in rows)
    print(f"- {a[0]}: {len(rows)} measured batches, {sum(s['requests'] for s in rows)} requests, errors {errs(rows)}, "
          f"finish reasons {fr}, content containing </think>: {think_close}")
