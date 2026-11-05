# G2 result (screen) — read 2026-11-03 00:10, after Amendment 1 completed

Inputs: `analysis/G2-SCORES.json` (frozen chain), `analysis/G2-SCORES-A1.json` (same plus k6r2). Supplementary contrasts
below (KL k6 vs k6r2, pooled base) were computed after reading and are labelled post hoc.

## Run integrity
- 12 launches (k6, all, 9 groups, k6r2), all ready; every swap arm logged the expected swapped-matrix count; every capture
  exited 0 with chosen-token checks passing. vLLM K3.25 serving restored 2026-11-03 00:08.
- Trace set: 77 finished traces (tr 40, on 37) and 16 not finished; P-A 25 windows.
- KV pool varied 1.36-1.40M tokens across launches (largest sequence < 100K; no effect on captures).

## Stop decision (teacher-forced on fixed traces)

| Arm | log p(</think>) at close, mean | Δ vs k6 [95% CI] | </think> top-1 at close |
|---|---|---|---|
| k6 (6-bit core) | -0.357 | — | 0.909 |
| **k6r2 (same, 2nd launch)** | -0.351 | +0.006 [-0.005, +0.018] | 0.909 |
| **all (BF16 core)** | -0.352 | +0.005 [-0.009, +0.019] | 0.909 |
| kda_qkv | -0.354 | +0.003 [-0.010, +0.017] | 0.909 |
| kda_o | -0.348 | +0.009 [-0.001, +0.020] | 0.909 |
| mla_a | -0.358 | -0.001 [-0.014, +0.010] | 0.909 |
| mla_q_b | -0.343 | +0.014 [+0.002, +0.026] | 0.909 |
| mla_o | -0.340 | +0.017 [+0.007, +0.029] | 0.909 |
| dense | -0.347 | +0.010 [-0.003, +0.025] | 0.909 |
| shared_gu | -0.352 | +0.004 [-0.011, +0.020] | 0.909 |
| shared_down | -0.343 | +0.014 [-0.002, +0.028] | 0.909 |
| lm_head | -0.353 | +0.004 [-0.010, +0.014] | 0.909 |

Hazard (mean p(</think>) over the 512 rows before the close) is 0.00026-0.00027 on every arm; max p(</think>) on the
16 not-finished traces is ~0 on every arm. The 7 traces where </think> is not top-1 at the close are the same 7 on
every arm.

**Reading rule (frozen + Amendment 1):** mla_q_b and mla_o meet it on lp_close (closure >= 0.5, CI excludes 0,
|Δ| > |k6r2 - k6| = 0.006). No group meets it on hazard or max p. The frozen rule alone would also flag k6r2 on hazard
(a no-change launch), which is what Amendment 1 guards against.

**Context for the two flags:**
- The reference gap itself (all - k6 = +0.005) is smaller than launch-to-launch noise (+0.006) and its CI includes 0, so
  closure ratios (2.9, 3.5) divide by a gap indistinguishable from zero.
- Post hoc: against k6r2 as base, both CIs include 0 (mla_o +0.011 [-0.002, +0.027]; mla_q_b +0.008 [-0.001, +0.017]);
  against the mean of k6 and k6r2 both exclude 0 (+0.014, +0.011).
- 9 groups x 3 measures = 27 tests; ~1.4 hits at 95% are expected with no effect.
- Size: +0.014 in log p is a ~1.4% relative change in p(</think>) at the close (mean p ≈ 0.70, median 0.94).

## Distribution distance

| Measure | Value |
|---|---|
| top-64 KL(all ‖ k6), every trace row | 0.0071 nats/token |
| top-64 KL(k6 ‖ k6r2), every trace row (post hoc) | 0.0040 nats/token |
| top-64 KL(all ‖ k6), last 512 rows before close | 0.0070 |
| top-64 KL(k6 ‖ k6r2), last 512 rows (post hoc) | 0.0038 |

More than half of the core-swap distance on long traces is the size of launch-to-launch variation (multi-chunk prefill).
Single-group swaps reduce KL to the all-BF16 arm by 0.0000-0.0005 each (largest: kda_o, kda_qkv, shared_gu, dense).

P-A (25 windows, short, single-chunk; k6r2 - k6 +0.0000007 [-0.0000013, +0.0000023]): KL to the BF16 teacher 0.0268 (k6) vs 0.0260 (all),
Δ -0.0008 [-0.0019, +0.0002]. lm_head Δ -0.0001 [-0.00015, -0.00007] (excludes 0, small). Per-domain cells (3-8
windows each) are descriptive only.

## What this says
- On fixed traces, replacing the 316 six-bit core tensors with BF16 does not measurably change the stop decision:
  p(</think>) at the close, the pre-close hazard and the top-1 at the close are within launch-to-launch variation.
- Per-token measures cannot see compounding over tens of thousands of free-generated tokens; G4 (free generation) is
  the instrument for that.
- Scope: only the core was swapped. The routed experts, which hold most of the parameters, were not in this experiment.

*Correction (2026-11-03, before publication).* The P-A line first read "k6r2 = k6 exactly". The two launches are not
bit-identical on P-A (KL 0.0268353 vs 0.0268360, NLL 1.06810 vs 1.06812); their difference is +0.0000007
[-0.0000013, +0.0000023]. Post-hoc contrasts quoted above are reproduced by `analysis/post_hoc.py`
(`analysis/POST-HOC.json`).

*Note (2026-11-04, after publication).* The max p(</think>) measure on the 16 not-finished traces falls on the first
scored row (the opening of the reasoning span) in 180 of 192 trace-arms. That row is the same for every trace of a
question, so the measure is mostly a per-question value counted once per trace (question 13 is 5 of the 16). The
reading above (no group meets the rule on max p) is unchanged; the measure says little about stopping later in a
reply. The same holds on CuteAFD (results/2026-11-03-cuteafd-core-swap, `S2-READ.md`), where the routed experts are
also compared.
