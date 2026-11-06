# vLLM q_b + o_proj arm: result (read 2026-11-05 21:45)

Inputs: `analysis/QBO.json` (analyze_qbo.py, frozen in FROZEN-QBO.json before the first launch; all frozen files
unchanged at analysis), `analysis/POSTHOC-QBO-ALL.json` (posthoc_qbo_all.py, after reading). Launches k6-a, qbo-a, k6-b,
qbo-b (vLLM fork v0.9.2-experimental, route b; qbo = mla_q_b, mla_o, kda_o, 56 matrices native BF16, loader confirmed);
93 traces captured on every launch; 77 finished traces, 11 questions.

## Frozen reading
- lp_close, qbo minus K4-Core-K6 (launch means): **+0.0118 [+0.0047, +0.0205]** clustered by question; +0.0118
  [+0.0009, +0.0225] over traces. Within-arm launch differences: k6 -0.0018, qbo -0.0007 (band 0.0018). The four
  cross-launch pairings: +0.0106 to +0.0131, all positive. Against the G2 k6 and k6r2 launches: +0.0098 to +0.0166.
  **Supported** under the rule written before the launch.
- Size: +0.012 in log p(</think>) at the close, about a 1.2% relative change in p(</think>) where the trace closed.
  The single-group G2 flags summed to about +0.04; the combined arm is a third of that.
- Hazard (mean p(</think>) over the 512 rows before the close): no change (0.0000 in every pairing).
  Last-512 mean log p(</think>): +0.008 [-0.012, +0.028], not detected.
- Position: KL to K4-Core-K6 does not grow with position (slope -0.022 per doubling, as every swap arm; launch-to-launch
  +0.0002); lp_close delta does not grow with trace length (slopes -0.003 to +0.001, intervals include 0);
  last-512 slope -0.004 to -0.008 (opposite to growth).

## Post hoc (not in the frozen rule)
- Against the mean of all four K4-Core-K6 launches (G2 k6, k6r2; k6-a, k6-b): whole-core BF16 (G2 "all") +0.0011
  [-0.0081, +0.0106]; qbo-a +0.0129, qbo-b +0.0122; single groups mla_q_b +0.0100, mla_o +0.0131, kda_o +0.0053.
- qbo minus whole-core BF16: +0.0114 [+0.0056, +0.0195]. Restoring the rest of the core as well removes the shift: the
  effect belongs to the mixed configuration (q_b and o_proj BF16, the rest of the core 6-bit), not to "more precision".
  The whole-core arm is a single launch (K4-Core-K6 launches spread -0.0038 to +0.0024 around their mean).

## What this says
- On these GPQA traces, on the vLLM fork, a checkpoint with q_b and o_proj in BF16 and the rest of the core 6-bit is slightly more ready to stop where the trace stopped than K4-Core-K6. Real
  against launch noise; small; no build-up with position or trace length.
- The whole-core BF16 swap shows no such shift, so this is not a measure of the 6-bit core's cost.
- Not measured: thinking length in free generation, code text, CuteAFD (cannot load a partial core in v4.0.0).
