# G4 protocol (reduced) — frozen 2026-11-03, after G2 was read, before any G4 sample

G3 (bisection) skipped: G2 found no core group whose
effect on the stop measures stands clear of launch-to-launch variation (G2-RESULT.md).

## Question
On free generation, does loading the 316 core tensors as BF16 change how long K4-Core-K6 thinks, compared with the
6-bit core rebuilt by route b? G2 measured the stop decision per token on fixed traces; G4 measures the
compounded effect over a whole reply.

## Design
| Item | Value |
|---|---|
| Engine | vLLM fork v0.9.2-experimental + route b, image sha256:5fc05b7c…, start-v092x-swap-capture.sh |
| Arms | `k6` (ARM=k6, no swap) and `all` (ARM=k6swap, SWAP_SET=all, 316 matrices from the BF16 file); one launch each |
| Question | GPQA diamond doc 12 (length instrument: G1b sd of log tokens 0.19 over 6 samples, 25-39K tokens, 6/6 correct) |
| Samples | 12 per arm, seeds 51201-51212 (50000 + 100 x 12 + rep), the same seeds in both arms |
| Sampling | as G1b: temperature 1.0, top_p 0.95, thinking on, max_tokens 327,680, streamed, 6 in flight |
| Budget | 4,500 s per arm; requests still running at the cut are kept as `unfinished_at_cut` |
| Driver | drivers/gen_traces.py `--docs 12 --n 12 --concurrency 6 --seed-base 50000 --budget-s 4500` |

The tail instrument (knife-edge questions 186, 81, 13, 86) is dropped: with G1b's spread it needs hundreds of samples
per arm.

## Reading (frozen)
- Primary: delta = mean(log completion tokens | all) - mean(log completion tokens | k6), 95% bootstrap interval
  (2,000 replicates, resampling samples within each arm, seed 20261103); reported as a ratio exp(delta).
- A shift is detected when the interval excludes 0. "No shift of 1.25x or more" when the interval lies inside
  +-log(1.25). Anything else is inconclusive.
- Completion tokens include the answer (a few hundred tokens; thinking dominates). Samples without a usage record (cut,
  error) are counted and listed, not imputed.
- Secondary, descriptive: seed-paired delta (same seed diverges once the weights differ, so pairing is weak), class
  counts, answer letter vs the gold (D) (reported, not used to select), G1b's 6 question-12 samples as context.
- Resolution: with sd 0.19 and 12 per arm, 80% power at alpha 0.05 for about a 1.24x shift. If the observed sd is
  larger, the resolution is coarser and is stated with the result.
- Scope: one question, one engine, core only (routed experts untouched). A null result does not speak for other
  questions or for the expert quantization.

## Change to a G2 input
drivers/gen_traces.py gained `--seed-base` (default 40000 reproduces G1b's seeds exactly) and records it in plan.json.
FROZEN.json's hash for that file refers to the version before this option; FROZEN-G4.json pins the current one.

## Run
`chain-g4.sh` in systemd unit `local-thinking-g4`; vLLM K3.25 serving restored on every exit path.
Expected wall time ~1.5 h (2 launches x ~6 min, 2 x ~25-40 min generation, restore ~7 min).
Output: g4/<arm>/, analysis/G4-RESULT.json, logs/g4*.log.
