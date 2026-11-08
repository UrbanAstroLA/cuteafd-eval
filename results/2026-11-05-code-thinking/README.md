# Code thinking length on CuteAFD: 6-bit core against BF16 core (2026-11-05/06)

K4-Core-K6 on CuteAFD v4.0.0 with its native 6-bit core (C-K6) against the same checkpoint with its 316 core tensors
restored to the BF16 originals, which CuteAFD converts to FP8 at load (C-K6x; the **local derived checkpoint, not a
producer release**, of [`results/2026-11-03-cuteafd-core-swap`](../2026-11-03-cuteafd-core-swap/)). Same routed experts.
16 code prompts x 4 seeds, the same seed on both arms. Site page: [Thinking length](../../docs/thinking.html).
**Read with** [`results/2026-11-06-vllm-code-thinking`](../2026-11-06-vllm-code-thinking/) (the same prompts on the vLLM fork, where the two cores think alike) and
[`results/2026-11-06-cuteafd-fp8-ablation`](../2026-11-06-cuteafd-fp8-ablation/) (CuteAFD's FP8 settings switched off cumulatively: the difference goes with the KDA setting).

- `CT-RESULT.md`: the result as read (with a correction to one descriptive field of `analysis/CT-RESULT.json`).
- `SUMMARY.json`: every number on the page.
- `protocol/`: the protocol as frozen and `FROZEN.json`.
- `prompts/`: the 16 prompts (`L/p0.json`-`L/p15.json`, `L/index.json`) and each project's spec, reference implementation and
  hidden tests (`L/code/`). p0-p3 are the four Block L code projects, unchanged; p4-p15 were written for this run before
  any request, and each reference implementation passes its tests (`code/tools/check_ref.py`).
- `analysis/`: `samples.csv` (one row per reply: seed, finish, reasoning tokens, decode speed, tests passed; no text),
  the reading and `analyze_ct.py`. Reasoning tokens and code checks come from
  [`repro/stage0/drivers/analyze_l.py`](../../repro/stage0/drivers/analyze_l.py) (unchanged; the run used a copy reading
  this prompt set).
- `code/`: the chain, the driver (it imports the v4 run's Block L driver,
  [`results/2026-11-03-cuteafd-core-swap/code/v4-drivers/block_l3.py`](../2026-11-03-cuteafd-core-swap/code/v4-drivers/block_l3.py),
  unchanged) and the prompt builder.

Not published: reply and reasoning texts (model output).
