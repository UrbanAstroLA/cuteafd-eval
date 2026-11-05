# Step 1 read: free generation (Block L stage L3, code and prose, CuteAFD v4.0.0), 2026-11-04

Input: `analysis/S1-RESULT.json` (`analysis/analyze_s1.py`, frozen). Reasoning tokens by re-tokenization of the saved
texts with the frozen Block L analyzer (`l/*.inner.json`; per request in `analysis/samples.csv`). 96 requests (3 arms x
32): 32 keys (content, prompt, rep), each with one seed shared by the three arms; 32 distinct seeds, none used in Block L
r1 or r2. All 96 finished (`stop`, under the 130,048 cap): 0 capped, 0 loops.

Direction: every ratio is the first-named arm over the second, so a value above 1 means the configuration with the
6-bit core (or with K4-Core-K6's experts) thought longer.

## Frozen reading (95% bootstrap over the 8 prompts primary, over the 32 pairs secondary)
| Contrast | a / b | Ratio | Prompts CI | Pairs CI | Code (4 prompts) | Prose (4 prompts) | Detected |
|---|---|---|---|---|---|---|---|
| core | C-K6 / C-K6x | 1.16 | [0.98, 1.36] | [1.01, 1.31] | 1.25 | 1.08 | no |
| experts | C-K6x / C-K4 | 0.99 | [0.93, 1.05] | [0.87, 1.12] | 1.02 | 0.97 | no |
| total | C-K6 / C-K4 | 1.15 | [0.97, 1.32] | [1.02, 1.29] | 1.27 | 1.04 | no |

Per prompt (code p0-p3; prose p0-p3): core 1.24, 1.37, 1.09, 1.32; 1.21, 1.65, 0.91, 0.74. Experts 1.08, 1.07, 1.08,
0.85; 0.96, 0.88, 1.09, 0.96. Total 1.35, 1.47, 1.17, 1.13; 1.16, 1.45, 0.99, 0.70.

## Against the observation that raised the question (post hoc, `analysis/BLOCK-L-POSTHOC.json`)
Block L, CuteAFD v4 run, K4-Core-K6 / K4 over two runs: code 1.43 [1.20, 1.59] (per prompt 1.61, 1.10, 1.50, 1.56),
prose 1.19 [1.06, 1.39], JSON 1.07 [0.99, 1.21], reasoning 1.05 [0.85, 1.39]. Same prompts here, new seeds: total code
1.27 (4 of 4 prompts above 1 again), prose 1.04 (2 of 4 above 1.1, one at 0.70).

## Read
- Under the frozen primary rule nothing is detected; the secondary pair-level intervals of core and total exclude 1.
  Direction and size: K4-Core-K6 thought about 15% longer than K4 overall, about 27% on code, about 4% on prose.
- The routed experts contribute nothing measurable (0.99, the narrowest interval of the three). The total is the core
  times the experts (1.16 x 0.99 = 1.15), so what difference there is goes with the 6-bit core.
- The gap is smaller than in the run that raised the question. That run was read because its difference stood out;
  a smaller value on new seeds is what that selection predicts, and does not by itself say the effect is absent.
- Decode speed (median tok/s, code / prose): C-K6 121 / 79, C-K6x 130 / 88, C-K4 129 / 88 (all 16 replies per content). The native 6-bit core is
  the slower part; with the BF16 core converted to FP8 at load, K4-Core-K6's experts decode as fast as K4's.
- Finished replies whose end repeats earlier text (the loop detector's onset; code answers restate code from the
  reasoning): C-K6 14, C-K6x 12, C-K4 8 of 32. Descriptive, not part of the frozen reading, and not loops: all finished.

## Scope
One engine and machine; 8 prompts (4 code, 4 prose) from Block L, 4 replies per prompt per arm. "BF16 core" here is
BF16 converted to FP8 at load (how CuteAFD serves K4). Routed experts compared as two whole quantizations.
