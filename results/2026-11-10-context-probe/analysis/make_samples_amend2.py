#!/usr/bin/env python3
"""One row per request of the four single-message passes of `k325-fp8` (amendment 2), without any text. Standard
library only.

Reads tasks/k325-fp8/m0/single-rep0 to single-rep3/requests.jsonl (written by drivers/run_tasks.py) and writes
samples-amend2.csv beside this file, in the columns of samples.csv (see make_samples.py for what each column holds
and what is left out). The four passes are named one by one.
"""
import csv
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parent.parent
ARM = "k325-fp8"
PASSES = ("single-rep0", "single-rep1", "single-rep2", "single-rep3")
HEAD = ["arm", "pass", "cell", "item", "family", "length", "rep", "turn", "final", "seed", "status", "finish_class",
        "fields", "correct", "prompt_tokens", "completion_tokens", "cached_tokens", "reasoning_chars",
        "content_chars", "ttft_s", "decode_tok_s", "ack_ok"]
ORDER = {"4k": 0, "16k": 1, "64k": 2, "128k": 3}


def main(tag="m0"):
    rows = []
    for ps in PASSES:
        for line in open(RUN / "tasks" / ARM / tag / ps / "requests.jsonl"):
            r = json.loads(line)
            s = r.get("score") or {}
            rows.append([ARM, ps, ps.rsplit("-rep", 1)[0], r["item"], r["family"], r["length"], r["rep"],
                         r["turn"], int(bool(r["final"])), r["seed"], r["status"], r["finish_class"],
                         s.get("fields", "") if r["final"] else "", s.get("correct", "") if r["final"] else "",
                         r["prompt_tokens"], r["completion_tokens"], r["cached_tokens"], r["reasoning_chars"],
                         r["content_chars"], r["ttft_s"], r["decode_tok_s"],
                         "" if r["final"] else int(bool(r.get("ack_ok")))])
    rows.sort(key=lambda x: (PASSES.index(x[1]), x[4], x[3], ORDER[x[5]], x[7]))
    with open(Path(__file__).resolve().parent / "samples-amend2.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEAD)
        w.writerows(["" if v is None else v for v in row] for row in rows)
    print(len(rows), "rows")


if __name__ == "__main__":
    main(*sys.argv[1:])
