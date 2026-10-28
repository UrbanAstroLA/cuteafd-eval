# F1-K4: CuteAFD prefill W8A8 -> W8A16 on K4 (declared 2026-10-27, before any F1-K4 request)

Follow-up outside the frozen K4 protocol (FROZEN.json generation 1 is unchanged), as F1 was on K3.25
(`<run>/FOLLOWUPS.md`, `f1/RESULTS-F1.md`). Requested 2026-10-27: repeat the
W8A8 -> W8A16 prefill change on K4.

**Question.** On K4, how much of CuteAFD's precision difference from vLLM (Block Q: P-A +0.0027, P-B +0.0054,
8-16K +0.0090, top-20) comes from W8A8 prefill GEMMs, and at what speed cost?

**Arm.** C-f1c = the K4 CuteAFD scoring config plus `GLM5_FLASH_FP8_PREFILL=off` (only change; configs
`local/glm53-flash-exl3-k4-2rtx-score-f1c.config` and serving `local/glm53-flash-exl3-k4-2rtx-f1c.config`).
Weights stay FP8 (CuteAFD's load-time conversion); prefill activations stay BF16 instead of FP8.

**Precision.** One scoring launch: P-A, P-B, Q2 with the frozen top-20 probe driver (CuteAFD is bit-deterministic,
so one pass). Scored with the frozen scorers against the same rows as Block Q: C-f1c vs the vLLM mean (V-r1, V-r2)
and vs C-r1 (as shipped). Same reading rule as Block Q (95% interval excludes 0 and exceeds vLLM's launch-to-launch
difference). c2-064k is reported separately (see analysis/c2/C2-FINDINGS.md).

**Speed.** Block T drift subset (1K and 32K, 1 and 4 streams, code and prose, replicates 0-1; 64 requests, frozen
seeds) on serving launches in the order base, f1c, base (ABA, bracketing drift). Reported: f1c / mean(base) per cell
for decode tok/s and TTFT, with the base-to-base difference as the noise band.

**Reading rule.** "W8A16 accounts for most of the difference" if C-f1c - C-r1 moves P-B 8-16K KL by more than half of
C-r1 - Vmean with an interval excluding 0 (as K3.25 F1c). Speed cost stated only outside the base-to-base band.
**Guardrail.** ~75 GPU-minutes expected; stop at 120.
