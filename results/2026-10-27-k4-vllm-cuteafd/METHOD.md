# K4 on tpurtell's vLLM fork v0.9.2 and CuteAFD v3.0.1: method

This file restates the frozen protocol of the K4 measurement for the two arms reported here, V (vLLM fork) and C
(CuteAFD). The protocol text itself is not in this repository; its freeze record is summarised below.

## Frozen before the first comparison request

- **Frozen at 2026-10-27T17:58:09-07:00**, after the startup and smoke stage and before any Block Q, T or L request.
- Freeze record `FROZEN.json`, sha256 `368e17007486ba0bf160077b4621bf54b7a262f1c18e882616ce1e3caa0dfa86`
  (generation 1, no amendments). It holds the sha256 of 70 files: the protocol, the grid, the cost estimate, the
  stage runner, the drivers, scorers and analysis, their self-tests, the reused K3.25 drivers, prompt manifest,
  indexes, checkers, plans and scorers, the top-20 scoring definitions, the stacks' launch files, the vLLM recipe
  `env.sh`, the CuteAFD configs, and the startup logs the grid was read from.
- Every comparison driver refuses to send a request unless its own hash and the grid's match the freeze record.
- Follow-up F1-K4 (`../f1k4/`) was declared after the Block Q results were known. It is outside the frozen protocol
  and labelled as such.

## Arms

| | V: vLLM fork | C: CuteAFD |
|---|---|---|
| Engine | tpurtell/glm-5.3-flash-ext3-2x-rtx v0.9.2, image `sha256:ea0430aa…` (as in the K3.25 run) | tpurtell/cuteafd v3.0.1, image `ghcr.io/tpurtell/cuteafd-coordinator:v3.0.1@sha256:392db7c0…` |
| Checkpoint | `brandonmusic/GLM-5.3-Flash-tr3-4bpw` @ `a5fee929cf4888b1824323e33e8a19b60129e025` ("K4") | the same bytes |
| Drafter | `incoai/GLM-5.3-Flash-DFlash2` @ `bf582e4e`, 3 draft tokens fixed | the same checkpoint, adaptive depth, FP8 drafter |
| Launch | the v0.9.0 repository's launcher with `MODEL_PROFILE=k4`, `GPU_MEMORY_UTILIZATION=0.95` and the image pin (`repro/k4/vllm/env.sh`); the same JIT-cache overlay as the K3.25 run | the unmodified launcher with `repro/k4/cuteafd/glm53-flash-exl3-k4-2rtx.config`; Block Q uses the scoring launch `glm53-flash-exl3-k4-2rtx-score.config` |

The expert bytes are the same on both arms. The tokenizer is byte-identical to K3.25-v1's (`19e77364…`). For
single-turn prompts, K4's chat template (`41cff9af…`) and the template the vLLM image uses (`0c4099f3…`) render
byte-identical text; they differ only on multi-turn reasoning history, which no prompt here contains. The K3.25
prompt sets therefore carry over unchanged, checked against their 133 manifest hashes before any request.

## Declared differences

Each engine runs as its author ships it, plus the local settings listed. None of these is tuned away.

