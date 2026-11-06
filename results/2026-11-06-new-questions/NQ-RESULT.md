# New GPQA questions: result (read 2026-11-06 10:00)

Inputs: `analysis/NQ.json` (analyze_nq.py, frozen in FROZEN.json before the first launch), post hoc lines marked.
Run 07:20-09:44: K4-Core-K6 (vLLM fork, route b) wrote 90 replies on 30 new questions (3 seeds each); all 90 finished;
set nq = 88 finished traces on 30 questions (2 over the 96K limit) + 0 not finished. Launches k6-a, qbo-a, all, k6-b,
qbo-b (loader counts confirmed); CuteAFD C-K6, C-K6x. Differences are the BF16 side minus the 6-bit side.

## Frozen reading (vLLM, q_b + o_proj vs K4-Core-K6)
- lp_close qbo - k6: **-0.0032 [-0.0161, +0.0064]** clustered by 30 questions. Launch band 0.0039; pairings -0.0063 to
  -0.0000. **Not replicated at this size**; the earlier +0.0118 lies outside the new interval.
- Pooled with the earlier 11 questions (41 questions, 165 traces): +0.0038 [-0.0046, +0.0105].
- Secondary: qbo - all +0.0077 [-0.0025, +0.0185]; all - k6 -0.0109 [-0.0315, +0.0046]. Hazard: no change.

## CuteAFD (6-bit core vs BF16 core, FP8 at load)
- lp_close C-K6x - C-K6: -0.0144 [-0.0497, +0.0187], not detected (rule: interval excludes 0). Pooled 41 questions:
  -0.0028 [-0.0263, +0.0195]. Same direction as vLLM's whole-core contrast (-0.0109); per-trace correlation 0.29.

## Descriptive
- Generation: 90/90 finished, 87 correct (96.7%); completion tokens median 2.4K (min 408, max 121K). The random draw is
  mostly easy for this model; the earlier 11 questions were picked as loop-prone or high-variance.
- Last-512 mean log p(</think>) (the approach to the close, where p is around 1e-6): vLLM all - k6 -0.114
  [-0.132, -0.096]; CuteAFD C-K6x - C-K6 +0.106 [+0.064, +0.148]. Opposite signs on the two engines, as in the earlier
  position analysis (-0.116 and +0.057). A tail-of-distribution measure; not the stop decision itself (hazard unchanged).
- Top-64 KL against k6-a (mean per trace): k6-b 0.0025 (launch to launch), qbo 0.0067, all 0.0074, C-K6 0.0076,
  C-K6x 0.0125. Trace NLL: 0.410-0.411 for every vLLM arm and C-K6, 0.419 for C-K6x.

## Post hoc (not in the frozen rule)
- Saturation check: on these questions p(</think>) at the close is near 1 (median 0.9988; earlier set 0.934). Restricted
  to traces where K4-Core-K6's lp_close < -0.01: new 38 traces / 18 questions -0.0074 [-0.0369, +0.0160]; earlier
  41 traces +0.0221 [+0.0090, +0.0372]. The non-replication is not explained by saturation.

## What this says
- The q_b + o_proj stop-decision shift measured on the earlier 11 questions does not appear on 30 new
  questions, including their non-saturated traces. On present evidence it is specific to those questions, not a
  general property of the layout. Pooled over 41 questions: no detectable shift.
- Neither engine shows a core effect on the GPQA stop decision (consistent with every earlier GPQA reading).
- Thinking length in free generation for the q_b + o_proj layout: not measured (code thinking length differs by core on CuteAFD;
  the vLLM code run is in progress).
