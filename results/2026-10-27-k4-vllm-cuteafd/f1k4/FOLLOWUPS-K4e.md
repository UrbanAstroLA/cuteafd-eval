# K4e: the deployable CuteAFD setting under the full serving tests (declared 2026-10-28, before any K4e request)

Follow-up outside the frozen K4 protocol (FROZEN.json generation 1 unchanged). Requested 2026-10-28: measure the most precise CuteAFD setting that serves on 2x RTX with K4, **W8A16 prefill + amax scale
rule** (`local/glm53-flash-exl3-k4-2rtx-w16amax.config`), with the protocol's full Block T and Block L, so it is
measured as a deployment and not only on fixed text.

**Runs (one CuteAFD launch at a time):**
1. As-shipped serving launch: Block T drift subset (64 requests) → `t/C-e-base1` (state check against Stage 3's C-d1).
2. W8A16 + amax serving launch: Block T full (272 requests, frozen grid, seeds and prompts identical to Stage 3's C-r1)
   → `t/C-w16amax-r1`; then Block L L1, L2, L3, L3s at 2 concurrent (L3 cap 130,048; seeds identical to Stage 4's
   C-r1) → `l/C-w16amax-r1-*`, with Stage 4's gates (exit 0, no new server-log errors, host memory floor).
3. As-shipped serving launch: Block T drift subset → `t/C-e-base2`.
**Comparisons.** Block T: W8A16+amax ÷ CuteAFD as shipped (Stage 3 C-r1) and ÷ vLLM (Stage 3 V-r1) per cell and content;
the band is max(8%, the base1-base2 and C-d1 drift deviations). If base1/base2 differ from Stage 3's C-d1 by more than
the band, Block T ratios against Stage 3 are reported as "machine state changed" and only the within-session drift
comparison is read. Block L: the frozen analyzer and the U5 loop rules on V-r1, C-r1 and C-w16amax-r1 (descriptive,
small n), reported per stage and content: finished on its own, cap hits, loops, content checks, reply length, decode.
**Guardrail.** ~5.5-6 GPU-hours expected; stop at 8.
