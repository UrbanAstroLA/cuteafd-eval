# CuteAFD v3.0.1 vs vLLM v0.9.2: higher-fidelity comparison — protocol DRAFT v2 (not frozen)

Status: draft for review. Nothing here has run. On approval it is frozen (SHA256 recorded in
the local change log) before the first GPU request; later changes are dated amendments, never silent edits.
Discovery behind it: `discovery-vllm-kld.md`, `discovery-cuteafd-fidelity.md` (zero GPU).

## Principles (why this is not a cherry-picked benchmark)

1. Grid, prompts, metrics and analysis fixed before any run. Prompts drawn from public sources by a
   fixed rule and seed; the few authored prompts (JSON, long code specs) are written and hashed here first.
2. Every cell reported: losses, errors, timeouts, cells an engine cannot run, and cells skipped for cost
   (listed below with the reason, before any run).
3. Same inputs, same scorer: identical token ids at identical positions, one scoring program per panel,
   one client for serving metrics.
4. Each engine as its author ships it, plus only the documented local deltas (listen address, request
   logging off, output limit raised, infiniband guard). Settings a measurement path requires (bench
   endpoint, API key, full-prefill logits) are listed per block.
5. Distinct recorded seed per request; analysis unit is the prompt or window, paired across engines.
6. Drift control: engine order C, V, then a predeclared subset of C again (CVC).
7. Intervals with every number; noise floors measured, not assumed.

## Arms

| Arm | Engine | Checkpoint | Role |
|---|---|---|---|
| V1 | vLLM v0.9.2 `ea0430aa` | K3.25-v1 `0490d2f7` | headline, as shipped |
| C1 | CuteAFD v3.0.1 `392db7c0` | Core-FP8 `d31ebc92` | headline, as shipped |
| C0 | CuteAFD v3.0.1 | K3.25-v1 `0490d2f7`, `GLM5_FLASH_FP8_MODEL_ID=off` | control, Block Q only |

Expert bytes are identical in all three. The engines' own arithmetic differs and is part of what is
compared, stated from source:

| | vLLM V1 | CuteAFD C1 | CuteAFD C0 |
|---|---|---|---|
| MLA / shared / dense projections | BF16 GEMMs | official FP8 E4M3 | FP8 quantized at load (pow2 scales) |
| KDA projections | BF16 | FP8 row128 | FP8 row128 |
| Output head | BF16 | FP8 | FP8 |
| KV | FP8 MLA (`fp8_ds_mla`) | FP8 MLA latent | FP8 MLA latent |
| KDA state | FP32 recurrent, BF16 conv | FP32 | FP32 |
| Router output | FP32 | FP32 | FP32 |

C1 vs C0 isolates the projection source inside one engine. A vLLM-on-Core-FP8 arm is not possible
without a loader change (discovery Q5) and is not run.

## Block Q — precision, teacher-anchored (0.5K-14.4K)

Teacher-forced, raw token ids (no chat template, no sampling), prefill-shaped on both engines.

| Panel | Windows | Context | Teacher | Scorer |
|---|---|---|---|---|
| P-A brandonmusic BF16 teacher (local, 30 GB) | 25 x 2,048, all 2,047 rows | 2K | full-vocab FP32 | ours (`kld_score.py`, fp64), cross-checked with Hugh Madden's `klgate.py` |
| P-B tpurtell `cuteafd-fidelity` glm5_flash v2 | 64 x last 512 rows (15,104 generated) | 0.5K-14.4K; buckets 0-2K / 2-8K / 8-16K | top-1024 + tail, from `zai-org/GLM-5.3-Flash-BF16` | port of his rule (`reference.rs:285-317`), validated against his CLI on C1 before use |

Metrics: KL(teacher‖engine), NLL, top-1, confident-top-1, top-3 containment; per window, per block, per
bucket, overall; paired bootstrap 95% intervals over windows. Generated rows are primary on P-B (his
rule); context rows reported separately.

Capture: vLLM through our prompt-logprob plugin (needs: windows.json loader, variable lengths, scored rows
only, batch-row offset fix); CuteAFD through `POST /v1/bench/probe` (`glmf-teacher-kl.py` path).
Shapes differ by engine and are recorded, not forced: vLLM chunks prefill at 2,048 tokens; CuteAFD
prefills token 0 alone, then up to 8,192 rows over 2 lanes.
Path settings: CuteAFD `ENABLE_BENCH=on`, `API_KEY_FILE` (key created with umask 077, shredded after),
`PROBE_DUMP_ROOT` under `<runs>/...`, `FULL_PREFILL_LOGITS=on`; vLLM speculation and prefix cache as
served (prompt-logprob requests skip the cache lookup).

Noise floor: V1 and C1 each scored twice; between-arm differences read against within-arm repeat difference.

**Load condition: not run.** CuteAFD's scoring takes an exclusive bench slot and runs alone
(`runner.rs:456-482`, `serve.rs:1059-1081`), so scoring under concurrent traffic cannot be done 1:1.
Batch-dependent numerics are covered only by the E1 router test already done.