| | V: vLLM fork v0.9.2 | C: CuteAFD v3.0.1 |
|---|---|---|
| Local settings needed | none beyond the recipe | `MAX_CONTEXT_TOKENS=262144`. At its defaults the planner refuses K4 on two RTX GPUs: its pool (260,608 tokens) is below the default 1,048,576-token context floor. The scoring launch adds `ENABLE_BENCH`, an API key, `FULL_PREFILL_LOGITS=on` and `PREFIX_CACHE_ENTRIES=0`; scoring probes never read the prefix cache (`probe.rs`), so the last frees memory without changing a scored value |
| Attention, dense and shared projections | BF16, as stored | FP8 E4M3, 128×128 blocks, converted from K4's BF16 at load with the default pow2 scales (no BF16 option) |
| KDA projections, head | BF16 | FP8 per row, converted at load |
| Logits that scoring reads | BF16 head output, log-softmax in fp32 | F32 from the FP8 head, log-softmax in f64 |
| KV / latent cache | `fp8_ds_mla` | FP8 latent |
| Speculation | DFlash2, 3 fixed, rejection sampling | DFlash2 adaptive, FP8 drafter; a draft stands only if it equals the target's selection |
| Prefill geometry | 2,048 tokens per step, interleaved with decode | 4,096-row lanes, prefill first |
| Capacity at these settings (startup lines) | KV pool 1,377,179 tokens, 16 sequences | pool 447,488 tokens (the dry run predicted 605,696; the desktop's context on GPU 1 takes the rest), 16 requests; scoring launch 451,584 |
| Prefix cache | `align` mode, whole 4,352-token blocks | 20 entries (serving launch); off in the scoring launch |
| Same seed twice, same prompt | different text in 2 of 3 (smoke; cause not examined) | identical 3 of 3 |
| Literal `<think>` text in a user turn | parsed as special tokens | kept as text (smoke check S2: 33 against 37 prompt tokens on a test prompt; 29 on both without the tags). This lengthens the 128K code prompts on CuteAFD |
| Run-to-run determinism of scored rows | not past the first 2,045-token prefill chunk (as on K3.25) | bit-identical (row hashes) |
| Top-20 route | `/v1/completions` with `prompt_logprobs: 20` | `/v1/bench/probe` with `top_k: 20` (scoring launch) |

## Order

Times UTC−7. Engines ran one after the other on one machine, alone on the GPUs apart from desktop graphics clients.

| Stage | Order | Times |
|---|---|---|
| 1 Startup and smoke | V cold, V warm; C cold, C warm, C scoring launch | 2026-10-27 17:34-17:51 |
| Freeze | | 17:58:09 |
| 2 Block Q | V launch 1 (P-A, P-B, Q2, P-B again) → C scoring launch (every panel twice) → V launch 2 (P-A, P-B, Q2) | 18:03-19:48 |
| 3 Block T | V (full grid, then its drift subset) → C (full grid, then its drift subset) → V drift subset again | 19:54-23:25 |
| F1-K4 follow-up | C scoring launch with W8A16 prefill; speed subset on serving launches base, W8A16, base | 23:31-00:32 |
| 4 Block L | V (L1, L2, L3, L3s) → C | from 2026-10-28 00:38 |

**Two vLLM launches.** vLLM's multi-chunk prefill is not run-to-run deterministic (K3.25 audit, item I1), so the
Block Q headline pairs CuteAFD against the per-row mean of two independent vLLM launches, which bracket the CuteAFD
captures in time. A within-launch P-B repeat on launch 1 (V-r1b) separates within-launch from launch-to-launch spread.
Each engine runs its own drift subset at the end of its Block T session; the final vLLM subset measures drift across
the whole stage.

## Request settings, identical on both engines

| Setting | Value |
|---|---|
| Thinking | `chat_template_kwargs.enable_thinking: true` on every chat request. The templates have no off switch, and the engines implement "off" differently |
| Sampling | `temperature 1.0`, `top_p 0.95`, `top_k -1`, sent explicitly |
| max_tokens | always explicit |
| Seeds | distinct per request, the same per request on both engines, recorded. Block T from 730,000,000, drift from 760,000,000, Block L from 840,000,000 (so no Block L seed equals a Block T seed) |
| Nonce | the first line of every prompt, from the K3.25 nonce groups keyed by (salt, seed); one fixed salt per block, shared by both engines (`K4-3E-2026-10-27:T`, `:T-drift`, `:L`) |
| Inputs | byte-identical messages (chat) or token ids (scoring); prompt tokens checked against the index on every request |
| Unit of analysis | the prompt, window or document, paired across engines; repeats of a prompt use distinct seeds |

A shared seed pairs requests across engines; it does not pair their outputs, because the samplers differ.

## Grid

| Block | Cells |
|---|---|
| T | 1 and 4 streams at 1K, 8K and 32K input; 1 stream at 128K; 1,024 output tokens |
| L | 2 requests in flight; caps L1 8,192, L2 32,768, L3 130,048 tokens; L3s one request at a time at the L3 cap |
| Panels P-A, P-B, Q2 | one request at a time; the longest request is 131,073 tokens |

The frozen protocol also included a third engine, not reported here; its memory limits set the concurrency grid and the long-output cap.

The grid is common to the protocol's arms. Both engines admitted more (startup lines above), so the K3.25 run's 8-
and 16-stream cells and its 131,072-token L3 cap are not repeated on K4.

## Block Q: precision, top-20 measures

**Panels** (reused unchanged from the K3.25 run):

| Panel | Windows | Rows | Reference |
|---|---|---|---|
| P-A | 25 × 2,048 tokens | all 2,047 rows | brandonmusic's BF16 teacher (`zai-org/GLM-5.3-Flash-BF16` @ `a6c167b6`), full vocabulary |
| P-B | 64 windows, 0.5K-14.4K | the last 512 rows; generated rows primary | tpurtell's `glm5_flash-v2` set, top 1,024 plus tail (BF16 root) |
| Q2 | 6 documents × 32K / 64K / 128K | the last 4,096 rows | none (engine against engine) |

**What each engine returns.** vLLM: the target model's own log-probs of the prompt rows (raw logits, no sampling
parameters), top 20 plus the forced token; prompt-logprob requests skip prefix-cache reads; speculative decoding
does not change them. CuteAFD: `/v1/bench/probe` rows with the top 20 (ties to the lower id), the forced token and a
hash of the raw f32 row; requests cold, without drafts, checked for `cached_tokens 0` and `score_path prefill`. Both
are prefill-shaped: the measure covers prompt arithmetic, not decode-shaped rows.

