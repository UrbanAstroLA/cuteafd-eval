#!/usr/bin/env python3
"""FP8 ablation run (PROTOCOL.md): the code-thinking driver, unchanged (16 code prompts x 4 replies, seed =
2_026_110_500 + 100 * prompt + rep, same wrapper, nonce rule, cap 130,048, 2 concurrent), imported from the code study.
--control limits the queue to one request (prompt 3, rep 3: the shortest C-K6x reply) for the replay check.

  fp8_ablation.py --arm C --label F-kda --stages L3 --out l/F-kda-L3.json [--control]
"""
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, "<ct-run>/drivers")
import code_thinking as CT  # noqa: E402  (patches the Block L driver on import)

if "--control" in sys.argv:
    sys.argv.remove("--control")
    CT.B.stage_queue = lambda stage: [("code", 3, 3, CT.SEED0 + 100 * 3 + 3)] if stage == "L3" else []
if __name__ == "__main__":
    sys.exit(CT.B.main())
