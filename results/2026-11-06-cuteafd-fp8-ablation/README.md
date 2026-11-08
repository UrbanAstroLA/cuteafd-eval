# Which part of CuteAFD's FP8 path shortens code reasoning (2026-11-06/07)

On CuteAFD v4.0.0 the BF16-core checkpoint (C-K6x; the **local derived checkpoint, not a producer release**, of
[`results/2026-11-03-cuteafd-core-swap`](../2026-11-03-cuteafd-core-swap/)) thought shorter on code than the native 6-bit
core ([`results/2026-11-05-code-thinking`](../2026-11-05-code-thinking/)), while on the vLLM fork the two cores thought alike
([`results/2026-11-06-vllm-code-thinking`](../2026-11-06-vllm-code-thinking/)). This run switches off, cumulatively, the three FP8 pieces that have a launch setting:
the KDA projections (F-kda), the vocabulary head (F-head) and FP8 prefill activations (F-pre). Same prompts, seeds and cap
as the code study; arms pair with C-K6x and C-K6 by seed. Site page: [Thinking length](../../docs/thinking.html).

- `FA-RESULT.md`: the result as read. `SUMMARY.json`: every number on the page.
- `protocol/`: the protocol as frozen and `FROZEN.json`.
- `analysis/`: `samples.csv` (one row per reply, including the control replay F-ctrl: seed, finish, reasoning tokens,
  decode speed, tests passed; no text), `analyze_fa.py` and `FA-RESULT.json`; post hoc, `pass_pairs.py` and
  `PASS-PAIRS.json` (hidden-test outcomes paired across the code-thinking arms of both engines, added 2026-11-08).
  Reasoning tokens and code checks come from
  [`repro/stage0/drivers/analyze_l.py`](../../repro/stage0/drivers/analyze_l.py) (unchanged).
- `code/`: the chain (launch, precision check in the server log before any request, run) and the driver (it imports
  [`results/2026-11-05-code-thinking/code/drivers/code_thinking.py`](../2026-11-05-code-thinking/code/drivers/code_thinking.py) unchanged).
  Prompts, specs and hidden tests: [`results/2026-11-05-code-thinking/prompts`](../2026-11-05-code-thinking/prompts/). What each switch changes, read in the
  engine's source: [`results/2026-11-06-vllm-code-thinking/CUTEAFD-FP8-PATH.md`](../2026-11-06-vllm-code-thinking/CUTEAFD-FP8-PATH.md).

Not published: reply and reasoning texts (model output).
