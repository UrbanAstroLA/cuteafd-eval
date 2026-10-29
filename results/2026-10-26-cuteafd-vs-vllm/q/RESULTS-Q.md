# Block Q results: precision, CuteAFD v3.0.1 vs vLLM v0.9.2 (2026-10-26)

Frozen protocol: `PROTOCOL-DRAFT.md` (v2 + amendments A1-A2), hashes in `FROZEN.json`.
Arms: V1 = vLLM v0.9.2 (`ea0430aa`) on K3.25-v1, served settings (DFlash2 on); C1 = CuteAFD v3.0.1
(`392db7c0`) on Core-FP8; C0 = CuteAFD on K3.25-v1 (control). Expert bytes identical in all arms.
Teacher-forced, raw token ids, prefill-shaped. Intervals: 95% bootstrap over windows (P-A, P-B) or documents (Q2).
Measurement under the frozen protocol (CuteAFD's Block Q captures ran shortly before the freeze, as amendment A1 declares), on two panels; not a general quality ranking.

## Paired against the vLLM runs, with the adversarial review (2026-10-27; `AUDIT-2026-10-27.md`)

1. **vLLM run-to-run variation: cause.** It is not batching or speculation: every vLLM capture ran alone.
   Rows inside the first 2,045-token prefill chunk are bit-identical between the two vLLM runs; rows beyond it almost
   never are (verified: e00 512/512 and d01 419/419 identical inside; a08 and b00 0/512 beyond). Multi-chunk prefill is
   not run-to-run deterministic on this stack (consistent with the earlier indexer top-k ordering finding).
2. **The headline pairs CuteAFD against the mean of both vLLM runs**, since one vLLM run is one draw of a varying
   engine. P-B generated rows at 8-16K: KL **+0.0050 [+0.0031, +0.0071]**, top-1 **−0.87 pts** (against V1 alone
   +0.0044 / −1.04; against V1r +0.0057 / −0.70). The 2-8K top-1 difference (+0.39 against V1) does not hold against V1r.
3. **Length and content.** The 8-16K bucket is block B (long code reading: all 12 windows, 82% of the
   bucket's rows). Within block A, the only block present at every length, the KL difference is flat
   (+0.0029 / +0.0017 / +0.0028). The difference is concentrated in long code reading; whether length or content
   drives it is not separated here. NLL is also higher for CuteAFD below 8K (+0.0069, +0.0073).
4. **Against the panel's own paired bar (0.005)**: CuteAFD's top-1 loss upper bound is 0.0080 (vs V1) / 0.0067
   (vs V1r), so it is not shown within that bar on top-1 (the bar is defined for same-engine changes; applied here by
   analogy only).
5. **Mechanism candidates.** Besides FP8 projections / head / KDA, the engines differ in the DSA indexer key format
   (CuteAFD BF16 keys, vLLM FP8), attention placement, KDA output sharding, prefill chunk geometry, BF16 logits in vLLM,
   and W8A8 prefill (specific to prefill-shaped scoring). Follow-up F1 tests the switchable ones; its KDA arm also
   drops KDA output sharding (launcher coupling), so it is not a clean single-factor test. CuteAFD's predictive entropy
   is higher in 18 of 18 8-16K windows (0.580 vs 0.523; teacher ~0.53), which is why its NLL difference is larger than
   its KL difference on this greedy-generated text.
6. **Q2 wording.** Six documents; the per-type intervals rest on 3 clusters each. With t-intervals, prose
   [−0.0013, +0.0050], code [−0.0135, +0.0077]; one code window (c2-064k) drives the code figure. Stated as: no NLL
   difference larger than about ±0.005 nat at 32K-128K at this sample size. Engine-vs-engine disagreement is about
   1.8x vLLM's own run-to-run disagreement on matched documents.
7. **Trailing context rows.** All 30 such spans are the same unrelated filler
   file; engine-vs-engine KL there is 0.7-3.1 nat and vLLM-vs-itself up to 1.96 nat. These rows are highly sensitive to
   any numerical change; they are not evidence about the reference.
8. **Panel text source** (noted): P-B's generated text is greedy output of the official FP8 model in his engine's
   arithmetic family; any resulting bias would favour CuteAFD, i.e. it runs against the observed difference.

## Headline against the first vLLM run (V1)

| Panel | Context | vLLM V1 | CuteAFD C1 | C1 − V1, paired | Within-engine floor |
|---|---|---|---|---|---|
| P-A full-vocab KL (25 x 2K) | 2K | 0.0458 | 0.0476 | **+0.0017 [+0.0006, +0.0028]** | V1 +0.000001; C1 0 |
| P-A NLL (teacher 1.0627) | 2K | 1.0731 | 1.0730 | ≈ 0 | |
| P-B coarse KL, generated rows | 0.5-14.4K | 0.0457 | 0.0484 | **+0.0027 [+0.0007, +0.0046]** | V1 −0.0006 [−0.0021, +0.0008]; C1 0 |
| P-B NLL, generated rows (teacher 0.1947) | 0.5-14.4K | 0.2317 | 0.2485 | **+0.0168 [+0.0121, +0.0211]** | V1 +0.0002 |
| P-B top-1, generated rows | 0.5-14.4K | 93.84% | 93.33% | **−0.51 pts [−0.85, −0.16]** | V1 −0.09 |
| Q2 NLL, human text (no teacher) | 32K-128K | 1.2329 | 1.2324 | −0.0005 [−0.0037, +0.0018] | |

Both engines pass tpurtell's calibrated bar for this set (generated rows, prefill: KL ≤ 0.05, top-1 ≥ 93%,
confident top-1 ≥ 96%, top-3 ≥ 97%); CuteAFD narrowly (0.0484 / 93.33% / 96.31% / 99.48%).
For scale: his published baseline for the official FP8 model on the same set is KL 0.0216 / top-1 95.77%, so
the 3.25-bit experts account for most of either engine's distance from BF16.

## By context bucket (P-B, generated rows, C1 − V1)

| Bucket | Rows | KL | NLL | Top-1 |
|---|---|---|---|---|
| 0-2K | 4,035 | +0.0012 [−0.0011, +0.0036] | +0.0069 [+0.0031, +0.0110] | −0.32 pts [−0.83, +0.11] |
| 2-8K | 3,547 | +0.0010 [−0.0038, +0.0047] | +0.0073 [+0.0015, +0.0128] | +0.39 pts [+0.03, +0.76] |
| 8-16K | 7,522 | **+0.0044 [+0.0017, +0.0069]** | **+0.0266 [+0.0214, +0.0308]** | **−1.04 pts [−1.47, −0.57]** |

By block, the 8-16K gap is block B (long code reading: KL +0.0047, NLL +0.029, top-1 −1.1 pts).
Below 8K the engines are within about 0.001 nat KL of each other.
Beyond 14K there is no teacher. On human-written text at 32K-128K (Q2) the engines' NLL differs by
no more than about ±0.005 nat at this sample size (C1 − V1 overall −0.0005 [−0.0037, +0.0018], 6 documents;
per type, with 3 documents each, the intervals are not resolved). Their distributions disagree by KL 0.014
(JS 0.0028, argmax agreement 96.2%), about 1.8x vLLM's own run-to-run disagreement on matched documents.
This does not say which is closer to BF16 there.

## Controls and checks

- C0 vs C1 (projection source inside CuteAFD): KL −0.0003 [−0.0019, +0.0014], top-1 −0.14 pts
  [−0.54, +0.25]. Indistinguishable; the official-FP8 vs load-quantized projections do not matter.
- Determinism: every CuteAFD repeat byte-identical (P-A, P-B, Q2). vLLM repeats differ (P-B KL ±0.0006 overall,
  larger at 8-16K; Q2 floor KL 0.0047) because multi-chunk prefill is not run-to-run deterministic (item 1).
- Scorer: our port of tpurtell's P-B rule reproduces his CLI with 0 difference on all 32,768 positions.
  P-A scorer reproduces the 2026-10-08 v0.8.0 result exactly.
- vLLM capture: dumped rows match vLLM's own API log-probabilities to < 6e-6 per checked row;
  captured with speculation on (works), prefix cache as served.
- Mechanism candidates: item 5 above. Follow-up F1 (`f1/RESULTS-F1.md`) switches the ones CuteAFD exposes.

## Panel caveat: trailing context rows

P-B's context rows (17,664; primary metrics exclude them) show KL ~1.7 nat on **both** engines
(V1 1.69, C1 1.73), concentrated in tool-call windows, and both engines' NLL there (3.61-3.77) is
lower than the reference's own (3.87). These rows are highly sensitive to any numerical change (item 7).

## Not covered

Decode-shaped scoring; scoring under concurrent load (CuteAFD's scoring path runs exclusive);
teacher-anchored precision beyond 14.4K; task quality.

## Files

`q/score/final/{pa,pb,q2}/`, captures under `q/rows/`, `q/dumps/`, `vllm-v092-dumps/runs/`,
logs under `q/cli/`, thinking check `q/thinking-check-vllm.json`.
