# G4 result (reduced) — read 2026-11-03 01:40

Protocol: G4-PROTOCOL.md (frozen before any sample). Data: g4/k6, g4/all; analysis/G4-RESULT.json.
Run: k6 ready 00:22, all ready 01:10, done 01:33; vLLM K3.25 serving restored 01:40. 24/24 samples returned.

| Arm | ok / loop | Completion tokens (sorted) | Median | Correct (D) |
|---|---|---|---|---|
| k6 (6-bit core) | 11 / 1 | 23.4K 23.9K 24.1K 26.1K 28.8K 31.9K 32.0K 36.1K 43.5K 45.6K 51.5K **327,680 (loop, cap)** | 32.0K | 11 (loop: no answer) |
| all (BF16 core) | 12 / 0 | 17.1K 20.5K 25.6K 27.8K 29.0K 30.7K 33.8K 33.8K 38.7K 42.6K 45.0K 45.3K | 33.8K | 11 |

**Primary (frozen):** ratio all/k6 of geometric-mean completion tokens 0.80, 95% interval [0.51, 1.14].
Interval includes 1 and is wider than [0.8, 1.25]: **inconclusive**. The width comes from the one k6 loop
(sd of log tokens 0.72 in k6 vs 0.31 in all).

**Post hoc (labelled; not the frozen reading):** finished replies only (11 vs 12): ratio 0.97 [0.78, 1.21];
sd of log tokens 0.28 and 0.31, larger than G1b's 0.19, so the resolution is about 1.3x, not the planned 1.24x.

**The loop:** k6 rep 3 (seed 51203) repeated one CIP-priority sentence until the 327,680 cap (1.49M characters
of reasoning, no answer). Question 12 had not looped in G1b (0/6); across G1b and G4 the 6-bit core looped 1 in 18
on this question, the BF16 core 0 in 12. One event cannot separate a core effect from chance (two-sided Fisher
p = 1.0).

## What this says
- Finished reply lengths on question 12 are the same within ~1.3x on the 6-bit and BF16 cores (medians 32.0K, 33.8K).
- The visible difference is a single runaway loop on the 6-bit core; whether the core changes the loop rate is
  not settled by these samples.
- Together with G2: no measurable core effect on the stop decision per token, nor on finished length. Not tested:
  the routed experts; other questions; other engines.
