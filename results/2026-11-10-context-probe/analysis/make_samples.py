#!/usr/bin/env python3
"""One row per request of the measured task runs, without any text. Standard library only.

Reads the task receipts (tasks/<arm>/<tag>/<pass>/requests.jsonl, written by drivers/run_tasks.py) and writes
samples.csv beside this file. Left out on purpose: reply and reasoning text, the values a reply gave, nonces,
session ids. Kept: what the scoring rule and the descriptive columns need.

Columns
  arm            anchor | hqa | compact
  pass           single-rep0 | single-rep1 | turns-p8-rep0
  cell           single | turns-p8          (the unit the frozen rule compares within)
  item, family, length, rep
  turn           0 for a single-message request; 0-7 for the eight delivery turns, 8 for the question turn
  final          1 for the request that is scored, 0 for a delivery turn
  seed           the sampling seed sent with the request
  status         ok | error (transport level)
  finish_class   stop | cap | repetition
  fields, correct  answer fields of the item and how many the last ANSWER line got right (final requests only)
  prompt_tokens, completion_tokens, cached_tokens   as the engine reported them
  reasoning_chars, content_chars                    characters streamed as reasoning and as reply
  ttft_s, decode_tok_s                              time to first streamed chunk; (completion tokens - 1) / stream time
  ack_ok         delivery turns only: 1 when the reply was the requested acknowledgement
"""
import csv
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parent.parent
ARMS = ("anchor", "hqa", "compact")
PASSES = ("single-rep0", "single-rep1", "turns-p8-rep0")
HEAD = ["arm", "pass", "cell", "item", "family", "length", "rep", "turn", "final", "seed", "status", "finish_class",
        "fields", "correct", "prompt_tokens", "completion_tokens", "cached_tokens", "reasoning_chars",
        "content_chars", "ttft_s", "decode_tok_s", "ack_ok"]
ORDER = {"4k": 0, "16k": 1, "64k": 2, "128k": 3}


def main(tag="m0"):
    rows = []
    for arm in ARMS:
        for ps in PASSES:
            for line in open(RUN / "tasks" / arm / tag / ps / "requests.jsonl"):
                r = json.loads(line)
                s = r.get("score") or {}
                rows.append([arm, ps, ps.rsplit("-rep", 1)[0], r["item"], r["family"], r["length"], r["rep"],
                             r["turn"], int(bool(r["final"])), r["seed"], r["status"], r["finish_class"],
                             s.get("fields", "") if r["final"] else "", s.get("correct", "") if r["final"] else "",
                             r["prompt_tokens"], r["completion_tokens"], r["cached_tokens"], r["reasoning_chars"],
                             r["content_chars"], r["ttft_s"], r["decode_tok_s"],
                             "" if r["final"] else int(bool(r.get("ack_ok")))])
    rows.sort(key=lambda x: (ARMS.index(x[0]), PASSES.index(x[1]), x[4], x[3], ORDER[x[5]], x[7]))
    with open(Path(__file__).resolve().parent / "samples.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEAD)
        w.writerows(["" if v is None else v for v in row] for row in rows)
    print(len(rows), "rows")


if __name__ == "__main__":
    main(*sys.argv[1:])
