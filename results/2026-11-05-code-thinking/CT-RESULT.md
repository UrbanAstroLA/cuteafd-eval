# Code thinking length, 6-bit core vs BF16 core, CuteAFD v4.0.0: result (read 2026-11-06 07:30)

Inputs: `analysis/CT-RESULT.json` (analyze_ct.py, frozen), `l/L-analysis.json` (Block L analyzer, unchanged; reasoning
tokens by re-tokenization, code checks). 128 requests (C-K6x 21:40-01:41, C-K6 01:41-07:11), 16 code prompts x 4
seeds, the same seed on both arms. All 128 finished (`stop`, under the 130,048 cap); none capped; no unpaired requests.
Ratio = C-K6 / C-K6x (above 1 = the 6-bit core thought longer). "BF16 core" here is BF16 converted to FP8 at load.

## Frozen reading
| Set | Prompts | Ratio | 95% CI over prompts | 95% CI over pairs | Prompts above 1 | Sign test |
|---|---|---|---|---|---|---|
| **p4-p15 (primary, new prompts)** | 12 | **1.26** | **[1.24, 1.29]** | [1.20, 1.33] | 12 of 12 | p = 0.0005 |
| all p0-p15 | 16 | 1.33 | [1.27, 1.40] | [1.26, 1.41] | 16 of 16 | p = 3e-5 |
| p0-p3 (Block L prompts) | 4 | 1.56 | [1.52, 1.62] | [1.40, 1.76] | 4 of 4 | p = 0.125 |

**Detected.** Per pair, C-K6 thought longer in 58 of 64 pairs (42 of 48 on p4-p15); single pairs range 0.86 to 2.62, so
the narrow prompt-level interval comes from consistent prompt means, not identical pairs.

## Descriptive
- Median reasoning tokens: C-K6 63,732; C-K6x 50,412. Median decode tok/s: C-K6 115, C-K6x 122.
- Tests (pytest, sandbox): all tests pass on 50 of 64 (C-K6) and 49 of 64 (C-K6x); mean share of tests passed 0.945 and
  0.936; the two arms agree on all-pass in 51 of 64 pairs. The extra thinking does not buy or cost correctness here.
- Finished replies whose end repeats earlier text (loop detector onset; code answers restate code from the reasoning;
  all finished, not loops): C-K6 51, C-K6x 44 of 64.
- Correction: `CT-RESULT.json` reports `all_tests_pass_of_finished: 0` for both arms. analyze_ct.py reads the per-arm
  `*.inner.json`, where code checks are still `pending`; the analyzer writes the checks only into `L-analysis.json`.
  The figures above are from `L-analysis.json`. The frozen ratio uses `reasoning_tokens`, which is in both files and
  identical; it is unaffected.

## Against earlier readings (same engine, same arms)
- Core-swap step 1, code (4 Block L prompts, other seeds): 1.25, prompt-level CI not excluding 1 (8-prompt primary).
- Block L v4 run, K4-Core-K6 / K4 (core and experts together): code 1.43.
- Here p0-p3 give 1.56 on new seeds; the 12 new prompts 1.26. The core accounts for the code gap seen in Block L.

## What this says
- On CuteAFD v4.0.0, with the routed experts held fixed, the native 6-bit core makes code replies think about 26% longer
  than the BF16 core converted to FP8 at load (33% over all 16 prompts), on every prompt, with no change in test pass rate.
- Earlier on the same engine: GPQA free generation and the GPQA stop decision showed no core difference. The effect is
  tied to code content (or long structured output), not reasoning in general.
- Not separated: 6-bit weights vs CuteAFD's native 6-bit kernel path. On the vLLM fork (route b) the 6-bit core is
  dequantized to BF16 at load, so the same prompts there would separate the two. Not run.
