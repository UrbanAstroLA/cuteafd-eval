# Loop checks (zero GPU, exploratory, 2026-11-03)

Asked after G4: can existing data reduce the uncertainty about whether the 6-bit core loops more often?
Post hoc and exploratory throughout; nothing here is a frozen reading.

## a. Cap-hit rate on the seven knife-edge questions (186, 12, 81, 120, 86, 74, 13)
Sources: local-inference-evals GPQA records (tools/analyze.py gpqa(); cap hit = completion tokens >= 327,680, since
older runs did not log finish reasons) and this run's G1b and G4. Seven older records (five K3.25, two K4) logged no
token counts; they are left out of the rates and counted separately with an empty answer as a proxy (where tokens were
logged, every cap hit has an empty answer and 42 of 43 empty answers are cap hits). Computed by
`analysis/loop_checks.py` -> `analysis/LOOP-CHECKS.json`.

| Checkpoint (engine) | Requests with token counts | Hit the cap | Share | With the proxy (all records) |
|---|---|---|---|---|
| K3.25 (vLLM fork 0.7.0-0.9.1, several configs) | 35 | 4 | 11.4% | 6 of 70 (8.6%) |
| K4 (vLLM fork 0.8.0-0.9.1) | 28 | 3 | 10.7% | 4 of 42 (9.5%) |
| K4-Core-K6, 6-bit core (v0.9.2-experimental + route b; G1b) | 42 | 4 | 9.5% | — |
| K4-Core-K6, 6-bit core (G4, question 12 only) | 12 | 1 | — | — |
| K4-Core-K6, BF16 core (G4, question 12 only) | 12 | 0 | — | — |

Whole benchmark, records with token counts: K3.25 19 of 990 (1.9%), K4 23 of 792 (2.9%); with the proxy 34 of 1,980
and 35 of 1,188. No checkpoint difference is distinguishable on the knife-edge set (K4 vs K4-Core-K6: Fisher p = 1.0);
engine versions, concurrency and route b differ between rows. Questions 81 and 13 carry most cap hits (K4-Core-K6 in
G1b: 4 of 12).

*Correction (2026-11-03, before publication).* The first version of this table counted the records without token
counts as "not at the cap" (K3.25 4 of 70, 5.7%; K4 3 of 42, 7.1%; whole benchmark 1.0% and 1.9%). The reading is
unchanged.

## b. Early-stop detector (local-inference-evals looping investigation: last 30,000 reasoning characters checked
every 10,000 from 30,000 on; stop after three consecutive zlib ratios below 0.10)
- No finished G1b or G4 reply would have been stopped (61 replies; lowest check 0.221, as in the investigation's 0.212).
- Where it would fire on this run's non-finished replies: G4 k6 rep 3 (question 12) at 110,000 of 1,485,415
  characters; G1b doc 13 rep 5 at 1,190,000 of 1,406,326; doc 81 rep 6 at 730,000 of 802,274; doc 13 rep 6 never
  (classified loop by the 0.15 end-of-reply rule); doc 81 rep 5 is an exhaustion (not a loop).
- So on these questions the loops start late; a stop at the detector would shorten them by about 1.2x.

## c. Chosen-token log-prob on the 16 not-finished traces (G2 dumps, every 64th row + last 512; truncated at 32K,
so mostly before any loop; `analysis/post_hoc.py` -> `analysis/POST-HOC.json`)
- BF16 core - 6-bit core: -0.0015 [-0.0031, -0.00004]; second 6-bit launch - first: -0.0010 [-0.0023, +0.0004].
- Same size as launch-to-launch variation: no sign that the BF16 core makes these continuations less likely.

