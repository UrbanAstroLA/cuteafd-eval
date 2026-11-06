# Code-thinking run: does K4-Core-K6's 6-bit core make it think longer on code? (CuteAFD v4.0.0, 2026-11-05)

Frozen before the first request (FROZEN.json). Written after the core-swap
step 1 read core 1.16 [0.98, 1.36] (code 1.25, 4 code prompts) and Block L post hoc code 1.43 [1.20, 1.59].

## Question
On code tasks, does K4-Core-K6 with its native 6-bit core think longer than the same checkpoint with the BF16 core?

## Arms (CuteAFD v4.0.0, 2x RTX PRO 6000, local experts; serving configs of the core-swap run, unchanged)
- C-K6: wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6 @ 5d3fffe1 (native 6-bit core).
- C-K6x: local derived checkpoint (not a producer release) derived/GLM-5.3-Flash-EXL3-K4-Core-K6-BF16core @ 049c0180: the
  same routed experts and MTP, the 316 core matrices as the BF16 originals (zai-org/GLM-5.3-Flash-BF16 @ f9fed3bb), which
  CuteAFD converts to FP8 at load (as it does for K4).
Order: C-K6x, then C-K6.

## Prompts (stage0/prompts, built by build_prompts.py)
16 code prompts in the Block L format (L_code wrapper; Python 3.12 package spec; files answered as `### FILE:` blocks;
hidden pytest suite). p0-p3: the four Block L code projects, byte-identical. p4-p15: twelve projects written 2026-11-05
for this run (spec, reference implementation, hidden tests; each reference passes its tests in the code sandbox), before
any request. The p0-p3 set raised the question, so it is not the primary set.

## Requests
4 replies per prompt per arm (64 per arm). Seed = 2,026,110,500 + 100 x prompt + rep, the same seed on both arms for a
(prompt, rep); no seed used before. The frozen v4 Block L stage-L3 driver (block_l3.py, imported unchanged through
drivers/code_thinking.py): nonce line per seed (salt unchanged), thinking on, model default sampling as in the v4 run,
cap 130,048 completion tokens, 2 concurrent, stop on the first HTTP error. Nothing else on the GPUs (pre-flight).

## Measures and reading (analysis/analyze_ct.py; the core-swap step 1 estimator)
- Reasoning tokens by re-tokenization of the saved reasoning text (the Block L analyzer, copied unchanged into
  stage0/drivers so it reads this prompt set; K3.25 tokenizer, same vocabulary).
- Pair = (prompt, rep), both finished (stop, under the cap). Core ratio = exp(mean log(C-K6 / C-K6x)).
- Primary: p4-p15, 95% bootstrap over prompts (4,000 replicates, seed 20261105). Detected when the interval excludes 1.
- Direction (reported with the primary): prompts with a mean log ratio above 0, of 12, with a two-sided sign-test p.
- Secondary: all 16 prompts; p0-p3 alone (against Block L 1.43 and core-swap step 1 1.25); pair-level intervals.
- Descriptive per arm: finished, capped, capped with a terminal repetition onset, all-tests-pass share of finished
  replies, median reasoning tokens, median decode tok/s. Unpaired requests are listed with their finish reasons.

## Not in this run
The stop decision on code text (fixed traces); routed experts (the core-swap run measured them: 0.99 [0.93, 1.05]);
other engines; prose, JSON and reasoning content.
