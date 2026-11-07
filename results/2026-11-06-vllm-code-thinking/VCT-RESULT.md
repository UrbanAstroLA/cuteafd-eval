# Code thinking length on the vLLM fork (route b): result (read 2026-11-06 21:45)

Inputs: `analysis/VCT-RESULT.json` (analyze_vct.py, frozen in FROZEN.json before the first launch), `l/L-analysis.json`.
Run 09:45-21:42. vLLM fork v0.9.2-experimental + route-b loader (local loader modification), image 5fc05b7c. Arms:
V-BF16 (K4-Core-K6, all 316 core tensors from the original BF16 release) and V-K6 (K4-Core-K6, 6-bit core rebuilt to
BF16 at load). Same 16 code prompts, 4 seeds, same seeds and cap (130,048) as the CuteAFD study. Ratio = V-K6 / V-BF16.

## Frozen reading
| Set | Pairs | Ratio | 95% CI over prompts | Prompts above 1 | Sign test |
|---|---|---|---|---|---|
| **p4-p15 (primary)** | 47 | **1.00** | **[0.96, 1.04]** | 8 of 12 | p = 0.39 |
| all p0-p15 | 63 | 1.00 | [0.95, 1.06] | 10 of 16 | p = 0.45 |
| p0-p3 | 16 | 1.01 | [0.85, 1.19] | 2 of 4 | p = 1.0 |

**Not detected.** One pair unpaired (p12 r0: V-BF16 hit the cap while looping).

Engine comparison (vLLM log ratio minus CuteAFD log ratio, paired by prompt): primary **0.79 [0.75, 0.83]**; all 16
0.75 [0.69, 0.81]. The interval excludes 1 below. Per PROTOCOL.md: **the CuteAFD code gap goes with CuteAFD's serving of
the 6-bit core (native kernels, or its FP8-at-load reference), not the weight values alone.**

## Descriptive
- Finished 64/64 (V-K6), 63/64 (V-BF16, 1 capped looping). Median reasoning tokens 62,853 vs 61,129. Decode 103.9 vs
  103.7 tok/s. All tests pass 53 vs 58 of finished; mean share of tests passed 0.955 vs 0.957.

## Post hoc (not in the frozen rule): which CuteAFD arm differs
`analysis/cross_engine.py` -> `analysis/cross_engine.json`.
Cross-engine ratios on the same prompts and seeds (seeds do not give the same samples across engines, so this compares
per-prompt means of 4 replies; descriptive only):
| | p4-p15 | prompts above 1 | all 16 | prompts above 1 |
|---|---|---|---|---|
| C-K6 / V-K6 | 1.04 | 9 of 12 | 1.04 | 11 of 16 |
| C-K6 / V-BF16 | 1.04 | 9 of 12 | 1.04 | 12 of 16 |
| C-K6x / V-BF16 | 0.82 | 0 of 12 | 0.78 | 0 of 16 |
| C-K6x / V-K6 | 0.82 | 0 of 12 | 0.78 | 0 of 16 |
Medians: C-K6 63,732; V-K6 62,853; V-BF16 61,129; C-K6x 50,412. CuteAFD's native 6-bit core sits with both vLLM arms;
CuteAFD's BF16 core converted to FP8 at load is the arm that thinks shorter, on every prompt. Its test pass rate is not
lower (C-K6x 49, C-K6 50 of 64).

## What this says
- On the vLLM fork the core's weight values (6-bit rebuilt to BF16 vs original BF16) do not change code thinking length.
- The CuteAFD 1.26x is better described as the FP8-at-load BF16 core thinking about 20% shorter than the other three
  configurations, not the 6-bit core thinking longer.
- Source reading (CUTEAFD-FP8-PATH.md): on CuteAFD the BF16-core arm also runs the KDA projections, the vocabulary head
  and MLA/FFN prefill activations in FP8; the 6-bit arm does not. Which of these goes with the shorter reasoning is open.
