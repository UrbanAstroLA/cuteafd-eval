# CuteAFD core swap: does K4-Core-K6's 6-bit core or its experts make it think longer? (2026-11-03/04)

On CuteAFD v4.0.0, K4-Core-K6 differs from K4 in its core (native 6-bit against BF16 converted to FP8 at load) and in its
routed experts (two separate 4-bit quantizations). A third arm separates them: K4-Core-K6 with its 316 core tensors
replaced by the BF16 originals, which are byte-identical to K4's core. Site page: [Thinking length](../../docs/thinking.html)
(with the vLLM investigation in [`results/2026-11-02-thinking-length`](../2026-11-02-thinking-length/)).

**Derived checkpoint.** `derived/GLM-5.3-Flash-EXL3-K4-Core-K6-BF16core` is a **local derived checkpoint, not a producer
release**. `prep/build_derived.py` builds it from [wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6 @ 5d3fffe1](https://huggingface.co/wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6/tree/5d3fffe1df9c4a109bbbdafb60dc19df9fac019d)
and the core tensors of [zai-org/GLM-5.3-Flash-BF16 @ f9fed3bb](https://huggingface.co/zai-org/GLM-5.3-Flash-BF16/tree/f9fed3bbc82291073373d67452e9f25317ef7577);
`prep/derived-manifest.json` lists every rewritten shard, `prep/core-hash.json` the 316 core tensors against
[brandonmusic/GLM-5.3-Flash-tr3-4bpw @ a5fee929](https://huggingface.co/brandonmusic/GLM-5.3-Flash-tr3-4bpw/tree/a5fee929cf4888b1824323e33e8a19b60129e025) (all identical).

- `SUMMARY.json`: every number on the page, each group with its source file.
- `S1-READ.md` (free generation) and `S2-READ.md` (fixed traces): the results as read.
- `protocol/`: the protocol as frozen (a cost estimate and two local scheduling notes left out) and `FROZEN.json`
  (sha256 of every frozen file; its `amendments` entry records the one launch-mechanics change).
- `analysis/`: `samples.csv` (one row per reply, here and in the Block L runs used post hoc: seed, finish, reasoning
  tokens, decode speed; no text), `s2-probes.csv` (one row per fixed-trace probe: timing, engine checks, a digest of
  the per-row logits hashes), the per-trace scores, the readings and the scripts that compute them.
- `prep/`: the derived checkpoint's build, manifest and core-hash check. `code/`: the chain, drivers, CuteAFD configs
  (serving and scoring) and the v4 run's Block L driver it reuses (`code/v4-drivers/`; that driver imports
  [`repro/stage0/drivers/block_l.py`](../../repro/stage0/drivers/)). Fixed traces are scored with the thinking-length run's
  [`analysis/score_stop.py`](../2026-11-02-thinking-length/analysis/score_stop.py); reasoning tokens come from
  [`repro/stage0/drivers/analyze_l.py`](../../repro/stage0/drivers/analyze_l.py).

Not published: reply texts (model output), the fixed-trace token ids and probe dumps (GPQA-derived model output and
top-64 log-probabilities, 0.2 GB), and checkpoint weights (rebuild from the two public sources with `prep/build_derived.py`).
