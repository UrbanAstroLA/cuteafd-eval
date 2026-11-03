# Amendment 1 (written 2026-11-02 ~19:00, before any G2 capture or score was read)

## 1. Launch-to-launch noise floor for G2

vLLM's multi-chunk prefill is not bit-identical between launches, and the frozen G2 design captures each arm
once. Added after the frozen chain ends: a second launch of the base arm (`k6r2`: ARM=k6, no swap) with the same captures
(pa, tr, on), then vLLM K3.25 serving restored. Script `amend-1.sh` (frozen in `FROZEN-A1.json`).

Reading-rule addition: a group "moves" a stop measure only if, besides the frozen conditions (closure >= 0.5 and the
bootstrap interval of arm - k6 excluding 0), |mean(arm - k6)| exceeds |mean(k6r2 - k6)| on the same traces. The k6r2 - k6
difference and its interval are reported for every measure, P-A KL included.

## 2. G4 redesign from the G1b spread (descriptive basis: G1b, 4-6 samples per question)

Pooled within-question sd of log thinking tokens on K4-Core-K6 (route b) is 1.56 (question 12: 0.17; 81: 2.77). With
8 samples per question, G4 would detect only changes of about 2x or more in typical thinking length. G4 therefore uses two
instruments, chosen per question from K4-Core-K6's own spread before any swap arm generates:
- length instrument: steady long thinkers (sd of log tokens <= 0.5; from G1b, question 12), enough samples per arm to
  detect a 1.25x shift (~9-15 per question);
- tail instrument: knife-edge questions (186, 81, 13, 86): share of replies longer than 32K tokens or hitting the cap,
  reported with its interval; secondary, descriptive unless the samples suffice.
Sample sizes are fixed from the G1b spread and the G2 result before G4 runs, and recorded in a G4 protocol.
