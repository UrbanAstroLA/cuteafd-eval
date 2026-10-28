# F1-K4b results: CuteAFD FP8 switches on K4 (2026-10-28)

Design `FOLLOWUPS-K4b.md` (declared before any request; amendments B1, B2 before the affected requests). Top-20
measures, same rows as Block Q; vs the mean of two vLLM launches and directly vs C-r1 (CuteAFD as shipped);
window-cluster bootstrap 95%. `score-b/f1b-summary.json`.

**Control (B1/B2 gate):** nospec = as-shipped scoring launch with the DFlash2 drafter removed: raw-logit row hashes
identical to C-r1 on **157,671 of 157,671** scored rows (P-A, P-B, Q2). Removing the drafter does not change scoring,
so the drafter-off scoring launches of head16, kda16 and all16 measure only their own switch.

| Arm | Change | P-A KL20 − vLLM | P-B 8-16K − vLLM | P-B 8-16K − as shipped | Serving fits 2x RTX + K4? |
|---|---|---|---|---|---|
| as shipped (C-r1) | — | +0.0027 [+0.0012, +0.0046] | +0.0090 [+0.0062, +0.0121] | — | yes |
| W8A16 prefill (F1-K4) | FP8_PREFILL off | +0.0009, not resolved | +0.0072 | −0.0019 [−0.0039, −0.0002] | yes (TTFT +3-4%) |
| amax | FP8 scale rule amax | +0.0025 [+0.0003, +0.0050] | +0.0068 [+0.0046, +0.0090] | −0.0023 [−0.0054, +0.0008] | yes (scales only) |
| best | FP8 scale rule best | +0.0009, not resolved | +0.0080 [+0.0066, +0.0096] | −0.0010, not resolved | yes (scales only) |
| head16 | BF16 output head | +0.0025 [+0.0010, +0.0045] | +0.0087 [+0.0059, +0.0119] | −0.0003 [−0.0004, −0.0002] | **no** (live: 9,472 tokens short) |
| kda16 | BF16 KDA projections | +0.0028 [+0.0015, +0.0045] | +0.0055 [+0.0026, +0.0084] | **−0.0035 [−0.0065, −0.0007]** | **no** (pool 194,560 short) |
| all16 | best + BF16 KDA + BF16 head + W8A16 | +0.0012, not resolved | +0.0041 [+0.0027, +0.0054] | **−0.0050 [−0.0078, −0.0021]** | **no** |

Reading (rule declared: "accounts for most" = moves 8-16K by more than half of 0.0090, interval excluding 0):
- **No single switch accounts for most of the 8-16K difference.** The largest is BF16 KDA projections (−0.0035, about
  39%), then the scale rule amax (−0.0023, not resolved) and W8A16 prefill (−0.0019, about 21%). The BF16 head moves it
  by −0.0003 (resolved, small).
- **All switches together (all16) account for most of it:** −0.0050 (about 56%). CuteAFD is still +0.0041 [+0.0027,
  +0.0054] from vLLM at 8-16K with every switch off; what remains sits in parts with no BF16 option (MLA, shared and
  dense projections converted to FP8 at load). Candidate, not tested.
- **On the teacher panel (P-A)** the scale rule `best` and all16 leave no resolved difference from vLLM (+0.0009,
  +0.0012).
- **On 2x RTX with K4, only the switches that cost no memory can serve:** W8A16 prefill and the scale rules. BF16 KDA
  and BF16 head do not fit a serving launch here (they would need more GPU memory, e.g. CuteAFD's Spark layouts).
- Speed: not measured for head16/kda16/all16 (serving does not fit); amax/best change stored values only.
- Untested combination that fits: W8A16 prefill + a scale rule (amax or best).

Files: `q/C-{amax,best,head16,kda16,all16,nospec}/`, `score-b/`, `t/HEAD16-SERVING-DOES-NOT-FIT`, configs
`glm53-flash-exl3-k4-2rtx{,-score}-<arm>.config`.

## K4c: W8A16 prefill + amax scale rule (the combination that fits; 2026-10-28)

Declared in `FOLLOWUPS-K4b.md` section K4c before any request. `score-c/f1c2-summary.json`.

| Arm | P-A KL20 − vLLM | P-B generated − vLLM | P-B 8-16K − vLLM | P-B 8-16K − as shipped | Q2 NLL − vLLM (6 documents) |
|---|---|---|---|---|---|
| as shipped | +0.0027 [+0.0012, +0.0046] | +0.0053 | +0.0090 [+0.0062, +0.0121] | — | +0.0076 [−0.0076, +0.0228] |
| W8A16 alone | +0.0009, not resolved | +0.0050 | +0.0072 | −0.0019 [−0.0038, −0.0002] | +0.0086, not resolved |
| amax alone | +0.0025 [+0.0002, +0.0049] | +0.0049 | +0.0068 | −0.0023, not resolved | +0.0108, not resolved |
| **W8A16 + amax** | **+0.0006, not resolved** | **+0.0025 [+0.0012, +0.0038]** | **+0.0030 [+0.0011, +0.0049]** | **−0.0061 [−0.0095, −0.0029]** | **+0.0002 [−0.0009, +0.0012]** |

Speed (serving launches base, w16amax, base; 64 requests each, no errors): decode W8A16+amax ÷ base 0.95-1.09 per cell
and content (base-to-base 0.92-1.02: level); time to first token +4.1-4.3% in every cell.

Reading:
- **W8A16 + amax accounts for most of the 8-16K difference** (−0.0061, about 68%, interval excluding 0), more than all
  switches together (all16: −0.0050) and more than the two single switches added (−0.0019 and −0.0023). CuteAFD remains
  +0.0030 [+0.0011, +0.0049] from vLLM there.
- On the teacher panel and on long-context NLL it leaves no resolved difference from vLLM; the Q2 interval is also much
  narrower than for any other CuteAFD arm (±0.001 against ±0.015-0.03). Not explained here.
- It serves on 2x RTX with K4 (both switches cost no memory), at about 4% longer time to first token and level decode.