**Metrics.** Names are kept distinct from full-vocabulary KL.

- P-A: **KL20**, KL(teacher ‖ engine) on the engine's 20 ids plus the actual token plus one rest cell, a lower bound;
  **KL20n**, the same on the ids both carry. Exact under top-20: NLL, top-1, confident top-1, top-3.
- P-B: **KL_pb20**, the top-20 truncation of tpurtell's top-1,024-plus-tail rule; exact: top-1, confident top-1,
  top-3, NLL. Groups: generated rows (primary), by bucket, by block (8-16K is block B, long code reading), block A by
  bucket; context rows separately (hypersensitive filler).
- Q2: NLL; engine against engine KL20n both directions and top-1 agreement; floors from repeats.

**Calibration** (zero-GPU check before the freeze, on the K3.25 run's full-vocabulary captures truncated to each
engine's own top 20): on P-A, KL20 read 0.79-0.80 of the full-vocabulary KL on every arm; on P-B generated rows,
KL_pb20 kept 98-99% of the published coarse KL. Every K3.25 difference whose interval excluded 0 kept its sign and its
significance under the truncation. The K4 scorers reproduce those per-row values exactly when fed emulated top-20
rows. Top-20 numbers are never printed in a column with full-vocabulary KL.

**Runs and repeats.**

| Arm | Runs | Purpose |
|---|---|---|
| V | V-r1 (launch 1): P-A, P-B, Q2; V-r1b: P-B again on launch 1; V-r2 (launch 2): P-A, P-B, Q2 | headline reference = per-row mean of V-r1 and V-r2; launch-to-launch and within-launch floors |
| C | C-r1 and C-r1b (one scoring launch), every panel | byte identity (row hashes), floor |

**Intervals.** P-A: window-cluster bootstrap 95%, seed 20260929, 20,000 replicates. P-B: SplitMix64, seed 20260829,
5,000 replicates, as tpurtell publishes. Q2: Student-t over the 6 documents (5 df).

**Reading rule** (declared before any request). "C differs from vLLM" on a measure needs both: the 95% interval of
C − Vmean excludes 0, and |C − Vmean| exceeds the vLLM launch-to-launch difference |V-r2 − V-r1| on the same rows.
Otherwise it reads "within vLLM's own launch-to-launch spread". The primary looks are P-A KL20, P-B generated KL_pb20
and P-B generated top-1. P-B bucket and block results are descriptive; mechanisms are listed as candidates, not
inferred. Q2: the unit is the document, no per-type claim, windows with rows above 1 nat are listed, the K3.25 outlier
window `q2-code-c2-064k` is reported separately and the overall numbers are also given without it, and cross-engine
KL20n is set against the floor on the same documents.

## Block T: throughput

- Inputs: the K3.25 Block T prompt set, unchanged. Prose and code at every length; reasoning and JSON at 1K and 8K.
- 3 replicates per cell, 1,024 output tokens, thinking on; at c streams a replicate is lcm(c, 4)/c barrier-released
  batches, so every prompt appears equally often. One warm-up batch and one cached cell (8K prose prompt 0, a primer
  and 3 repeats). 272 requests per engine (264 measured, 4 warm-up, 4 cached).
- Per request: time to first token, prefill rate at one stream, per-stream decode, usage, finish reason, content and
  reasoning characters. Per replicate: aggregate tokens per second.
- Analysis: per cell the median decode, the decode of "clean" streams (decode windows overlapping other streams'
  prefill by less than 5%), the aggregate, the median time to first token, prompt-token mismatches and cached tokens;
  ratios to vLLM with the range over replicates.
- **Reading rule.** The noise band per cell is max(8%, the largest drift deviation of either engine); both engines'
  drift stayed inside 8%, so the band is 8%. Inside it a ratio is "level"; outside, "faster" or "slower", stated no
  more precisely than the band. The 128K code cells hold literal `<think>` / `</think>` text and are reported with the
  smoke check's finding.
- Drift: 1K and 32K, 1 and 4 streams, code and prose, replicates 0-1 (64 requests), seeds +30,000,000 and its own
  salt; reported as later over earlier per cell.

## Block L: long output

| Stage | Cap | In flight | Requests |
|---|---|---|---|
| L1 | 8,192 | 2 | 32 (4 contents × 4 prompts × 2 seeds) |
| L2 | 32,768 | 2 | 32 |
| L3 | 130,048 | 2 | 32 |
| L3s | 130,048 | 1 | 4 (prompt 0 of each content) |

- Inputs: the K3.25 Block L prompt set (prose, code, reasoning, JSON).
- Gate between stages: 0 HTTP errors, no new error lines in the server log, host memory above 10 GiB; a failure stops
  that engine's remaining stages.
- Analysis: the frozen K3.25 analyser, unchanged (stop against cap, lengths, decode rate by position, correctness:
  math answers, the hidden pytest suites in a CPU sandbox without network, the JSON schema, the prose length ratio),
  then the loop classification with the K3.25 audit's U5 correction applied from the start (R50 on the content span
  alone, the copy-from-reasoning share, "terminal loop" only with an exact period, "copy from reasoning" as its own
  category).
