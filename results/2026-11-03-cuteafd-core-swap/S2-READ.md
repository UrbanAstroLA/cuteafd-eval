# Step 2 read: fixed traces (the stop decision), CuteAFD v4.0.0, 2026-11-03

Inputs: `analysis/S2-SCORES-base-C-K6.json` (core and total; second launch), `analysis/S2-SCORES-base-C-K6x.json`
(experts), `analysis/S2-IDENTITY.json`; per-probe timing and checks in `analysis/s2-probes.csv`. The 93 traces of the
vLLM investigation (77 finished, 16 not; GPQA reasoning, generated on the vLLM fork), token ids unchanged; 93,670
scored rows per arm; the longest trace (95,362 tokens) scored in 88 s. score_stop.py reports arm minus base; below,
differences are stated as K4-Core-K6's side minus the other (negative = K4-Core-K6's side less ready to stop).

## Frozen reading
- Cross-launch: C-K6 and C-K6r2 bit-identical on 93/93 traces and 93,670/93,670 rows (logits hash per row). No launch
  variation, so the rule is "the interval excludes 0".
- log p(</think>) where the trace closed (77 finished): core C-K6 - C-K6x -0.011 [-0.039, +0.017]; experts C-K6x - C-K4
  +0.004 [-0.025, +0.031]; total C-K6 - C-K4 -0.007 [-0.044, +0.026]. Not detected. Per trace, C-K6x above C-K6 on
  35 of 77, C-K4 above C-K6x on 38 of 77.
- Mean p(</think>) over the 512 rows before the close: not detected in any contrast. </think> the top token at the
  close: 0.909 in every arm.
- Max p(</think>) on the 16 unfinished traces: the intervals of experts and total exclude 0 (C-K4 higher); core not
  detected. See the post hoc check below before reading this.
- Top-64 KL between arms over all rows (nats per token): core (C-K6 vs C-K6x) 0.0127; experts (C-K4 vs C-K6x)
  0.0203, (C-K6x vs C-K4) 0.0212; total (C-K6 vs C-K4) 0.0259.

## Post hoc (`analysis/post_hoc_s2.py` -> `analysis/POST-HOC-S2.json`; not in the frozen protocol)
- The per-trace max p(</think>) falls on the first scored row (the opening of the reasoning span) in 46 of 48
  trace-arms here, and in 180 of 192 on the vLLM investigation's captures. That row is the same for every trace of a
  question, so the measure is mostly a per-question value counted once per trace; question 13 is 5 of the 16 unfinished
  traces and carries the max-p result (C-K4 1.49e-4 against C-K6x 2.40e-5).
- With the opening row removed, max p is about 1e-6 and the order of the arms changes from question to question (C-K4
  highest on 81, 127 and 88, lowest on 13 and 79). No consistent arm difference on unfinished traces.

## Read
- On these traces neither the 6-bit core nor the routed experts changes how ready the model is to stop where it
  stopped. The experts move the next-token distribution more than the core does (KL about 1.6x), without moving the
  stop decision.
- The traces are GPQA reasoning, the content where free generation shows no length difference (Block L reasoning 1.05
  [0.85, 1.39]; vLLM G4, finished replies, 6-bit / BF16 1.03). The stop decision on code text was not scored.

## Scope
Teacher-forced vLLM-generated GPQA traces, not Block L code or prose. One engine and machine. KL is top-64 (a lower
bound), not full vocabulary.
