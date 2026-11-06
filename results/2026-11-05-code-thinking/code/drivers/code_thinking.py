#!/usr/bin/env python3
"""Code-thinking run (PROTOCOL.md): the CuteAFD v4 run's frozen Block L stage-L3 driver (block_l3.py, imported unchanged;
its own freeze check applies), as the core-swap's block_l3_cs.py did, pointed at this run's prompt set
(stage0/prompts: 16 code prompts, p0-p3 the Block L code projects, p4-p15 new) with this run's queue:
16 prompts x 4 replies, seed = 2_026_110_500 + 100 * prompt + rep (distinct from every earlier Block L seed), the same
seeds on every arm. Same wrapper, nonce rule and salt, cap 130,048, 2 concurrent, thinking on, gates.

  code_thinking.py --arm C --label C-K6 --stages L3 --out l/C-K6-L3.json [--dry-run]
"""
import hashlib, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "<runs>/2026-10-30-cuteafd-v4/drivers")
import block_l3 as B  # noqa: E402

PROMPTS = Path("<ct-run>/stage0/prompts")
SEED0, N_PROMPTS, REPS = 2_026_110_500, 16, 4


def load_prompts():
    idx = json.loads((PROMPTS / "L" / "index.json").read_text())
    out = {}
    for c in idx["prompts"]:
        f = PROMPTS / c["file"]
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h != c["sha256"]:
            sys.exit(f"prompt file changed since the index was written: {c['file']}")
        out[(c["content"], c["prompt_index"])] = json.loads(f.read_text()) | {"sha256": h}
    return out


def stage_queue(stage):
    if stage != "L3":
        return []
    return [("code", p, rep, SEED0 + 100 * p + rep) for rep in range(REPS) for p in range(N_PROMPTS)]


B.block_l.load_prompts = load_prompts
B.client.PROMPTS = PROMPTS
B.stage_queue = stage_queue
if __name__ == "__main__":
    sys.exit(B.main())
