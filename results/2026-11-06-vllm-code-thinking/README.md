# Code thinking length on the vLLM fork: 6-bit core against BF16 core (2026-11-06)

The CuteAFD code study ([`results/2026-11-05-code-thinking`](../2026-11-05-code-thinking/)) repeated on the vLLM fork with the route-b loader (local loader
modification, not a tpurtell release): K4-Core-K6 with its 6-bit core rebuilt to BF16 at load (V-K6) against the same
checkpoint with all 316 core tensors loaded from the original BF16 release (V-BF16). Same routed experts, same 16 code
prompts, seeds and cap as the CuteAFD study. Site page: [Thinking length](../../docs/thinking.html).
**Read with** [`results/2026-11-06-cuteafd-fp8-ablation`](../2026-11-06-cuteafd-fp8-ablation/): the FP8 pieces listed in `CUTEAFD-FP8-PATH.md` switched off cumulatively on CuteAFD.

- `VCT-RESULT.md`: the result as read, with a post hoc cross-engine comparison marked as such.
- `CUTEAFD-FP8-PATH.md`: what changes with the core's format on CuteAFD v4.0.0, read in its source and launch logs (no GPU).
- `SUMMARY.json`: every number on the page.
- `protocol/`: the protocol as frozen (engine-comparison readings stated before the run) and `FROZEN.json`.
- `analysis/`: `samples.csv` (one row per reply: seed, finish, reasoning tokens, decode speed, tests passed; no text),
  the frozen reading (`analyze_vct.py`, `VCT-RESULT.json`) and the post hoc cross-engine table (`cross_engine.py`,
  `cross_engine.json`). Reasoning tokens and code checks come from
  [`repro/stage0/drivers/analyze_l.py`](../../repro/stage0/drivers/analyze_l.py) (unchanged).
- `code/`: the chain and the driver (it imports the CuteAFD study's driver, [`results/2026-11-05-code-thinking/code/drivers/code_thinking.py`](../2026-11-05-code-thinking/code/drivers/code_thinking.py),
  and adds the vLLM engine entry). Prompts, specs and hidden tests: [`results/2026-11-05-code-thinking/prompts`](../2026-11-05-code-thinking/prompts/).

Not published: reply and reasoning texts (model output).
