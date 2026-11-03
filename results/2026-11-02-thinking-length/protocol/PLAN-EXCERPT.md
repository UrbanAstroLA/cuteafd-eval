# Thinking length and the quantized core: the frozen plan (excerpt)

Excerpt of the plan frozen in `FROZEN.json` on 2026-11-02 before the first G2 capture (whole file sha256 `3cf93c52175a60af205ec95ba2ed699146d5f368b99b7b3a01291e05431d5ebb`): the trace set, the knife-edge questions, the stages and the G2 reading rule as written. Left out: the opening notes and the discovery list (planning context), and attributions of suggestions made in private conversation. [V] verified, [I] inferred at the time of writing.

## Trace set from the looping investigation (found 2026-11-02) [V]

The main GPQA runs logged counts and hashes only (lm-eval keeps the final answer, not the reasoning). The hard-question
probes of the looping investigation (2026-09-29 to 10-09, `<runs>/diagnostics/*`) stored the full reasoning text
per sample: 649 samples on GPQA documents 88, 79, 13, 127 and 121 (plus 9 on 90), mostly K3.25, some K4, tpurtell
v0.7.0 / v0.8.0 era. 378 finished (`stop`: the `</think>` position is known), 170 ended in a repetition loop and 73
exhausted the cap without looping (`length`), 19 were unfinished at a cut. Use: teacher-force the same text through every
swap arm (paired; off-policy for K4-Core-K6, which is fine for comparing arms on identical text) and record, per arm,
log p(`</think>`) at the true close, the stop hazard over the last N reasoning tokens of finished samples, and the
largest p(`</think>`) along looped samples (did any arm want to stop where the run did not). Needs one addition to the
vLLM capture plugin: the log-probability of token 154842 at every position, not only top-20. Cost: subsample to ~60
finished + ~30 looped/exhausted (~2-3M tokens per arm, ~7-10 min of prefill per arm) [I]. GPQA question text stays
unpublished (dataset terms); results carry document ids only.

## Knife-edge questions [V]

Which GPQA questions vary most in thinking length? From the published local-inference-evals records (198 questions,
9 logged replies each over 10 runs; completion tokens include the answer, thinking dominates):

| Measure | Top questions |
|---|---|
| spread of log tokens across all runs (mixed engines, checkpoints, seeds) | 12, 120, 186, 165, 81, 121, 75 |
| same configuration, three seeds (K4 v0.9.1 c4; K3.25 v0.9.1), mean sd of log tokens | **186, 12, 81**, 86, 74, **120**, 101, 55, 13 |

186, 12, 81 and 120 lead on both: the same configuration sometimes stops in a few thousand tokens and sometimes thinks
past 100K (question 12: median 20K, max/min ~1,500x). The looping-probe questions are a different kind: 79 and 88 have a
median at the 327,680 cap (chronically long) and rank 62nd and 18th on same-configuration spread; 13 (9th) and 121 (28th)
are the probe questions that also vary. Median length and spread correlate only weakly (r = 0.24).
Use: the knife-edge questions are where a small core change is most likely to tip the stop decision; the chronically long
ones test whether the model can stop at all. Both stay in the design.

## Stages (each needs maintainer approval)

| Stage | What | Engine | GPU wall time |
|---|---|---|---|
| G0 | loader switch written and CPU-tested (selected owners load BF16 bytes; others unchanged, hashes logged) | — | 0 |
| G1 | optional behaviour baseline: GPQA K4 vs K4-Core-K6, 2 passes each, request seeds 1234/1235, questions paired (lower priority now that G1b and G4 use the knife-edge set) | CuteAFD v4 (native K6), 524K | ~8-11 h [I] |
| G1b | on-policy traces: K4-Core-K6 (route b, no swap) generates 8 samples on each of 186, 12, 81, 120, 86, 74 and 13 (default sampling, distinct seeds recorded, cap 327,680, reasoning text kept); gives K4-Core-K6's own spread on these questions and adds on-policy traces to the G2 trace set. Runs first in the G2 session (same launch) | vLLM fork + route b | ~1.5-2 h [I] |
| G2 | screen: arms = K6 core (route b), all-BF16 core, and ~9 groups swapped to BF16 one group at a time (KDA q/k/v, KDA o, MLA q_a+kv_a, MLA q_b, MLA o, dense MLP, shared expert gate/up, shared expert down, lm_head); per arm P-A and P-B (reduced dumps, top-64 KL) + stop hazard on the trace set (looping probes + G1b on-policy traces) | vLLM fork + route b | ~11 arms x ~25-30 min = ~5-6 h [I] |
| G3 | narrow: the group(s) that move the stop measures, split by layer range (bisection) | vLLM fork + route b | ~2-4 h [I] |
| G4 | behaviour check on the knife-edge set: K6-core, all-BF16-core and the 1-2 candidate swaps, 8 samples per question on the G1b questions, same seeds across arms; thinking tokens per question (paired), finish-before-cap share. Full GPQA only if the knife-edge result needs confirming | vLLM fork + route b | ~1-2 h per arm, ~4-8 h [I] |

Reading rule (frozen before G2): per arm, change against the K6-core arm and against the all-BF16-core arm for (a) P-A
KL overall and reasoning-termination domain, (b) P-B KL at the 32 close positions, (c) mean stop log-probability on the
trace set; a group "moves" a measure when its swap closes at least half the K6-core to all-BF16-core gap with a window
bootstrap interval excluding 0. G4 reads thinking tokens per question (paired), finish-before-cap share and empty
answers; accuracy reported, not used to select.

## Caveats

- Route b is not CuteAFD's native arithmetic (native-K6 plan, gates G0-G5); attribution within route b is clean, transfer to
  CuteAFD is inferred until checked.
- Thinking length is also engine-dependent (Block L: vLLM fork thinks longest on K4), so G1 and G4 compare arms on one
  engine only.
- GPQA empty answers are rare (0-9 of 198 per pass), hence the knife-edge set for G4; its questions were chosen from
  data on K3.25 and K4 (v0.9.1), so K4-Core-K6's own spread on them is measured in G1b before G4 relies on it.
