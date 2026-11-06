# Does the core's effect build up with position? (exploratory, zero GPU, 2026-11-05)

Question: does the difference between arms, or the stop-decision difference, grow with position along the trace? The
vLLM G2 screen had flagged mla_q_b and mla_o on lp_close; attention projections act on every later token.

Data (existing, no new requests): vLLM G2 dumps (<tl-run>/dumps/runs, 12 arms, launch noise
present) and CuteAFD core-swap step 2 dumps (<cs-run>/s2/runs, bit-identical launches).
93 traces (GPQA reasoning, vLLM-generated), top-64 rows, row r predicts token r+1; position = r + 1.

Written before computing:
- M1 divergence vs position: per row top-64 KL(ref || arm) (score_stop.py convention). Per trace, OLS slope of KL on
  log2(position); mean over traces, 95% bootstrap clustered by question. Also pooled KL by position bin.
  vLLM: each group arm vs k6; noise reference k6r2 vs k6; differences (group - k6r2) of slopes.
  CuteAFD: core (C-K6x vs C-K6) and experts (C-K4 vs C-K6x); launch C-K6r2 vs C-K6 (expected 0).
- M2 stop decision vs length: per finished trace, delta lp_close (BF16 side - 6-bit side) regressed on log2(close
  position); slope with clustered bootstrap. Same arms. Also delta of mean log p(</think>) over the last 512 rows.
- Attention groups under the idea: mla_q_b, mla_o (named), kda_o (o_proj in KDA layers); other attention: kda_qkv,
  mla_a; controls: shared_gu, shared_down, dense, lm_head.
- "Could be interpreted as positive" (triggers the GPU arm): for mla_q_b, mla_o or kda_o, an M1 or M2 slope whose
  interval excludes 0 in the predicted direction (divergence growing with position; BF16 side more ready to stop on
  longer traces), or the three agreeing in direction and exceeding k6r2 and the controls; on CuteAFD, the core's M1 or
  M2 slope excluding 0 in the predicted direction or exceeding the experts'. Many measures: a hit is a lead, not a result.

## Zero-GPU result (POSITION.json, read 2026-11-05 19:20)
- M1: divergence does not grow with position for any group, on either engine. Every swap arm's KL to the 6-bit core is
  highest in the first 1K rows, flat from 1K to 64K, lower beyond 64K; attention groups look like the controls (shared
  experts, dense). k6r2 (launch noise) and lm_head are flat.
- M2 lp_close slope: no group positive (mla_q_b -0.003, mla_o -0.007, CIs include 0).
- CuteAFD lead (meets the trigger above): mean log p(</think>) over the last 512 rows before the close, BF16-core side
  minus 6-bit, +0.057 [+0.011, +0.104], slope +0.033 per doubling of position [+0.020, +0.046]; experts slope -0.038
  [-0.056, -0.015] (opposite). Core M1 slope minus experts +0.019 [+0.002, +0.047] (the core's divergence falls less
  with position than the experts'). Against it: this log-space window measure was not in the frozen protocol; it weights
  rows where p(</think>) is ~1e-6, so it is sensitive to the head's tail; on vLLM the whole-core swap goes the other way
  (-0.116 [-0.148, -0.092]) and lm_head alone -0.069.

## GPU arm (run on a positive reading), written before the launch
CuteAFD v4 refuses a layer whose attention group mixes native and BF16 projections ("incomplete native GLM Flash
operator group", rust/crates/cuteafd-loader/src/families/glm5_flash/core.rs), so q_b + o_proj alone cannot be served.
Arm C-K6a: all 180 attention matrices BF16 (FP8 at load), the rest of the core and the head 6-bit (prep/build_attn.py).
Contains the q_b + o_proj set. Scored on the 93 traces; C-K6 rechecked on the 10 longest traces against the
stored dumps (bit-identical on 10/10 = the stored C-K6 and C-K6x dumps serve as the other arms; otherwise not comparable).
Readings: attention = C-K6a - C-K6, rest = C-K6x - C-K6a (rest includes the head). A position effect through attention predicts the lead sits in attention: last-512 log p slope > 0 with interval excluding 0, larger than rest's; also reported: lp_close, hazard, KL
by position, M1 slopes. Exploratory; one arm; reported whichever way it falls.

## GPU arm outcome (2026-11-05 19:39)
C-K6a was refused at load, before any request: "native Flash requires complete attention and FFN operator groups"
(rust/crates/cuteafd-daemon/src/families/glm5_flash/weights.rs:777; logs/start-s2-C-K6a.log). The native path needs
every layer's attention and FFN groups native together, so CuteAFD v4 serves the core either all 6-bit or all BF16/FP8;
no partial core (attention only, or q_b + o_proj) is loadable. The C-K6 recheck (10 traces) ran as chained.

## vLLM arm (test where observed), written before the launch, 2026-11-05
The q_b/o_proj flags come from the vLLM fork's G2 screen (single groups, one launch each, launch noise
+0.006). Arm qbo: SWAP_SET=mla_q_b,mla_o,kda_o (56 matrices: q_b in the 11 MLA layers, o_proj in all 45; native BF16), the thinking-length run's swap launch unchanged (chain-qbo.sh). Launches
interleaved k6-a, qbo-a, k6-b, qbo-b; reduced captures of the 93 fixed traces (tr, on).
Primary (analyze_qbo.py): lp_close, qbo minus k6 (launch means), per finished trace (77), bootstrap clustered by question
(11) and over traces. Supported if: the question-clustered interval excludes 0 on the positive side (BF16 side more ready
to stop), |delta| exceeds the larger within-arm launch difference, and all four cross-launch pairings are positive.
Expectation if the single-group flags were additive: about +0.03 to +0.04 (mla_q_b +0.014, mla_o +0.017, kda_o +0.009);
if they were noise: about 0. Secondary, descriptive: hazard, last-512 mean log p(</think>), the pairings against the G2
k6 and k6r2 launches, position slopes and KL by position. Scope: GPQA traces (where the flags came from); says nothing
about thinking length on code.
