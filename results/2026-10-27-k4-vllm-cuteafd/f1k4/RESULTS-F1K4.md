# F1-K4 results: CuteAFD prefill W8A8 -> W8A16 on K4 (2026-10-28)

Design declared in `FOLLOWUPS-K4.md` before any request. Top-20 measures as in Block Q (not comparable in level with
K3.25's full-vocabulary F1). C-r1 = CuteAFD as shipped (Block Q); C-f1c = same plus `GLM5_FLASH_FP8_PREFILL=off`.
Intervals: window-cluster bootstrap, 5,000 replicates (`score/f1c-minus-c1.json` for the direct C-f1c − C-r1 pairs).

| Measure | C-r1 − vLLM mean | C-f1c − vLLM mean | C-f1c − C-r1 (direct) |
|---|---|---|---|
| P-A teacher KL | +0.0027 [+0.0012, +0.0047] | +0.0009 [−0.0014, +0.0028] not resolved | −0.0018 [−0.0050, +0.0005] |
| P-A top-1 | −0.55 pts | −0.34 pts [−0.57, −0.07] | +0.21 pts, not resolved |
| P-B generated, all | +0.0053 [+0.0033, +0.0076] | +0.0050 [+0.0034, +0.0067] | −0.0004 [−0.0018, +0.0010] |
| P-B 0-2K | +0.0018, not resolved | +0.0034 [+0.0006, +0.0060] | +0.0015, not resolved; top-1 −0.57 pts [−1.05, −0.05] |
| P-B 8-16K | +0.0090 [+0.0062, +0.0122] | +0.0072 [+0.0048, +0.0096] | **−0.0019 [−0.0039, −0.0002]** |
| P-B block B (long code) | +0.0098 | +0.0080 | −0.0018 [−0.0041, +0.0004] |
| Q2 NLL (6 documents) | +0.0076, not resolved | +0.0086, not resolved | — |

Speed (Block T drift subset, serving launches base / W8A16 / base, 64 requests each, no errors). Per cell and
content (decode rates of code and prose differ by ~40%, so they are not pooled):

| Cell | Decode tok/s, W8A16 ÷ base (code / prose) | TTFT, W8A16 ÷ base | base-to-base decode (code / prose) |
|---|---|---|---|
| 1K x 1 | 1.08 / 1.02 | 1.03-1.04 | 1.02 / 1.02 |
| 1K x 4 | 1.02 / 0.97 | 1.03-1.04 | 1.01 / 1.02 |
| 32K x 1 | 1.04 / 1.03 | 1.04 | 1.01 / 1.01 |
| 32K x 4 | 0.98 / 1.02 | 1.04 | 0.94 / 1.02 |

Reading (rule declared in FOLLOWUPS-K4.md):
- **W8A16 prefill does not account for most of the K4 long-code difference.** It moves P-B 8-16K by −0.0019, about
  21% of CuteAFD's +0.0090 difference from vLLM (rule: more than half). On K3.25 the same switch moved it by about 59%.
- **On the teacher panel (P-A) it moves KL by −0.0018 (not resolved directly)**, and CuteAFD with W8A16 is no longer
  resolved from vLLM there (+0.0009).
- **Cost:** time to first token +3-4% in every cell (base-to-base 0.2%); decode speed level (W8A16 ÷ base 0.97-1.08
  per cell, base-to-base 0.94-1.02). Corrected 2026-10-28: an earlier draft pooled code and prose, whose decode rates
  differ by ~40%, and read 1.06-1.07x faster.
- What remains on K4 is consistent with sources other than prefill activations. Candidates (not tested): CuteAFD's
  load-time FP8 conversion of K4's BF16 projections (default pow2 scales; `FP8_SCALES=amax` approximates the official
  codes), the FP8 head and KDA projections (the K3.25 F1a/F1b switches). Tested afterwards in follow-ups F1-K4b, K4c and
  K4d (`RESULTS-F1K4b.md`): W8A16 together with the amax scale rule moves about two thirds.

Files: `score/{pa20,pb20,q2-top20}.json`, `score/f1c-minus-c1.json`, `q/C-f1c/`, `t/C-{base1,f1c,base2}.json`.
