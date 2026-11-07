# Code thinking length on the vLLM fork: 6-bit core vs BF16 core (frozen 2026-11-06, before the first launch)

Follows `<ct-run>/CT-RESULT.md` (CuteAFD v4.0.0: C-K6 / C-K6x reasoning tokens 1.26
[1.24, 1.29] on 12 new code prompts). That run cannot separate the 6-bit weights from CuteAFD's native 6-bit kernel path
(and its BF16 arm is FP8 at load). On the vLLM fork with the route-b loader the 6-bit core is dequantized to BF16 at load
and runs on the same BF16 kernels as a native BF16 core, so the only difference between arms is the weight values.

## Design (everything as the CuteAFD study except the engine)
- Prompts, seeds, wrapper, cap, concurrency, thinking: the CuteAFD study's driver imported unchanged
  (`drivers/code_thinking_v.py` adds only an engine entry naming the served image). 16 code prompts x 4 seeds,
  seed 2,026,110,500 + 100 * prompt + rep, the same on both arms and the same as the CuteAFD study. Cap 130,048, 2 in flight.
- Arms (vLLM fork v0.9.2-experimental image 5fc05b7c, route-b loader = local loader modification, the swap launch
  script unchanged, loader counts checked at launch): **V-BF16** (SWAP_SET=all: the whole core native BF16, 316 matrices)
  then **V-K6** (6-bit core dequantized to BF16). Routed experts K4 in both.
- Reasoning tokens by re-tokenization and code checks: the Block L analyzer (the CuteAFD study's copy, unchanged).

## Reading (analysis/analyze_vct.py)
- **Primary**: ratio V-K6 / V-BF16 over p4-p15, exp(mean log ratio over seed pairs where both finished), 95% bootstrap
  over prompts (4,000, seed 20261106). **Detected** if the interval excludes 1. Secondary: all 16, p0-p3, pair intervals,
  sign counts.
- **Engine comparison** (stated now): vLLM log ratio minus CuteAFD log ratio, paired by prompt, bootstrap over prompts.
  - vLLM detected above 1 and the comparison interval includes 1: the gap goes with the 6-bit weights (both engines).
  - vLLM not detected and the comparison interval excludes 1 below: the gap goes with CuteAFD's serving of the 6-bit
    core (native kernels, or its FP8-at-load reference), not the weight values alone.
  - Anything else: partial; reported as measured.
- **Descriptive** (not part of any rule): finished, capped, capped looping, finished with a terminal repeat, all-tests-pass,
  mean share of tests passed, median reasoning tokens, median decode tok/s, per-prompt ratios on both engines.

## Scope
One machine; one prompt family (16 Python projects); thinking on. The two engines also differ in everything else (attention
kernels, sampler); the comparison is of the core contrast within each engine, not of absolute lengths.
