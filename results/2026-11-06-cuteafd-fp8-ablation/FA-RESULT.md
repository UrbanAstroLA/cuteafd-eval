# Which part of CuteAFD's FP8 path shortens code reasoning: result (read 2026-11-07 18:15)

Inputs: `analysis/FA-RESULT.json` (analyze_fa.py, frozen in FROZEN.json before the first request), `l/L-analysis.json`
(Block L analyzer, unchanged; not published, its per-reply fields are in `analysis/samples.csv`). Run 2026-11-06 22:25 to 2026-11-07 15:41, CuteAFD v4.0.0, BF16-core checkpoint. Every launch
showed the expected `kda_fp8` / `fp8_head` / `fp8_prefill` in its server log before any request. C-K6x and C-K6 are the
code study's arms (11-05), paired by (prompt, rep) and seed. Ratios above 1 = the first arm thought longer.

Control: replay of C-K6x p3 r3 on the unchanged config is identical in reasoning and content (60,617 reasoning chars each).

## Frozen reading (primary set p4-p15, 12 prompts; 95% bootstrap over prompts)
| Contrast | Ratio | 95% CI | Detected |
|---|---|---|---|
| Reference gap C-K6 / C-K6x | 1.26 | [1.24, 1.29] | yes |
| **Step: KDA projections BF16** F-kda / C-K6x | **1.31** | **[1.24, 1.38]** | **yes**, 12 of 12 prompts |
| Step: head BF16 F-head / F-kda | 1.02 | [0.97, 1.07] | no |
| Step: prefill activations unquantized F-pre / F-head | 0.99 | [0.97, 1.02] | no (47 pairs) |
| C-K6 / F-kda | 0.96 | [0.92, 1.01] | no |
| C-K6 / F-head | 0.94 | [0.91, 0.97] | yes |
| C-K6 / F-pre | 0.95 | [0.91, 0.98] | yes (47 pairs) |

- **Gap closed at F-kda**: C-K6 / F-kda includes 1 and F-kda / C-K6x excludes 1 above.
- **Attribution**: only the KDA step is detected; gap share 1.16 [0.95, 1.37] (whole gap within the interval).
- **Remainder clause**: C-K6 / F-pre excludes 1, but below 1: with all three switches off, the BF16-core arm thinks about
  6% *longer* than the native 6-bit core, not shorter. The clause was written for a remaining shortfall; there is none, so
  reading the overshoot is post hoc. It is detected from F-head on (C-K6 / F-head 0.94 [0.91, 0.97]), not at F-kda, and not
  on all 16 prompts. Not located: the head step (not detected on its own), chance, the parts the F arms do not change (FP8
  MLA/MLP projections, the core's format) or another difference not found in the source.

Secondary (all 16 prompts): KDA step 1.38 [1.29, 1.47], detected; head 0.99 [0.94, 1.04] and prefill 1.00 [0.97, 1.03] not
detected; C-K6 / F-pre 0.97 [0.94, 1.01] and C-K6 / F-head 0.98 [0.94, 1.02] include 1 (overshoot only on the new prompts).

## Descriptive (not in the rule)
| Arm | Finished | Capped (looping) | Median reasoning tokens | All tests pass | Mean share passed | Median decode tok/s |
|---|---|---|---|---|---|---|
| C-K6x | 64 | 0 | 50,412 | 49 | 0.936 | 121.8 |
| F-kda | 64 | 0 | 64,089 | 55 | 0.963 | 116.5 |
| F-head | 64 | 0 | 67,890 | 54 | 0.950 | 113.6 |
| F-pre | 63 | 1 (1), p7 r0 | 68,145 | 59 of 63 | 0.950 | 111.6 |
| C-K6 | 64 | 0 | 63,732 | 50 | 0.945 | 115.1 |
- Post hoc: all-pass discordant pairs favour the F arms (F-kda vs C-K6x 10 to 4; F-pre vs C-K6 13 to 4). Mean share of
  tests passed is close across arms (0.936-0.963). The C arms ran a day earlier on the same engine (control identical).
  Not a frozen measure; not read as a correctness effect.
- Decode cost of turning the switches off: about 4% (KDA), 7% (KDA + head), 8% (all three) versus C-K6x.
- KV pool at launch (server log, `pool N tokens`): F-ctrl (= C-K6x config) 1,931,264; F-kda 1,414,656; F-head and F-pre
  1,215,488. BF16 KDA costs about 27% of the pool, BF16 head a further 10% of the original pool (14% of F-kda's) on this checkpoint; all arms served 2 in flight.
- Earlier on K4 (cuteafd-eval F1-K4b, 2026-10-28): BF16 KDA was the largest single switch toward vLLM's precision at
  8-16K (KL -0.0035), and did not fit a serving launch with K4's experts.

## What this says
- On CuteAFD v4.0.0, the shorter code reasoning of the BF16-core checkpoint goes with the launcher's KDA setting: row128
  FP8 KDA projections (q/k/v and f_a/g_a/b packed into one FP8 operand, per-row x 128-K pow2 scales) and, on this two-GPU
  head split, the KDA output sharding that v4 runs only with FP8 KDA (`run-family.sh:2366`, `mod.rs:1296-1299` at v4.0.0;
  the native core runs without it, `mod.rs:1716-1722`). Switching the setting off changes both; which carries the length is
  not separated. With it off the gap to the native 6-bit core closes; the FP8 head and FP8 prefill activations show no step.
- MLA projections (including q_b and o_proj) stay FP8 in every F arm and the gap still closes: FP8 MLA projections show no
  measurable code-length shortening at this resolution.
- Consistent with the vLLM fork, where KDA projections are BF16 and the two cores think alike.
- The launcher's `auto` selects row128 KDA for any checkpoint without a native KDA format, including stock K4.
- Not separated: FP8 format vs the KDA split path vs the pow2 scale rule; which packed projections matter; interactions (cumulative design).
