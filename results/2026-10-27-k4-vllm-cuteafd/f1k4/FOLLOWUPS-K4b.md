# F1-K4b: CuteAFD FP8 switches on K4 (declared 2026-10-28, before any F1-K4b request)

Follow-up outside the frozen K4 protocol (FROZEN.json generation 1 unchanged), extending F1-K4 (W8A16 prefill,
`RESULTS-F1K4.md`). Operator request 2026-10-28: try CuteAFD's other FP8 switches on K4 for more behaviour data.

**Question.** Which of CuteAFD's FP8 choices on K4 carry its precision difference from vLLM (Block Q: P-A +0.0027,
P-B 8-16K +0.0090, top-20), and at what speed cost? F1-K4 found W8A16 prefill moves P-B 8-16K by only −0.0019.

**Arms** (each = the K4 CuteAFD scoring/serving config plus only the listed change; configs
`glm53-flash-exl3-k4-2rtx{,-score}-<arm>.config`):
| Arm | Change | What it changes |
|---|---|---|
| amax | `FP8_SCALES=amax` | scale rule of the FP8 copies made from K4's BF16 projections at load (default pow2) |
| best | `FP8_SCALES=best` | the launcher's third scale rule |
| kda16 | `GLM5_FLASH_KDA_FP8=off` | KDA projections stay BF16 (default row128 FP8) |
| head16 | `GLM5_FLASH_FP8_HEAD=off` | output head stays BF16 (default FP8) |
| all16 | best + kda16 + head16 + `GLM5_FLASH_FP8_PREFILL=off` | every available switch; MLA, shared and dense projections stay FP8 (no BF16 option) |

**Memory rule (declared now).** Each config is planner-dry-run first. If an arm's launch does not fit at
MAX_CONTEXT_TOKENS=262,144, it is retried once with MAX_CONTEXT_TOKENS=139,264 (≥ the longest panel request 131,073
and the speed subset's 33,792); this changes only the KV pool size, not arithmetic, and is recorded per arm. An arm that
still does not fit is reported as "does not fit on 2x RTX with K4".

**Precision.** One scoring launch per arm: P-A, P-B, Q2 with the frozen top-20 probe driver (bit-deterministic, one
pass), scored with the frozen scorers against the same rows as Block Q: each arm vs the vLLM mean (V-r1, V-r2) and
directly vs C-r1 (as shipped), window-cluster bootstrap.

**Speed.** Block T drift subset (64 requests, frozen seeds) on serving launches for the arms that change kernels or
formats (kda16, head16, all16), bracketed by two as-shipped base launches (base, kda16, head16, all16, base); amax/best
change only stored scale values, so their speed is not measured. Reported per cell and content (not pooled): arm ÷ mean(base),
with base-to-base as the band.

**Reading rule.** An arm "accounts for most" of the 8-16K difference if C-arm − C-r1 moves P-B 8-16K KL by more than
half of C-r1 − Vmean (0.0045) with an interval excluding 0. Every arm is reported, including null results.
**Guardrail.** ~2.5-3 GPU-hours expected; stop at 4. vLLM K3.25 serving restored at the end on every exit path.

**Pre-run note (2026-10-28, planner dry runs, before any F1-K4b request).** All five scoring configs fit
(pools: amax/best 1,419,264; kda16 881,152; head16 1,220,096; all16 681,984 tokens). Serving: head16 fits (406,528);
kda16 and all16 do not fit at 262,144 (pool 194,560 short) nor, per the memory rule, at 139,264 (150,016 short):
**serving with BF16 KDA projections does not fit on 2x RTX with K4**. Their precision is still measured (scoring
launches); their speed is not. Speed order becomes base, head16, base.

**Run note (2026-10-28 12:47).** amax and best captured. The kda16 scoring launch did not fit live at 262,144 ("41 of 42
fit"; the planner does not see the desktop's 2.6 GB on GPU 1). Per the memory rule, the kda16 and all16 scoring configs
were set to MAX_CONTEXT_TOKENS=139,264 and the run resumed from kda16 (ARMS="kda16 head16 all16").

**Amendment B1 (2026-10-28 13:05, before any further request).** The 139,264-token retry did not fit either: CuteAFD's
GLM Flash pool keeps a 262,144-token floor, and with BF16 KDA GPU 0 has room for 1,536 tokens. The DFlash2 drafter
(~2 GB on GPU 0) is not used by scoring probes (probe.rs: scoring probes are always no-speculation). So:
1. **Control arm nospec** = the as-shipped K4 scoring config + `SPECULATOR=off` only. Pass criterion: its raw-logit
   row hashes equal C-r1's on every scored row of P-A, P-B and Q2 (CuteAFD is bit-deterministic). If they do not, the
   drafter is not neutral for scoring and kda16/all16 are reported as "does not fit".
2. **kda16 and all16** scoring configs: MAX_CONTEXT_TOKENS back to 262,144, plus `SPECULATOR=off`; reported with the
   control's result. Order: head16, nospec, kda16, all16, then the speed check (base, head16, base).

**Amendment B2 (2026-10-28 13:10, before any further request).** The head16 scoring launch did not fit live either
(KV pool 252,672 tokens, 9,472 short of the 262,144 floor, GPU 0 limiting). B1 is extended to head16's scoring config
(`SPECULATOR=off`), gated by the same nospec control, which now runs first: nospec, head16, kda16, all16. The speed
check is no longer fatal to the run: if the head16 serving launch does not fit live, that is recorded as "does not fit
for serving on 2x RTX with K4" and scoring proceeds.

## K4c: the combination that fits (declared 2026-10-28, before any K4c request)

Operator request: test the most precise CuteAFD setting that can serve on 2x RTX with K4. **Arm w16amax** =
as-shipped config + `GLM5_FLASH_FP8_PREFILL=off` + `FP8_SCALES=amax` (configs
`glm53-flash-exl3-k4-2rtx{,-score}-w16amax.config`; drafter kept: both switches cost no memory, and F1c's
scoring launch fit with it). Precision: one scoring launch, P-A/P-B/Q2, scored as above. Speed: serving launches
base, w16amax, base (drift subset, per cell and content, base-to-base band). Reading: report the 8-16K change vs as
shipped and the remaining difference from vLLM; "accounts for most" rule as above. Expected ~1 GPU-hour.

## K4d: W8A16 prefill + best scale rule (declared 2026-10-28, before any K4d request)

Operator request after K4c. **Arm w16best** = as-shipped config + `GLM5_FLASH_FP8_PREFILL=off` + `FP8_SCALES=best`
(configs `glm53-flash-exl3-k4-2rtx{,-score}-w16best.config`; drafter kept). Same precision and speed method as K4c
(serving launches base, w16best, base). Reported beside K4c; same reading rule. Expected ~1 GPU-hour.