- The JSON tasks are sized for thinking off; they are labelled "infeasible by design" where the reasoning fills the
  cap.

## Power: what this design can and cannot show

Estimated from the K3.25 interval widths on the same panels.

| Measure | Smallest difference reliably detected |
|---|---|
| P-A KL20, C − Vmean | about 0.0013 (80% power, two-sided 5%) |
| P-B generated KL_pb20, all buckets | about 0.0025; at 8-16K about 0.003 |
| P-B top-1 | about 0.4 percentage points |
| Q2 NLL, 6 documents | can exclude an NLL penalty above about 0.004-0.005 nat; nothing per document type |
| Block T | per-cell ratios outside about ±8-10%; smaller differences read "level" |
| Block L | descriptive only: 2 seeds per prompt, 8 replies per content per stage; differences of 1-2 in 8 are not distinguishable |
| Startup | descriptive (one cold and one warm start per engine) |

## Guardrails

| Stage | Hard limit per step | Stop points |
|---|---|---|
| 1 | 60 min per launch | load failure; host memory below 10 GiB; garbage output; an unexplained prompt-token difference |
| 2 | 45 min per panel capture | a capture refused or malformed; a launch that cannot hold the panels; C's P-A window-0 NLL far from V's |
| 3 | 150 min per engine's full Block T, 45 min per drift subset | request errors; a launch that cannot hold the grid; host memory |
| 4 | L1 60 min, L2 150 min, L3 7 h, L3s 2 h per engine | any Block L gate |

Every later launch is checked against the frozen grid; a launch that cannot hold its stage's cells stops that stage,
and cells are never shrunk silently.

## Amendments

None.
