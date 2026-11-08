# Which part of CuteAFD's FP8 path shortens code reasoning? (frozen 2026-11-06, before any request)

## Question
On CuteAFD v4.0.0 the BF16-core checkpoint (C-K6x) thinks about 0.79x as long on code as the native 6-bit core (C-K6), while
on the vLLM fork the 6-bit and BF16 cores think alike (`results/2026-11-06-vllm-code-thinking/VCT-RESULT.md`). The source
reading (`CUTEAFD-FP8-PATH.md` there) lists what changes with the core's format on CuteAFD: FP8 KDA projections, FP8
vocabulary head (the drafter reads it), FP8 prefill activations, FP8 MLA/MLP projections. The first three have launch
settings. This run switches them off cumulatively.

## Arms (CuteAFD v4.0.0, BF16-core checkpoint, serving config of the code study's C-K6x, launcher unmodified)
| Arm | Launch settings (`run.sh --set`) | KDA | Head | Prefill activations |
|---|---|---|---|---|
| C-K6x (code study, 11-05) | none | FP8 | FP8 | FP8 (MLA, FFN) |
| F-kda | GLM5_FLASH_KDA_FP8=off | BF16 | FP8 | FP8 |
| F-head | + GLM5_FLASH_FP8_HEAD=off | BF16 | BF16 | FP8 |
| F-pre | + GLM5_FLASH_FP8_PREFILL=off | BF16 | BF16 | none |
| C-K6 (code study) | native 6-bit core | 6-bit | 6-bit | none |
Each launch must show the expected `kda_fp8`, `fp8_head` and `fp8_prefill` in its server log before any request, or the arm is
not run. MLA and MLP projections stay FP8 in every F arm (no BF16 option on v4).

Requests: the code study's driver unchanged: 16 code prompts x 4 replies, seed = 2_026_110_500 + 100 * prompt + rep, cap
130,048, 2 in flight, thinking on. Same engine and seeds as C-K6x and C-K6, so arms pair by (prompt, rep).
Control (descriptive): one replay of C-K6x p3 r3 on the unchanged config; identical text would confirm the engine reproduces
the 11-05 run; a difference is not decisive (the original ran with a second request in flight).

## Reading (frozen)
Estimator as the code study: ratio of reasoning tokens, seed-paired, exp(mean log ratio), 95% bootstrap over prompts
(4,000, seed 20261106). Primary set: the 12 new prompts p4-p15; secondary: all 16.
- **Step contrasts**: F-kda / C-K6x, F-head / F-kda, F-pre / F-head. A step is **detected** when its interval excludes 1.
- **Gap closed at arm X**: C-K6 / X interval includes 1 and X / C-K6x interval excludes 1 above.
- **Attribution**: the pieces whose steps are detected account for the gap in proportion to their gap shares
  (log(X / C-K6x) / log(C-K6 / C-K6x), bootstrapped). If C-K6 / F-pre still excludes 1, the remainder lies in what the F arms
  do not change (the FP8 MLA/MLP projections, or another difference not found in the source).
- An arm that does not run, or runs partly, is reported as such; no step is read across a missing arm.

## Descriptive (not part of the rule)
Per arm: finished, capped, capped looping, finished with a terminal repeat, all tests pass, share of tests passed, median
reasoning tokens, median decode tok/s; per-prompt ratios; the control.

## Scope
One checkpoint, one engine version, 16 Python projects. Cumulative design: a step's effect is measured with the earlier
pieces already off; interactions between pieces are not separated.
