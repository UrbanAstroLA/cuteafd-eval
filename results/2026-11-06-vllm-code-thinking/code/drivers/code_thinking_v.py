#!/usr/bin/env python3
"""vLLM arm of the code-thinking study (PROTOCOL.md): the CuteAFD study's driver (code_thinking.py, imported unchanged:
same 16 code prompts, seeds 2_026_110_500 + 100 * prompt + rep, wrapper, nonce rule, cap 130,048, 2 concurrent,
thinking on, gates; it in turn imports the v4 run's frozen block_l3.py) with one engine entry added so the receipts name
the engine actually served: the vLLM fork v0.9.2-experimental image with the route-b loader (local loader modification).

  code_thinking_v.py --arm Vb --label V-K6 --stages L3 --out l/V-K6-L3.json [--dry-run]
"""
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, "<ct-run>/drivers")
import code_thinking as CT  # noqa: E402  (patches block_l3 on import)

CT.B.K.ENGINES["Vb"] = {"name": "vLLM fork v0.9.2-experimental + route-b loader (local loader modification), image 5fc05b7c",
                        "container": "glm53-flash-exl3-b12x-vllm", "ready_regex": r"container is ready",
                        "top20_route": "completions", "key": False}
if __name__ == "__main__":
    sys.exit(CT.B.main())