**Context limit:** no teacher beyond 14,403 tokens (P-B's longest window; its design targeted 32K).

## Block Q2 — precision beyond 14K, teacher-free (32K, 64K, 128K)

- NLL on fixed long human-written documents, identical token ids for both engines, scored at the last
  4,096 positions of each length: public-domain books (PG-19 test split) and Apache-2.0 source code
  (vLLM's own source, local). 3 documents per type per length.
- Engine-vs-engine divergence: KL between the two engines' top-20 distributions at the same positions
  (disagreement, not correctness).
- Within-engine floor: each engine scores one document per length twice.
- Not a result: which engine is closer to BF16 beyond 14K.

## Block T — serving throughput

One client (`throughput.py`, extended), every stream its own request and seed, inputs made unique per
request (nonce first line) so no prompt is served from cache; one small cell measures cached prompts.

| Factor | Levels |
|---|---|
| Input | 1K, 8K, 32K, 128K |
| Output | 1,024 tokens (decode rate); time to first token separately |
| Concurrency | 1, 4, 8, 16 (16 = both engines' configured request limit) |
| Content | prose, code, reasoning (thinking on), JSON at 1K and 8K; prose and code at 32K and 128K |
| Replicates | 3 per cell, 4 prompts per content type, distinct seeds |

Skipped for cost, declared now: 128K input at 8 and 16 streams (1-2M prompt tokens per run).

## Block L — long output, staged to 128K

| Stage | Cap | Gate |
|---|---|---|
| L1 | 8K | 0 errors, logs clean |
| L2 | 32K | 0 errors, no memory warnings |
| L3 | 128K | — |

- Content: prose (LongBench-Write-style length-specified writing), code (4 authored multi-file specs with
  tests, hashed here before running), reasoning (thinking on; MATH-500 level 5 and similar with known
  answers), JSON (authored schema, N records).
- 8 concurrent requests, queued (32 per stage per engine: 4 content x 4 prompts x 2 seeds); plus a 1-stream
  subset (1 prompt per content) at L3.
- Measured: finish reason, length distribution, reasoning length, loop onset and exact period
  (`periods.py` from the long-reply work), decode rate vs position, errors; correctness where checkable
  (math answers; code tests in a CPU sandbox).

## Prompt sources (each download needs approval; licences confirmed before download)

| Source | Use | Approx. size |
|---|---|---|
| `wrldsuksgo2mars/cuteafd-fidelity` @ fixed revision, glm5_flash config | P-B | 212 MB |
| PG-19 test split, 6 books | Q2 long prose, T long inputs | ~10 MB |
| LongBench-Write prompts | L prose | <1 MB |
| MATH-500 | L reasoning, T reasoning | <1 MB |
| HumanEval+ / MBPP+ prompts | T code at 1K-8K | <5 MB |
| vLLM source (in the local image) | Q2 / T long code | 0 (local) |

## Cost (GPU-hours = wall hours x 2 GPUs; worst case = every reply runs to its cap)

| Block | Per engine, worst | Expected |
|---|---|---|
| Q + Q2 (incl. launch with bench settings) | 0.6 h | 0.5 h |
| C0 control (CuteAFD only) | 0.3 h | 0.25 h |
| T | 2.0 h | 1.5 h |
| L (L1+L2+L3, plus 1-stream subset) | 4.0 h | 2.0 h |
| Engine switches, CVC repeat subset | 1.0 h total | 0.8 h |
| **Total, both engines** | **~14 h wall, ~28 GPU-h** | **~9 h wall, ~18 GPU-h** |

Stage gates allow stopping after Q (cheapest, highest information), after T, or after any L stage.

## Stage 0 before any GPU (CPU only)

1. Plugin changes for P-B (windows loader, scored rows only, batch-row offset fix) with a CPU test.
2. P-B scorer port; P-A reader for CuteAFD's dump layout.
3. Prompt set built and hashed; authored prompts and tests written; protocol frozen.

## Amendments (dated)

**A1, 2026-10-26 ~17:15 (before freeze; written while CuteAFD Block Q captures were running).**
Block Q captures for CuteAFD (C1 P-B twice, C0 P-B once, C1 P-A twice, C1 Q2 started) ran from 16:32
on, before this protocol was frozen. Instruments were fixed and not tuned: tpurtell's own CLI and
published rule for P-B (our port validated against it on the same bytes: 0 difference on all 32,768
positions), our existing scorer for P-A. No vLLM precision result existed when the changes below
were made, and none depends on a comparison result:
1. Q2 engine-vs-engine divergence is full-vocabulary KL (both directions) and JS, not top-20
   (the scorer and both capture paths produce full rows; strictly more information).
2. Q2 within-engine floor: one prose and one code document per length scored twice (6 windows),
   not all 18; CuteAFD's scoring path takes ~10 min per 128K window.
3. P-B rows for CuteAFD come from his CLI's own dumps (his geometry: context prefilled normally, the
   512 scored rows through the scoring path). P-A and Q2 rows for CuteAFD come from
   `glmf-teacher-kl.py` (the whole window through the scoring path from token 1). vLLM computes all
   rows in its normal chunked prefill for every panel. Geometries are recorded per arm.
4. P-B context rows: reported separately as the protocol already said; noted that trailing context
   rows in tool-call windows show KL 1.5-4.6 nat on CuteAFD while generated rows in the same windows
   are normal (cause open; vLLM on the same rows will show whether it is reference- or engine-side).

**A2, 2026-10-26 (before freeze; before any Block T or L request).**
1. Thinking on for every Block T and L cell. Reason (source, not yet measured): the checkpoint's chat
   template, which vLLM is also configured with (`glm53-zai-a5b45eb.jinja`, byte-identical), has no
   thinking-off switch and always ends with `<|assistant|><think>`; CuteAFD implements
   `enable_thinking:false` itself as an empty `<think></think>`; vLLM ignores the flag, so its
   "thinking off" replies contain reasoning in the content. Thinking on gives both engines the same
   prompt. The difference is reported as a stack feature difference, not measured as throughput.
2. Sampling: temperature 1.0, top_p 0.95 (the checkpoint's generation_config), every T and L request.
3. Prompt set frozen by `stage0/prompts/MANIFEST.json` (SHA256 recorded at freeze), drivers by their
   hashes below; Block T is 1,016 requests per engine (16.2M prompt tokens), Block L 100 per engine.
