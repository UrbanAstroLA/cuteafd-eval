# cuteafd-eval

Maintained by Michael M: [UrbanAstroLA](https://github.com/UrbanAstroLA) on GitHub, [@UrbanAstroFella](https://x.com/UrbanAstroFella) on X.

{{HOME_INTRO}}

> This README and the results site in `docs/` are generated from the files under `results/` by `tools/build_readme.py`
> and `tools/build_site.py`. Each section below has a page of its own on the site.

## Findings

{{HOME_FINDINGS}}

## Does the precision difference matter?

Distance from the BF16 model, lower is closer. Each panel is one measure on one text set; compare rows within a panel.

{{HOME_BARS}}

{{HOME_MATTERS}}

## Pick by workload

What the published results show for common workloads, on this machine and these checkpoints. They describe the
measurements; they are not a general ranking.

{{HOME_PICK}}

## Settings measured

{{HOME_SETTINGS}}

## Speed in numbers

{{HOME_SPEED}}

## How sure are we

{{HOME_SURE}}

## Terms

{{HOME_GLOSSARY}}

## Status

{{STATUS}}
{{K4_STATUS}}

<!-- results:start -->
## Results in detail

Tables built from the published receipts; text and intervals per run in each run's README:
[`results/2026-10-26-cuteafd-vs-vllm`](results/2026-10-26-cuteafd-vs-vllm/) (K3.25, with
[`SUMMARY.md`](results/2026-10-26-cuteafd-vs-vllm/SUMMARY.md) and the separate review
[`AUDIT-2026-10-27.md`](results/2026-10-26-cuteafd-vs-vllm/AUDIT-2026-10-27.md)) and
[`results/2026-10-27-k4-vllm-cuteafd`](results/2026-10-27-k4-vllm-cuteafd/) (K4). One machine, one model family, one
tokenizer; intervals are 95% bootstrap intervals over windows or documents.

### K3.25: precision by context bucket

{{Q_BUCKETS}}

### K3.25: throughput

Block T, median of 3 replicates per cell (thinking on, 1,024 output tokens, every prompt unique, a distinct seed per
request). With thinking on, "code" and "json" cells measure reasoning text about a code or JSON prompt. Full grid:
[`{{T_LINK}}`](results/2026-10-26-cuteafd-vs-vllm/{{T_LINK}}); caveats:
[`t/CAVEATS.md`](results/2026-10-26-cuteafd-vs-vllm/t/CAVEATS.md).

{{T_TABLE}}

{{T_COUNTS}}

### K3.25: long output

Block L per stage: 4 contents × 4 prompts × 2 seeds, 8 requests in flight; L3s is one request at a time. Checks: code
against a hidden pytest suite, JSON against a schema, reasoning against the MATH-500 answer, prose by words written over
words required. {{L_NOTE}} Detail: [`l/SUMMARY.md`](results/2026-10-26-cuteafd-vs-vllm/l/SUMMARY.md).

{{L_TABLE}}

{{K4_RESULTS}}
<!-- results:end -->

## Running it: observations in detail

Each item is the behaviour as measured or as read in source, with how it is known. None is a claim about output quality.

### Capacity

{{CAPACITY}}

K3.25 leaves room for about 4.7 million tokens of KV cache on both engines; K4 for far fewer (1.38 million on the
vLLM fork, 447,488 on CuteAFD). K3.25's weights take about 69 GiB per GPU on the vLLM fork (its startup log); K4's
weight size is not in the published files. The smaller K4 pools are consistent with its 4-bit experts taking more
memory than K3.25's 3.25-bit ones, but that was not measured, and why CuteAFD's K4 pool is smaller than the vLLM fork's
was not examined beyond the planner's lines below.

CuteAFD on K4 needs one local setting on two RTX GPUs: at its defaults the planner refuses K4 (pool 260,608 tokens,
below its 1,048,576-token context floor); `MAX_CONTEXT_TOKENS=262144` gives a 447,488-token pool beside the desktop's
context on GPU 1 (the dry run predicted 605,696). Its BF16 KDA and BF16 head options do not fit a K4 serving launch. With that setting CuteAFD
serves K4 with prompts up to 262,144 tokens; the needle checks at 256K-1M tokens ran on K3.25.

### Startup

Startup time is the cost of switching models. "Ready" here is the engine's ready line in its server log: for K3.25
counted from container start (measured from the server logs:
[`results/2026-10-27-vllm-startup-cache`](results/2026-10-27-vllm-startup-cache/)). CuteAFD v3.0.1 is ready in 89 s: its
kernels are compiled ahead of time and shipped in the image (`PROGRAMS.json`), so there is no startup JIT; its CPU
planner computes the memory layout up front, so there is no profiling pass; and the experts load through a parallel
shared read in 30.6 s. On this setup, the container keeps `~/.cache` between starts but not the TileLang, Triton,
TorchInductor and CUDA kernel caches, so the vLLM fork v0.9.2 compiled 49 TileLang kernels at every start and was ready
in 697 s (11.6 min). Persisting those caches (pointing `TILELANG_CACHE_DIR`, `TRITON_CACHE_DIR`,
`TORCHINDUCTOR_CACHE_DIR` and `CUDA_CACHE_PATH` into the cache directory the container already keeps) brings it to
382 s (6.4 min, −45%):

| Phase | Caches not persisted | Caches persisted, warm |
|---|---|---|
| Process start and weight loading | 242 s (weights 135.7 s) | 254 s (weights 139.3 s) |
| TileLang JIT | 222 s (49 compiles) | 0 compiles |
| CUDA graph capture | 153 s | 58 s (43 s of it capturing graphs) |
| Warm-up (4 passes) | about 73 s | about 64 s |
| **Ready** | **697 s** | **382 s** |

The first start after the change fills the caches and takes 714 s; later starts are warm. What remains is mostly
weight loading (about 4 minutes including loader overhead). Other projects keep these caches between starts the same
way ([blackwell-llm-docker#73](https://github.com/local-inference-lab/blackwell-llm-docker/pull/73), which reports about
3.2 min of TileLang compiling per restart; [sglang#39364](https://github.com/sgl-project/sglang/pull/39364); vLLM's
[Docker guide](https://docs.vllm.ai/en/stable/deployment/docker/) mounts the Hugging Face cache and `~/.cache/vllm`).

On K4, counted from the start command (Stage 1 of the K4 run; one cold and one warm start per engine,
descriptive). The vLLM fork's 257 s warm start is not directly comparable with K3.25's 382 s: a different checkpoint,
measured in a different session (K3.25: the JIT-cache measurement of 2026-10-27 morning; K4: that evening, with the same
cache overlay); what differs between the two starts was not broken down. CuteAFD's K4 cold and warm starts (76 s and
86 s) are one start each, so their 10 s difference is not read as an effect.

{{K4_STARTUP}}

### Prefix cache

- **vLLM prefix-cache reuse is in whole 4,352-token blocks, without the last two blocks of a prompt** (measured, F2):
  repeated prompts of 1K to 8,704 tokens got 0 cached tokens; a 17,408-token prompt got 4,352, then 8,704. The server
  log shows the MLA cache groups at block size 4,352 in `align` mode. The v0.9.0 opt-in boundary lookup
  (`GLM53_DFLASH_BOUNDARY_LOOKUP`, default 0) was not tested.
- **CuteAFD restored a repeated 8K prompt from its prefix cache in 0.017 s** (Block T cached cell; the vLLM fork took
  2.10 s, uncached). Its serving launch keeps 20 entries. The K4 scoring launch turns the prefix cache off
  (`PREFIX_CACHE_ENTRIES=0`) to fit the full prefill-logits buffer beside the desktop's context; scoring probes never
  read the prefix cache, so no scored value changes.

### Thinking off and control tokens

- **Thinking off: the two stacks render different prompts** (prompt measured with one request; parser behaviour read in
  source). The checkpoint's chat template, byte-identical on both stacks, has no thinking switch and always ends with
  `<|assistant|><think>`. CuteAFD renders `enable_thinking: false` as an empty `<think></think>` (one more prompt
  token). vLLM renders the same prompt with the flag on or off (147 prompt tokens both times), and with it off its
  reasoning parser returns the generated reasoning as content. Thinking off would therefore give the two engines
  different prompts and different generated content, so every generation request in Blocks T and L runs with thinking on.
- **Control-token strings in user text** (measured in Block T and the K4 smoke checks). The 128K code prompts contain
  literal `<think>` and `</think>` strings; the vLLM stack parses them as control tokens, CuteAFD keeps them as text, so
  those prompts are 24 tokens longer on CuteAFD.

### Launcher defaults that matter

- **CuteAFD** (read in the launcher): output limit 4,096 tokens, which clamps longer requests (the runs here set
  `MAX_OUTPUT_TOKENS=393216`; with it, a 12,000-token request ran to its `max_tokens`, measured); request logging on
  unless `USAGE=off`; listen address `0.0.0.0` under host networking unless `ADDR` is set; the coordinator launch passes
  `--device=/dev/infiniband`, which Docker requires to exist (the runs here pass it only when it exists, in the same form
  as the repository's `wip.sh`: [`repro/cuteafd/patches/`](repro/cuteafd/patches/)). Its `swiglu_limit` is a compiled
  constant (10, this checkpoint's declared value); the value in `config.json` is parsed but not compared with it.
- **vLLM fork**: the runs use the v0.9.2 release image with the v0.9.0 repository's `start.sh` (its `IMAGE`
  override; the launcher is otherwise unchanged). Its GPU memory utilization defaults to 0.97, which does not start beside a desktop session on GPU 1
  (the runs use 0.95), and its port is published as `PORT` (default `8001`, on every interface; the runs use
  `127.0.0.1:8001`). The K4 launches also carried the stack's local environment overlay unchanged: the JIT caches
  above and a host-memory stopgap that calls `malloc_trim` in the workers periodically (noted in
  [`repro/k4/vllm/env.sh`](repro/k4/vllm/env.sh)).

### Determinism and drafting

- **vLLM's multi-chunk prefill is not run-to-run deterministic** (measured, Block Q captures, each run alone on the
  server). Rows inside the first 2,045-token prefill chunk are bit-identical between runs; rows beyond it almost never
  are. CuteAFD's repeats are byte-identical. CuteAFD is therefore compared with the mean of three vLLM runs from two
  launches (K3.25) or of two launches (K4).
- **Same seed, same prompt** (K4 smoke check, 3 prompts): CuteAFD returned identical text 3 of 3 times, the vLLM fork
  1 of 3; the cause was not examined. Repeats in these runs always use distinct seeds.
- **Draft acceptance** (measured on vLLM, drift subset): 1.53 of 3 drafted tokens accepted per verify step (51%).
  CuteAFD drafts adaptively and exposes no acceptance counter on its API.

### Other engine observations

- **CuteAFD converts K4's BF16 projections to FP8 at load** (read in source before the K4 freeze): attention, dense and
  shared projections in 128×128 blocks with pow2 scales, head and KDA projections per row. On K3.25 those projections
  came from the official FP8 checkpoint (Core-FP8); the vLLM fork serves them in BF16.
- **CuteAFD's router logits differ slightly between its two GEMM routes** (measured on one GPU, exploratory): across the
  160/161-row switch 0.36% of logits are bit-equal, the largest difference is 8.2e-5, and the top-8 expert set differs in
  2 of 64,000 rows; within each route the logits do not depend on the row count, and decode steps stay on one route.
  This is numerical variation between routes, the same kind as observed on the vLLM engine:
  [`results/2026-10-26-e1-router-route`](results/2026-10-26-e1-router-route/).
- **Earlier vLLM-engine items D1-D7 in CuteAFD** (read in source, not measured): the source audit maps the seven items
  from earlier evaluation (five of them addressed in tpurtell's v0.9.2) onto CuteAFD. For four, CuteAFD covers the same
  case in its own code; three do not arise in its design:
  [`results/2026-10-26-cuteafd-setup-checks`](results/2026-10-26-cuteafd-setup-checks/).

## Setup

**Hardware.** 2× NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition (300 W), driver 595.84, Linux 7.0, IOMMU in
pass-through mode. Besides the engine under test, the only processes on the GPUs were desktop graphics clients (about
2 GB on GPU 1), the same for both engines.

| | vLLM fork (V1) | CuteAFD (C1) | CuteAFD control (C0, Block Q only) |
|---|---|---|---|
| Engine | tpurtell/glm-5.3-flash-ext3-2x-rtx v0.9.2 (tag `f18f51f5`) | tpurtell/cuteafd v3.0.1 (`9098781f`) | same as C1 |
| Image | `ghcr.io/tpurtell/glm-5.3-flash-exl3-4bpw-2x-rtx:v0.9.2`, index `sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2` | `ghcr.io/tpurtell/cuteafd-coordinator:v3.0.1@sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a` | same as C1 |
| Checkpoint | `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-v1` @ `0490d2f708b12145f6516555ab066aaeb401cd21` | `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-Core-FP8` @ `d31ebc921f1f098b4a56d37aaccb3cdef4096184` | K3.25-v1 @ `0490d2f7`, `GLM5_FLASH_FP8_MODEL_ID=off` |
| Expert bytes | K3.25-v1 | identical to K3.25-v1: 150,047 of 150,047 base tensors byte-checked | K3.25-v1 |
| Projections | BF16 | official FP8 E4M3 (179 tensors) | FP8, quantized at load |
| Drafter | DFlash2, 3 draft tokens fixed, BF16, `incoai/GLM-5.3-Flash-DFlash2` @ `bf582e4e` | DFlash2, same checkpoint, adaptive depth, FP8 drafter | same as C1 |
| KV cache | FP8 MLA, 4,707,515 tokens | FP8 MLA latent, 4,726,784 tokens | |
| Request limit | 16 (`max-num-seqs`) | 16 (`CONCURRENCY` default) | |
| Startup to ready | 382 s with the JIT caches persisted on this setup (697 s without) | 89 s (kernels compiled ahead of time) | |
| Prefix cache | on, `align` mode (reuse in 4,352-token blocks, F2) | on (engine default) | |
| Attention and indexer | MLA layers owned whole by one GPU (`split:25`); FP8 index keys | MLA split by token across both GPUs (`context`); BF16 index keys | as C1 |
| Logits | BF16 before log-softmax | FP32 | as C1 |
| Local deltas | GPU memory utilization 0.95 (upstream 0.97, which does not start beside the desktop); listen address; launched with the v0.9.0 repository's start script and the v0.9.2 image | listen address 127.0.0.1:8001, request logging off (`USAGE=off`), `MAX_OUTPUT_TOKENS=393216`, the infiniband guard | as C1 |

Block Q additionally needs each engine's scoring path: CuteAFD's bench endpoint (`ENABLE_BENCH=on`, an API key,
`FULL_PREFILL_LOGITS=on`), and on vLLM a prompt-logprob capture plugin ([`repro/stage0/capture-vllm`](repro/stage0/capture-vllm/)).
The FP8 projections in Core-FP8 are reproducible from K3.25-v1's BF16 tensors with amax/448 128×128 block scales
(99.99998% of E4M3 codes equal): [`results/2026-10-26-cuteafd-setup-checks`](results/2026-10-26-cuteafd-setup-checks/).
Exact launch files: [`repro/cuteafd/`](repro/cuteafd/) and [`repro/REPRODUCE.md`](repro/REPRODUCE.md). GPU telemetry from
2026-10-27 01:06 on (after both engines' Block T): both GPUs at the 300 W cap while busy, GPU 0 median 1,890 MHz and 87 °C
([`telemetry/`](results/2026-10-26-cuteafd-vs-vllm/telemetry/)).

The K4 measurement used the same engines, images, drafter and machine with brandonmusic's GLM-5.3-Flash-tr3-4bpw
(`brandonmusic/GLM-5.3-Flash-tr3-4bpw` @ `a5fee929`) on both arms; its arms, declared differences and settings are in
[`METHOD.md`](results/2026-10-27-k4-vllm-cuteafd/METHOD.md).

## Confounds

What else differs between the two arms, and how each block handles it.

| Confound | What differs | How it is handled |
|---|---|---|
| Thinking-off rendering | CuteAFD renders off as `<think></think>`; vLLM's template ignores the flag | Blocks T and L run thinking on for every request (amendment A2), so both engines get the same prompt. |
| Chat template | Byte-identical Z.ai template on both; prompt token counts differ by one only when thinking is off | Thinking on everywhere; each request's real `prompt_tokens` is recorded. Block Q uses raw token ids, no template. |
| Prefix cache | CuteAFD restores repeated prompts from its cache; vLLM's `align` mode reuses whole 4,352-token blocks only, not the last two of a prompt (F2) | Every Block T and L prompt starts with a per-request nonce line, so no prompt is served from cache; one small cell measures cached prompts on purpose. vLLM's prompt-logprob requests skip the cache lookup. |
| FP8 vs BF16 arithmetic | CuteAFD: MLA, shared and dense projections, KDA projections and output head in FP8; vLLM: BF16 GEMMs. KV FP8 on both; router output FP32 on both | Part of what is compared: each engine as its author ships it. C0 isolates the projection source inside CuteAFD; follow-up F1 the optional FP8 paths. A vLLM arm on Core-FP8 would need a loader change and is not run. |
| Determinism | CuteAFD repeats are byte-identical; vLLM's rows beyond the first 2,045-token prefill chunk vary from run to run (every capture ran alone, so this is not batching) | CuteAFD is paired against the mean of three vLLM runs from two launches (F3); within-engine repeats are reported next to every difference. |
| Prefill shape | vLLM chunks prefill at about 2,048 tokens; CuteAFD prefills token 0 alone, then up to 8,192 rows over 2 lanes | Recorded per arm, not forced. |
| P-B trailing context rows | The panel's trailing context rows (excluded from the primary metrics) are 30 copies of one unrelated file; there, KL is 0.7-3.1 nat between engines and up to 1.96 nat between two vLLM runs | These rows react strongly to any numerical change, so they are not used as a precision probe; only generated rows are primary, as tpurtell's rule specifies. |
| Teacher context limit | No BF16 reference beyond 14,403 tokens (P-B's longest window) | Beyond 14K, Q2 compares the engines with each other and with their own repeats; it does not say which is closer to BF16. |
| Load condition | CuteAFD's scoring path takes an exclusive bench slot | Block Q is scored on idle servers only; batch-dependent numerics are covered only by the router route test. |
| Speculation | vLLM drafts 3 tokens per step with a BF16 drafter; CuteAFD drafts adaptively with an FP8 drafter | Both as shipped. vLLM accepts 1.53 of 3 drafted tokens per step (drift subset); CuteAFD's API exposes no acceptance counter. |
| Order and drift | Engines run one after the other on one machine | Order V then C; a drift repeat of 16 cells on each engine, hours later: medians within ±2%, single cells up to about ±13%. GPU telemetry from 01:06 on: both GPUs at the 300 W cap while busy. |
| Request inputs | Per-request nonces differ between the engines (prompt bodies identical); the 128K code prompts contain control-token strings that vLLM parses and CuteAFD keeps as text (24 tokens) | Reported per cell; the effect on throughput is small. The drift repeats reuse each engine's own nonces, so they are byte-identical to that engine's earlier cells. |
| Other arithmetic and geometry | Attention placement (vLLM `split:25`, CuteAFD `context`), index-key format (FP8 vs BF16), KDA output sharding, logits (BF16 vs FP32), prefill chunking | Part of each engine as shipped; listed so the precision differences are not read as one cause. F1 tests the switches CuteAFD exposes. |

Fixtures are not comparable across model families, and NLL is per tokenizer; every number here is one model family
and one tokenizer.

## Timeline

Chronological, times UTC−7. K3.25 checkpoint first ([`results/2026-10-26-cuteafd-vs-vllm`](results/2026-10-26-cuteafd-vs-vllm/)), then K4.

2026-10-26:

- **14:14-14:47.** CuteAFD v3.0.1 cloned at its release tag; local config and the infiniband guard; Core-FP8 checkpoint
  byte-checked against K3.25-v1 (expert bytes identical) and its FP8 projections checked against K3.25-v1's BF16; source
  audit; first start, ready in 89 s.
- **15:04.** Router route test on CuteAFD (one GPU, about a minute; exploratory).
- **15:56-16:38.** Zero-GPU discovery for a higher-fidelity comparison; prompt sources fetched with revisions, licences
  and hashes; the Stage 0 instruments built and tested on CPU.
- **16:32.** CuteAFD Block Q captures begin, before the protocol is frozen (declared in amendment A1: instruments fixed
  and not tuned, no vLLM precision result yet).
- **~17:15.** Amendment A1. Amendment A2: thinking on for every Block T and L request, sampling from the checkpoint's
  generation config, prompt set and drivers frozen by hash.
- **17:32.** Protocol frozen (`protocol/FROZEN.json`).
- **17:47 to before 18:35.** vLLM Block Q captures (capture plugin, then the normal server restored); Block Q scored on
  CPU by 18:40.
- **17:59.** Thinking-off check on vLLM (one request): the same 147-token prompt with thinking on and off; with it
  off, the reasoning parser returns the generated reasoning as content.
- **18:35-20:35.** Block T on vLLM: 1,008 measured requests, 0 errors.
- **20:36-22:39.** Block L on vLLM, stages L1 to L3s, 100 requests, 0 errors; analysed.
- **22:39.** Block T on CuteAFD started.
- **23:20.** Follow-ups F1 (CuteAFD FP8 ablation) and F2 (vLLM prefix cache) declared, after the Block Q results were
  known; they are labelled as outside the frozen protocol and are reported separately.

2026-10-27:

- **00:29.** Block T on CuteAFD finished (started 22:39): 1,008 measured requests, 0 errors.
- **~00:30.** F1 amendment A1: a speed subset per F1 arm, declared before any F1 request.
- **00:31-01:40.** F1: four CuteAFD scoring launches (KDA projections, head, prefill GEMMs, all three) on panel P-B,
  each with its speed subset, plus a speed baseline on the unchanged scoring launch.
- **01:04. Separate review** of Blocks Q, T and vLLM's Block L by a reviewer who did not run the measurements,
  read-only and CPU only
  ([`AUDIT-2026-10-27.md`](results/2026-10-26-cuteafd-vs-vllm/AUDIT-2026-10-27.md)). Results it established, written at
  the top of [`q/RESULTS-Q.md`](results/2026-10-26-cuteafd-vs-vllm/q/RESULTS-Q.md):
  - **vLLM's run-to-run variation comes from multi-chunk prefill.** Every vLLM capture ran alone; rows inside the first
    2,045-token prefill chunk are bit-identical between runs, rows beyond it almost never are.
  - **The headline pairs CuteAFD against the mean of the vLLM runs**, since one vLLM run is one draw of a varying engine.
    The 2-8K top-1 difference against the first run does not hold against the second.
  - **Length and content are not separated.** The 8-16K bucket is block B, long code reading; within block A, the only
    block present at every length, the KL difference is flat.
  - **Q2: no NLL difference larger than about ±0.005 nat at 32K-128K** on 6 documents. Per-type intervals rest on 3
    documents each; engine-vs-engine disagreement is about 1.8x vLLM's own run-to-run disagreement on matched documents.
  - **Trailing context rows are sensitive to any numerical change.** They are 30 copies of one unrelated file, and vLLM
    differs from itself there by up to 1.96 nat; they are not used as a precision probe.
  - **C0 control:** C1 − C0 −0.0003 [−0.0019, +0.0014].
- **~01:15.** Declared after the audit and before any of these requests: the drift subset, F3 (a second vLLM launch
  for precision) and vLLM draft-acceptance counters; GPU telemetry logged every 5 s.
- **01:42-03:21.** Block L on CuteAFD, stages L1 to L3s, 100 requests, every gate passed; analysed together with
  vLLM's run.
- **03:22-03:35.** Drift repeat on CuteAFD (same launch, same seeds and nonces as its Block T cells).
- **03:35-03:51.** F3: a fresh vLLM capture launch, P-B and P-A captured once more (run V2).
- **04:03-04:17.** Drift repeat on vLLM (fresh normal launch) with acceptance counters; F2 prefix-cache lengths.
- **04:32. Evaluation complete.** Every slot of the run done; summary written
  ([`SUMMARY.md`](results/2026-10-26-cuteafd-vs-vllm/SUMMARY.md)).
- **10:55-11:14.** vLLM JIT caches persisted on this setup (TileLang, Triton, TorchInductor and CUDA, into the cache
  directory the container already keeps): startup 697 → 382 s; the first start after the change fills the caches (714 s)
  ([`results/2026-10-27-vllm-startup-cache`](results/2026-10-27-vllm-startup-cache/)).
{{NEEDLE_LINE}}
{{TIMELINE_K4}}

## Other runs

Not part of the comparison above. Exploratory runs and checks are labelled as such in their folders and never share a
table with the measured results.

{{OTHER_RUNS}}

## Reproduce

[`repro/REPRODUCE.md`](repro/REPRODUCE.md) walks through it step by step: the engines and checkpoints, the CuteAFD
configs and launcher patch, the vLLM capture plugin, the prompt build (with hashes to confirm), the drivers, the scorers
and the analysis. Adding a new engine version, arm or follow-up: [`iterations/`](iterations/).

```bash
python3 tools/verify.py          # manifests, published-copy hashes, labels, content scan
python3 tools/build_readme.py    # rebuild this README and the run summaries from results/
python3 tools/build_site.py      # rebuild the site in docs/
```

The tools in `tools/` need Python 3.10+ and its standard library only; the scorers in `repro/stage0/scorers/` also
need numpy and scipy.

## Layout

```
protocol/                     the frozen protocol, amendments, follow-ups, dataset provenance; HASHES.json ties copies to the frozen hashes
results/<date>-<run>/         RUN.json (kind, arms, slot status), README.md, MANIFEST.json, per-block summaries
repro/                        REPRODUCE.md; stage0/ (drivers, scorers, capture plugin, prompt build); cuteafd/ (configs, patch, plan receipts); k4/ (K4 launch files)
iterations/                   how a new iteration is frozen, run, exported and verified; TEMPLATE/
tools/                        verify.py, build_readme.py, build_site.py (its charts: site_charts.py), README templates
docs/                         the results site (GitHub Pages, served from main /docs), built by tools/build_site.py
MANIFEST.json                 sha256 of every file in the repository
```

Published copies replace local paths with placeholders such as `<run>/`, `<runs>/`, `<datasets>/`, `<cuteafd>/`,
`<hf-hub>/`, so those files differ from their frozen hashes; `protocol/HASHES.json` lists which files are byte-identical.
No logit dumps, token ids or generated reply texts are published: summaries, receipts, small JSON, and per-position scores
as compact CSV (`q/rows/`).

## Licenses

Code: Apache-2.0 (`LICENSE`). Results and documentation: CC BY 4.0 (`LICENSE-DATA.md`). Third-party material (prompt sources, tpurtell's fidelity set,
both engines, the checkpoints) is attributed in [`NOTICE.md`](NOTICE.md) and stays under its own licence. Cite with
[`CITATION.cff`](CITATION.cff).
