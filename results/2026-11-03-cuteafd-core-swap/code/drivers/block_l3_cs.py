#!/usr/bin/env python3
"""Core-swap step 1: Block L stage L3, code and prose only, with new seeds. Runs the v4 run's frozen block_l3.py
unchanged (imported; its own freeze check against <v4 run>/FROZEN.json applies), as block_l3_r2.py did, with two
differences: every seed and rep index is offset by CS_OFFSET (20 or 30; r1 used 0, r2 10), so no seed equals a Block L
seed and request ids stay distinct; and the queue keeps the code and prose contents only. Same prompts, salt, cap
(130,048), 2 concurrent, gates.

  CS_OFFSET=20 block_l3_cs.py --arm C --label C-K6x-a --stages L3 --out l/C-K6x-a-L3.json [--dry-run]
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, "<runs>/2026-10-30-cuteafd-v4/drivers")
import block_l3 as B  # noqa: E402

OFFSET = int(os.environ.get("CS_OFFSET", "0"))
if OFFSET not in (20, 30):
    sys.exit("CS_OFFSET must be 20 or 30")
KEEP = ("code", "prose")
_orig = B.stage_queue


def stage_queue(stage):
    return [(c, p, rep + OFFSET, seed + OFFSET) for c, p, rep, seed in _orig(stage) if c in KEEP]


B.stage_queue = stage_queue
if __name__ == "__main__":
    sys.exit(B.main())
