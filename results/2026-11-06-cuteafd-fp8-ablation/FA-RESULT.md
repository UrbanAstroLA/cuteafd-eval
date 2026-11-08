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
- Post hoc: all-pass discordant pairs favour the F arms (F-kda vs C-K6x 10 to 4; F-pre vs C-K6 13 to 4, all 64 pairs
  including F-pre's capped reply; the post hoc section below pairs finished replies only, 13 to 3). Mean share of
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


## Design context (added 2026-11-08)
The settings switched off here are the launcher's defaults, with reasons stated by the engine's author. At v4.0.0:
- The launcher comment above the GLM 5.3 Flash precision block (`scripts/launch/run-family.sh:2337-2351`): row128 KDA (FP8,
  one scale per row and 128 input columns) and an FP8 head on both layouts; on the two-GPU head split, token-row KDA output
  ownership, added because it avoids rounding the two GPUs' half-K BF16 partial outputs (its dated check: single-request
  decode +7.6%, paired top-1 453 -> 460 of 512, KL +0.0008).
- The model notes (`docs/models/glm5_flash.md:163-210`, "Default precision"): the trade of single-request decode speed
  (+9.0% on 1 RTX + 2 Sparks) against top-1 and KL on 512 teacher-forced positions, and that the speculation check "does
  not establish byte-identical speculative output".
- The `--kda-fp8` option text (`rust/crates/cuteafd-daemon/src/families/glm5_flash/mod.rs:189-197`): row128 costs top-1 on
  its check and doubles verify-vs-decode rounding, enough to flip greedy output under speculation.
- The model notes and the option text describe BF16 KDA as the default on the two-GPU split; the launcher comment and code
  select row128, which every launch here logged. The documents differ; the launcher's choice is what runs.
The cited checks are teacher-forced on 512 positions; this run measures free generation of long reasoning with speculative
decoding.

## Where in the engine (judgement from source and measurements; not isolated by its own run, added 2026-11-08)
Judged most likely on the generation path (decode and speculative verify); prefill is not excluded.
- Prompts are 1,155-1,758 tokens; median reasoning is 50-68K tokens per arm, so prefill is about 2-3% of the tokens.
- Speculative verify steps run on the decode programs (`engine.rs:4660`, `:4686`: "speculative steps are
  decode-shaped"); with FP8 KDA, decode rows read the FP8 copies and KDA output sharding is not limited to prefill
  (`engine.rs:3844-3847`, `:4666-4695`).
- Not excluded: the KDA setting also changes the KDA projections in prefill, and the recurrent state the prompt leaves
  seeds every later token. The prefill-activation switch (F-pre) covers the MLA and MLP activations only, not the KDA
  projections (the launcher's default list is mla,ffn), so it does not bear on this.
- FP8 MLA projections (MLA q_b and o_proj included) run on decode rows in every F arm and the gap still closes.
- Teacher-forced results elsewhere in this investigation (stop decision, KL) run through the prefill programs on
  science-question traces; they do not measure this path on code.
Open: KDA in prefill against generation; plain decode against speculative verify (with FP8 KDA, decode rows up to 64 take
the FP8 GEMV and wider verify steps W8A16); KDA format against output sharding.

## Post hoc: hidden tests across arms (added 2026-11-08; not in any frozen rule)
`analysis/pass_pairs.py` -> `analysis/PASS-PAIRS.json`: every contrast looked at (13), pairs = same prompt and seed with
both replies finished; all-pass difference in points, 95% bootstrap over the 16 prompts, and the Bonferroni interval for
13 looks.

| Contrast | All pass | Only first / only second passes | All-pass difference, 95% | Bonferroni (13 looks) | Share-passed difference |
|---|---|---|---|---|---|
| V-K6 vs C-K6 (same checkpoint, two engines) | 53 / 50 of 64 | 11 / 8 | +4.7 [-7.8, +18.8] | [-14.1, +23.4] | +1.0 [-5.7, +9.5] |
| V-K6 vs C-K6x | 53 / 49 of 64 | 10 / 6 | +6.2 [-4.7, +17.2] | [-9.4, +23.4] | +1.9 [-4.9, +8.7] |
| V-BF16 vs C-K6 | 58 / 49 of 63 | 12 / 3 | **+14.3 [+1.6, +28.1]** | [-3.2, +34.9] | +2.8 [-0.1, +6.7] |
| V-BF16 vs C-K6x | 58 / 49 of 63 | 13 / 4 | **+14.3 [+3.1, +26.2]** | [-1.6, +31.7] | +3.6 [+0.2, +7.9] |
| V-BF16 vs V-K6 | 58 / 53 of 63 | 10 / 5 | +7.9 [-3.1, +19.4] | [-7.8, +26.7] | +1.7 [-3.8, +7.4] |
| C-K6 vs C-K6x (native vs FP8-from-BF16 core) | 50 / 49 of 64 | 7 / 6 | +1.6 [-7.8, +10.9] | [-12.5, +17.2] | +0.9 [-3.6, +5.6] |
| F-kda vs C-K6x (the KDA step) | 55 / 49 of 64 | 10 / 4 | **+9.4 [+1.6, +18.8]** | [-1.6, +21.9] | +2.8 [-0.2, +6.7] |
| F-kda vs C-K6 | 55 / 50 of 64 | 8 / 3 | +7.8 [+0.0, +17.2] | [-3.1, +20.3] | +1.9 [-0.9, +5.5] |
| F-head vs C-K6x | 54 / 49 of 64 | 13 / 8 | +7.8 [-3.1, +20.3] | [-6.2, +26.6] | +1.5 [-4.0, +7.2] |
| F-head vs C-K6 | 54 / 50 of 64 | 11 / 7 | +6.2 [-3.1, +17.2] | [-7.8, +20.3] | +0.5 [-5.6, +7.5] |
| F-pre vs C-K6x | 59 / 48 of 63 | 15 / 4 | **+17.5 [+7.8, +28.6]** | [+4.8, +34.4] | +3.1 [-0.3, +7.2] |
| F-pre vs C-K6 | 59 / 49 of 63 | 13 / 3 | **+15.9 [+6.3, +27.0]** | [+3.2, +32.8] | +2.1 [-0.8, +5.9] |
| V-K6 vs F-kda | 53 / 55 of 64 | 7 / 9 | -3.1 [-14.1, +9.4] | [-20.3, +14.1] | -0.8 [-6.6, +4.8] |

- Direction: every arm with CuteAFD's FP8 settings switched off (F-kda, F-head, F-pre) and the vLLM BF16 core pass all
  tests more often than both code-study arms (C-K6, C-K6x). 95% intervals exclude 0 in 5 of 13 contrasts, all that way;
  allowing for 13 looks, only F-pre (all three settings off) against C-K6x and against C-K6. Other differences ride along:
  the F arms ran a day after the C arms (same engine and config; a replayed request was identical), and V-BF16 is another
  engine. The share of tests passed moves by up to about 4 points; one interval excludes 0.
- Passing does not follow length: C-K6 and C-K6x differ by about a fifth in reasoning and pass equally often; F-pre and
  C-K6 think about as long (F-pre 3-5% longer) and differ most in passing. The shorter reasoning is not shown to cost
  correctness. C-K6 has none of the FP8 settings and still passes less often than the F arms, so the direction is not
  "FP8 settings cost passes"; whether KDA and head weights at their original BF16 values raise the pass rate, against
  6-bit or FP8 values, is open (one prompt family, post hoc).
