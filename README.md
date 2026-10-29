# cuteafd-eval

Maintained by Michael M: [UrbanAstroLA](https://github.com/UrbanAstroLA) on GitHub, [@UrbanAstroFella](https://x.com/UrbanAstroFella) on X.

Two inference engines by the same author, **tpurtell** (`wrldsuksgo2mars` on Hugging Face), on the same model
and machine:

- **CuteAFD** ([tpurtell/cuteafd](https://github.com/tpurtell/cuteafd)), his own runtime, built for attention/FFN
  disaggregation (AFD): attention and the expert (feed-forward) layers run as separate workers, so experts can sit on
  other machines; here, on two GPUs, they stay local.
- **His vLLM fork** ([tpurtell/glm-5.3-flash-ext3-2x-rtx](https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx)), his
  vLLM-based engine for this model on two RTX GPUs.

The model is GLM-5.3-Flash on two RTX PRO 6000 Blackwell Max-Q GPUs at 300 W, in two quantized checkpoints: **K3.25**
(tpurtell's mixed 3.25-bit EXL3 experts) and **K4** (brandonmusic's 4-bit EXL3 experts, Local Inference Lab). The
questions: how close each engine stays to the original BF16 model, how fast it is, and how to set it up.

Results as of 2026-10-28; versions tested: CuteAFD v3.0.1, vLLM fork v0.9.2. Measured by Michael M (UrbanAstroLA).

> This README and the results site in `docs/` are generated from the files under `results/` by `tools/build_readme.py`
> and `tools/build_site.py`. Each section below has a page of its own on the site.

## Findings

- **Precision: the quantization matters more than the engine.** On K3.25, KL from the BF16 model (teacher panel) is 0.0458 on the vLLM fork and 0.0476 on CuteAFD. The largest engine difference is on long code (8-16K-token prompts): CuteAFD +0.0054 further on K3.25, +0.0090 on K4 (top-20 measure). [Precision](results/2026-10-26-cuteafd-vs-vllm/q/RESULTS-Q.md)
- **Speed: CuteAFD generates faster; under concurrency the vLLM fork's first tokens come sooner.** One stream: 114-168 tokens/s on the vLLM fork, 120-235 on CuteAFD (K3.25). First token, one request: 1K prompt 0.25 s and 0.41 s, 128K prompt 35.1 s and 29.6 s. With 4-16 requests at once the vLLM fork's first tokens come sooner in most cells, while tokens per second are level or ahead on CuteAFD except at 1K × 8. [Speed](results/2026-10-26-cuteafd-vs-vllm/t/T-SUMMARY.md)
- **A CuteAFD setting trades about 4% first-token time for precision.** W8A16 prefill closes about 59% of the long-code difference on K3.25 (8K prose prompt 1.808 → 1.878 s); W8A16 prefill with the amax scale rule closes about two thirds on K4 (32K code prompt 7.38 → 7.69 s), decode level. [Settings](results/2026-10-27-k4-vllm-cuteafd/f1k4/RESULTS-F1K4b.md)
- **Long tasks: the same at the longest cap; CuteAFD finished more code at 32K.** At the 128K cap code passed every test in 7/8 (K3.25) and 8/8 (K4) on both engines, math 8/8. At the 32K cap CuteAFD finished 4/8 (K3.25) and 5/8 (K4) code tasks, the vLLM fork 0/8 and 0/8, consistent with CuteAFD's shorter code replies (0.74x and 0.77x the vLLM fork's median length at 128K); descriptive, n = 8. Needles in prompts of 256K to 1M tokens (K3.25): all found on both (exploratory); at 1M the first token took 270 s on the vLLM fork and 254 s on CuteAFD. [Long tasks](results/2026-10-26-cuteafd-vs-vllm/l/SUMMARY.md)
- **Practical.** Ready to serve in 382 s on the vLLM fork (JIT caches kept) and 89 s on CuteAFD. A repeated 8K prompt: 2.10 s on the vLLM fork, 0.017 s from CuteAFD's prefix cache. Only CuteAFD honours "thinking off". K4 KV cache: 1,377,179 tokens on the vLLM fork, 447,488 on CuteAFD. [Running it](#running-it-observations-in-detail)

## Does the precision difference matter?

Distance from the BF16 model, lower is closer. Each panel is one measure on one text set; compare rows within a panel.

| Panel and measure | Row | KL from BF16 |
|---|---|---|
| K3.25 · BF16 teacher panel (P-A) · full-vocabulary KL | vLLM fork | 0.0458 |
|  | CuteAFD | 0.0476 |
| K3.25 · tpurtell's fidelity set (P-B), all generated positions · coarse KL | Official FP8 model (tpurtell's baseline) | 0.0216 |
|  | vLLM fork | 0.0451 |
|  | CuteAFD | 0.0484 |
|  | CuteAFD, W8A16 prefill | 0.0468 |
| K3.25 · the same set, 8-16K long code · coarse KL | vLLM fork | 0.0504 |
|  | CuteAFD | 0.0557 |
|  | CuteAFD, W8A16 prefill | 0.0525 |
| K3.25 and K4 · BF16 teacher panel (P-A) · top-20 KL (KL20) | K3.25, vLLM fork | 0.0365 |
|  | K3.25, CuteAFD | 0.0380 |
|  | K4, vLLM fork | 0.0192 |
|  | K4, CuteAFD | 0.0219 |

KL is how far an engine's next-token probabilities are from the BF16 model's on the same text (0 is
identical, lower is closer; units: nats).

- **The quantization's own distance dwarfs the engine difference.** On tpurtell's set his official FP8 model scores
  0.0216, the 3.25-bit checkpoint 0.0451 (vLLM fork) and 0.0484 (CuteAFD): the engine difference is
  7% of the vLLM fork's distance (11% on long code). K4 roughly halves the distance on both.
- **tpurtell's bar** counts a paired change below 0.005 KL or 0.5 top-1 points as within it (defined for changes to one
  engine; applied here by analogy). K3.25 overall is inside on KL (+0.0033, interval to +0.0049), not on
  top-1 (−0.46 points, to −0.73); long code is not shown inside on either checkpoint
  (+0.0054, +0.0090); K4 with W8A16 prefill + amax reads +0.0030 (to +0.0049).
- **On tasks**, code and math checks at the 128K cap and the needle checks came out the same on both engines.
- **Not measured:** the distance from BF16 beyond 14.4K tokens (no reference exists there) and on the decode path
  (scoring runs prompts through prefill).

## Pick by workload

What the published results show for common workloads, on this machine and these checkpoints. They describe the
measurements; they are not a general ranking.

| Workload | The data shows | Key numbers (vLLM fork first, CuteAFD second) | Evidence |
|---|---|---|---|
| Long code (8-16K), closest to BF16 | vLLM fork closer to BF16 | KL at 8-16K: 0.0504 vs 0.0557 (K3.25); 0.0334 vs 0.0424 (K4, top-20) | [Precision](results/2026-10-26-cuteafd-vs-vllm/q/RESULTS-Q.md) |
| CuteAFD on K3.25, closer to BF16 | W8A16 prefill closes about 59% of the difference | difference +0.0054 → +0.0022; first token +3.8% to +4.5% per cell | [Settings](results/2026-10-26-cuteafd-vs-vllm/f1/RESULTS-F1.md) |
| CuteAFD on K4, two RTX GPUs | W8A16 prefill + amax scale rule closes about two thirds; the BF16 options do not fit | difference +0.0090 → +0.0030; first token +4.0% to +4.2% per cell | [Settings](results/2026-10-27-k4-vllm-cuteafd/f1k4/RESULTS-F1K4b.md) |
| One request at a time | CuteAFD generates faster | 114-168 vs 120-235 tok/s | [Speed](results/2026-10-26-cuteafd-vs-vllm/t/T-SUMMARY.md) |
| Long prompts, one at a time | CuteAFD's first token sooner | 128K: 35.1 s vs 29.6 s | [Speed](results/2026-10-26-cuteafd-vs-vllm/t/T-SUMMARY.md) |
| Short prompts, many at once | vLLM fork's first token sooner; tokens/s higher on the vLLM fork at 1K × 8, level at 1K × 16 | 1K × 8: 1.44 s vs 2.76 s, 345-454 vs 321-410 tok/s; 1K × 16: 2.38 s vs 4.31 s, 378-508 vs 397-516 tok/s | [Speed](results/2026-10-26-cuteafd-vs-vllm/t/T-SUMMARY.md) |
| Many long prompts at once | vLLM fork's first tokens sooner; CuteAFD's tokens/s higher | 32K × 16: 72 vs 106 s, 100-105 vs 107-112 tok/s | [Speed](results/2026-10-26-cuteafd-vs-vllm/t/CAVEATS.md) |
| Repeated long prefix | CuteAFD reuses it | 8K repeated: 2.10 vs 0.017 s | [Running it](results/2026-10-26-cuteafd-vs-vllm/f2/RESULTS-F2.md) |
| Long replies (to 128K) | same code and math at the 128K cap; CuteAFD finished more code at 32K | 128K code: 7/8 vs 7/8; 32K code finished: 0/8 vs 4/8 (K3.25) | [Long tasks](results/2026-10-26-cuteafd-vs-vllm/l/SUMMARY.md) |
| Switching models often | CuteAFD starts faster | 382 vs 89 s | [Running it](results/2026-10-27-vllm-startup-cache/) |
| Many long contexts at once (K4) | vLLM fork holds about 3x the KV cache | 1,377,179 vs 447,488 tokens | [Running it](results/2026-10-27-k4-vllm-cuteafd/startup/startup.json) |
| K4 on CuteAFD, two RTX GPUs | context up to 262,144 tokens (MAX_CONTEXT_TOKENS); the 256K-1M needle checks ran on K3.25 | 262,144 tokens | [Running it](results/2026-10-27-k4-vllm-cuteafd/METHOD.md) |

## Settings measured

The configurations measured here, as files you can copy; with each, what it measured. **Measured, not a
recommendation.** The exact files are in [repro/](repro/); checkpoints download as in
[Reproduce, step 1](repro/REPRODUCE.md).

**vLLM fork v0.9.2, both checkpoints.** Startup 697 → 382 s with the JIT caches kept (K3.25).

```bash
# the launcher: tpurtell's vLLM fork repository at tag v0.9.0; its start.sh runs the v0.9.2 image pinned below
git clone https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx && cd glm-5.3-flash-ext3-2x-rtx && git checkout v0.9.0
export IMAGE=ghcr.io/tpurtell/glm-5.3-flash-exl3-4bpw-2x-rtx@sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2
export MODEL_PROFILE=k325                # k4 for the K4 checkpoint
export GPU_MEMORY_UTILIZATION=0.95       # the default 0.97 does not start beside a desktop session
export PORT=127.0.0.1:8001               # the default publishes port 8001 on every interface
# keep the JIT caches inside the cache directory the container already keeps between starts
export DEBUG_ENV="TILELANG_CACHE_DIR=/root/.cache/tilelang
  TRITON_CACHE_DIR=/root/.cache/triton
  TORCHINDUCTOR_CACHE_DIR=/root/.cache/torchinductor
  CUDA_CACHE_PATH=/root/.cache/nv/ComputeCache"
./start.sh
```

**CuteAFD v3.0.1: the launcher.** On a host without `/dev/infiniband`, apply the guard in
[repro/cuteafd/patches/](repro/cuteafd/patches/) first.

```bash
git clone https://github.com/tpurtell/cuteafd && cd cuteafd && git checkout v3.0.1
mkdir -p local                           # save the config below as local/<name>.config, then:
./run.sh --config local/<name>.config --restart
```

**CuteAFD on K3.25, as shipped** (`glm53-flash-exl3-k3.25-core-fp8-2rtx.config`; `ADDR`, `MAX_OUTPUT_TOKENS` and `USAGE`
are the local settings: the launcher defaults are `0.0.0.0` under host networking, a 4,096-token output limit, and
request logging on).

```bash
MODEL_ID=wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-Core-FP8
MODEL_REVISION=d31ebc921f1f098b4a56d37aaccb3cdef4096184
GLM5_FLASH_FP8_MODEL_ID=off
SPECULATOR=dflash2
SPECULATOR_MODEL_ID=incoai/GLM-5.3-Flash-DFlash2
SPECULATOR_MODEL_REVISION=bf582e4eacc1810f76656d1811693ff6c6737d2a
POOL_TOKENS=auto
EXPERT_BACKEND=local
SPARK_COUNT=0
RTX_GPUS=2
COORDINATOR_GPU=0
ADDR=127.0.0.1:8001
MAX_OUTPUT_TOKENS=393216
USAGE=off
COORDINATOR_DOCKER_INFERENCE=ghcr.io/tpurtell/cuteafd-coordinator:v3.0.1@sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a
```

**With the measured setting, W8A16 prefill:** append the line below. Measured: long-code difference from the vLLM fork
+0.0054 → +0.0022, first token +3.8% to +4.5% per cell, decode
0.99x (scoring launches, follow-up F1).

```bash
GLM5_FLASH_FP8_PREFILL=off
```

**CuteAFD on K4, as shipped** (`glm53-flash-exl3-k4-2rtx.config`; `MAX_CONTEXT_TOKENS=262144` is needed on two RTX GPUs,
where the planner refuses K4 at its default). Measured: KV pool 447,488 tokens, 16 requests at once.

```bash
MODEL_ID=brandonmusic/GLM-5.3-Flash-tr3-4bpw
MODEL_REVISION=a5fee929cf4888b1824323e33e8a19b60129e025
GLM5_FLASH_FP8_MODEL_ID=off
SPECULATOR=dflash2
SPECULATOR_MODEL_ID=incoai/GLM-5.3-Flash-DFlash2
SPECULATOR_MODEL_REVISION=bf582e4eacc1810f76656d1811693ff6c6737d2a
POOL_TOKENS=auto
MAX_CONTEXT_TOKENS=262144
VISION=off
EXPERT_BACKEND=local
SPARK_COUNT=0
RTX_GPUS=2
COORDINATOR_GPU=0
ADDR=127.0.0.1:8001
MAX_OUTPUT_TOKENS=393216
USAGE=off
COORDINATOR_DOCKER_INFERENCE=ghcr.io/tpurtell/cuteafd-coordinator:v3.0.1@sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a
```

**With the measured setting, W8A16 prefill + amax scale rule:** append the two lines below. Measured: long-code
difference +0.0090 → +0.0030, teacher panel no longer resolved, first token +4.0% to
+4.2% per cell, decode level, the same memory.

```bash
GLM5_FLASH_FP8_PREFILL=off
FP8_SCALES=amax
```

## Speed in numbers

|  | K3.25: vLLM fork | K3.25: CuteAFD | K4: vLLM fork | K4: CuteAFD |
|---|---|---|---|---|
| Decode, 1 stream, tok/s | 114-168 | 120-235 | 108-164 | 116-220 |
| Decode per stream, 4 streams (1K-8K), tok/s | 59-99 | 61-117 | 55-93 | 63-114 |
| First token, 1K | 0.25 s | 0.41 s | 0.27 s | 0.42 s |
| First token, 8K | 2.11 s | 1.80 s | 2.20 s | 1.84 s |
| First token, 32K | 8.70 s | 7.26 s | 9.05 s | 7.38 s |
| First token, 128K | 35.1 s | 29.6 s | 36.4 s | 30.1 s |
| Startup to the ready line | 382 s (697 s without JIT caches) | 89 s | 257 s warm, 307 s cold | 86 s warm, 76 s cold |
| KV cache, tokens | 4,707,515 | 4,726,784 | 1,377,179 | 447,488 |

Decode: range over content types and 1K-128K prompts; first token: median over content types, one request at a time; 1,024 tokens per request. Startup and KV cache: [Running it](#startup). Every speed cell: [Speed](results/2026-10-26-cuteafd-vs-vllm/t/T-SUMMARY.md).

## How sure are we

- **K3.25:** frozen protocol. After the runs, a separate reviewer who did not run the measurements re-ran the
  scorers and checked the claims against the receipts; its corrections are applied ([Review](results/2026-10-26-cuteafd-vs-vllm/AUDIT-2026-10-27.md)).
  It covered the precision and speed blocks and the vLLM fork's long output; it did **not** cover CuteAFD's long output,
  the follow-ups F1-F3 (it saw their designs and the F1 baseline speed run), the drift repeats, the startup measurement
  or the needle pilot. CuteAFD is paired with three vLLM runs from two launches. Thin: 8 long replies per content type,
  six long documents. K3.25 speed noise: a repeat hours later moved the median by under 2% and single cells by up to 13%; single-cell ratios within ±10% read as level.
- **K4:** frozen protocol; **no separate review** of any part of it, its settings follow-ups included. CuteAFD is
  paired with two vLLM launches. K4 speed noise: a ±8% band declared before the run (both engines' drift repeats stayed inside it); single-cell ratios within ±8% read as level.
- **One machine:** two RTX PRO 6000 Blackwell Max-Q cards at 300 W, with a desktop session using about 2 GB on GPU 1;
  speed on other power limits or cards was not measured.

## Terms

- **AFD**: attention/FFN disaggregation: attention and the expert layers run as separate workers.
- **BF16 model**: the original, unquantized model; the precision reference.
- **K3.25, K4**: the two quantized checkpoints (3.25-bit and 4-bit EXL3 experts).
- **FP8**: 8-bit floating point, CuteAFD's format for the other weights.
- **KL**: distance between next-token distributions, in nats; 0 is identical.
- **Coarse KL, KL20, KL_pb20, KL20n**: KL over the reference's top 1,024 tokens plus the rest (tpurtell's rule); over each engine's top 20 (K4, teacher panel); the top-20 form of tpurtell's rule (K4, fidelity set); top 20 shared by two engines (K4, long texts).
- **Top-1**: how often the most likely next token matches the reference's.
- **P-A, P-B, Q2**: the text sets: BF16 teacher texts (2K tokens), tpurtell's fidelity set (to 14.4K), six long documents.
- **Long code (8-16K)**: P-B's longest prompts, all code reading.
- **95% interval, resolved**: a difference's likely range; resolved if it excludes zero.
- **Level**: a speed ratio inside the noise band: not a difference.
- **Prefill, decode**: reading the prompt; generating tokens.
- **First token**: time until the first generated token.
- **Stream**: one request in flight.
- **W8A8, W8A16**: CuteAFD prefill with 8-bit or 16-bit activations.
- **Scale rule**: how CuteAFD makes FP8 scales from BF16 weights at load: pow2 (powers of two, the default), amax (from the largest value), best (the launcher's third rule).
- **KDA, head**: linear-attention projections; the final vocabulary layer.
- **Drafter**: DFlash2, a small model that proposes tokens for the main model to check (speculative decoding).
- **Serving, scoring launch**: the engine as users run it; the same engine with the endpoints that return per-position probabilities for precision scoring.
- **Block Q, T, L**: the measurement blocks: precision, speed (throughput), long output.
- **Run labels**: K3.25: V1 and V1r (vLLM fork, one launch), V2 (a second launch), C1 (CuteAFD), C0 (CuteAFD control on K3.25-v1); K4: V-r1 and V-r2 (two vLLM launches), C-r1 (CuteAFD).
- **Prefix cache**: reuse of a repeated prompt's processed state.
- **JIT caches**: kernels compiled at startup, kept between starts.
- **Thinking**: the model's reasoning before its answer; always on here.

## Status

- Block Q, precision (V1, C1, C0): done
- Block Q per-position scores (P-B, Q2) and tail and position statistics (P-A, P-B, Q2): done
- Block T, throughput: vLLM fork v0.9.2 (V1): done
- Block T, throughput: CuteAFD v3.0.1 (C1): done
- Block L, long output: vLLM fork v0.9.2 (V1): done
- Block L, long output: CuteAFD v3.0.1 (C1): done
- Follow-up F1, CuteAFD FP8 switches: precision at 8-16K and speed (outside the frozen protocol): done
- Follow-up F2, vLLM prefix-cache reuse on repeated prompts (outside the frozen protocol): done
- Follow-up F3, second vLLM launch for precision (outside the frozen protocol): done
- Drift check, repeat subset on both engines: done
- GPU telemetry during the later runs (summary): done
- K4: Startup and smoke checks (Stage 1, before the freeze): done
- K4: Block Q, precision (top-20 measures): P-A, P-B, Q2: done
- K4: Block Q per-position scores and tails (P-A, P-B, Q2): done
- K4: Block T, throughput, with drift repeats: done
- K4: Block L, long output: done
- K4: Follow-ups F1-K4 (W8A16 prefill), F1-K4b (FP8 switches), K4c (W8A16 + amax) and K4d (W8A16 + best), CuteAFD on K4 (outside the frozen protocol): done
- K4: Q2 document c2: rows where vLLM differs from itself: done

<!-- results:start -->
## Results in detail

Tables built from the published receipts; text and intervals per run in each run's README:
[`results/2026-10-26-cuteafd-vs-vllm`](results/2026-10-26-cuteafd-vs-vllm/) (K3.25, with
[`SUMMARY.md`](results/2026-10-26-cuteafd-vs-vllm/SUMMARY.md) and the separate review
[`AUDIT-2026-10-27.md`](results/2026-10-26-cuteafd-vs-vllm/AUDIT-2026-10-27.md)) and
[`results/2026-10-27-k4-vllm-cuteafd`](results/2026-10-27-k4-vllm-cuteafd/) (K4). One machine, one model family, one
tokenizer; intervals are 95% bootstrap intervals over windows or documents.

### K3.25: precision by context bucket

Panel P-B, generated rows, against the mean of the three vLLM runs (two launches; `pb-vs-vllm-mean3.json`). The 8-16K bucket is block B, long code reading; whether length or content drives the difference is not separated here. F1c and F1d are follow-up F1 arms of CuteAFD, outside the frozen protocol. History: the tokens before each scored position. Tails (p99, p99.9) and KL by position: [`q/tails/`](results/2026-10-26-cuteafd-vs-vllm/q/tails/).

| Bucket | Rows | History, tokens (min / median / max) | KL, CuteAFD − vLLM | Top-1, CuteAFD − vLLM | KL, F1c (W8A16 prefill) − vLLM | KL, F1d (KDA, head, prefill) − vLLM |
|---|---|---|---|---|---|---|
| all generated rows | 15,104 | 1,084 / 5,751.5 / 14,402 | +0.0033 [+0.0016, +0.0049] | -0.46 pts [-0.73, -0.17] | +0.0017 [+0.0006, +0.0028] | +0.0010 [-0.0002, +0.0021] |
| 0-2K | 4,035 | 1,084 / 1,735 / 2,361 | +0.0017 [-0.0006, +0.0044] | -0.38 pts [-0.88, +0.05] | +0.0007 [-0.0010, +0.0027] | +0.0008 [-0.0011, +0.0028] |
| 2-8K | 3,547 | 2,083 / 4,254 / 5,781 | +0.0007 [-0.0029, +0.0032] | +0.19 pts [-0.16, +0.52] | +0.0016 [+0.0007, +0.0026] | -0.0001 [-0.0017, +0.0013] |
| 8-16K | 7,522 | 10,284 / 12,069 / 14,402 | +0.0054 [+0.0034, +0.0074] | -0.81 pts [-1.22, -0.44] | +0.0022 [+0.0005, +0.0041] | +0.0016 [-0.0005, +0.0033] |

### K3.25: throughput

Block T, median of 3 replicates per cell (thinking on, 1,024 output tokens, every prompt unique, a distinct seed per
request). With thinking on, "code" and "json" cells measure reasoning text about a code or JSON prompt. Full grid:
[`t/T-SUMMARY.md`](results/2026-10-26-cuteafd-vs-vllm/t/T-SUMMARY.md); caveats:
[`t/CAVEATS.md`](results/2026-10-26-cuteafd-vs-vllm/t/CAVEATS.md).

| Input | Content | Decode tok/s per stream, 1 stream: vLLM | CuteAFD | Streams | Aggregate tok/s: vLLM | CuteAFD | TTFT s, 1 stream: vLLM | CuteAFD |
|---|---|---|---|---|---|---|---|---|
| 1K | prose | 120.7 | 125.7 | 16 | 377.9 | 397.0 | 0.25 | 0.41 |
| 1K | code | 145.2 | 196.0 | 16 | 476.8 | 483.6 | 0.25 | 0.41 |
| 1K | reasoning | 161.2 | 228.0 | 16 | 508.1 | 516.2 | 0.26 | 0.41 |
| 1K | json | 130.8 | 154.9 | 16 | 473.1 | 462.1 | 0.25 | 0.40 |
| 8K | prose | 117.4 | 119.8 | 16 | 233.1 | 244.9 | 2.11 | 1.80 |
| 8K | code | 151.1 | 174.6 | 16 | 263.7 | 278.0 | 2.10 | 1.80 |
| 8K | reasoning | 168.4 | 234.7 | 16 | 255.5 | 277.7 | 2.11 | 1.81 |
| 8K | json | 130.1 | 146.1 | 16 | 260.0 | 271.1 | 2.11 | 1.80 |
| 32K | prose | 114.4 | 121.4 | 16 | 99.6 | 106.6 | 8.71 | 7.26 |
| 32K | code | 148.0 | 169.3 | 16 | 105.1 | 112.1 | 8.70 | 7.27 |
| 128K | prose | 119.5 | 122.9 | 4 | 27.5 | 30.6 | 35.08 | 29.58 |
| 128K | code | 150.2 | 165.3 | 4 | 28.2 | 31.3 | 35.02 | 29.57 |

CuteAFD v3.0.1: 1,008 measured requests in 132 batches, 0 errors, 0 replies with `</think>` in the content; vLLM fork v0.9.2: 1,008 measured requests in 132 batches, 0 errors, 0 replies with `</think>` in the content.

### K3.25: long output

Block L per stage: 4 contents × 4 prompts × 2 seeds, 8 requests in flight; L3s is one request at a time. Checks: code
against a hidden pytest suite, JSON against a schema, reasoning against the MATH-500 answer, prose by words written over
words required. The terminal-loop counts on code replies come from the detector counting the answer restating code drafted in the reasoning; no periodic structure was found in them (audit U5). The code, JSON and prose tasks were sized for thinking off: at the L1 and L2 caps, and for the 1,030-record JSON task at L3, the reasoning leaves too little room for the answer, so those cells measure stop-versus-cap rather than task completion. Detail: [`l/SUMMARY.md`](results/2026-10-26-cuteafd-vs-vllm/l/SUMMARY.md).

| Stage | Cap | Content | Requests | vLLM: finished / at cap / terminal loops | vLLM: check | vLLM: decode tok/s | CuteAFD: finished / at cap / terminal loops | CuteAFD: check | CuteAFD: decode tok/s |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 8K | prose | 8 | 0 / 8 / 0 | words/required 0.00 | 43.0 | 0 / 8 / 0 | words/required 0.00 | 40.7 |
| L1 | 8K | code | 8 | 0 / 8 / 0 | all tests pass 0/8 | 54.2 | 0 / 8 / 0 | all tests pass 0/8 | 54.9 |
| L1 | 8K | reasoning | 8 | 8 / 0 / 0 | correct 8/8 | 71.9 | 8 / 0 / 0 | correct 8/8 | 106.2 |
| L1 | 8K | json | 8 | 0 / 8 / 0 | valid 0/8 | 55.1 | 0 / 8 / 0 | valid 0/8 | 59.9 |
| L2 | 32K | prose | 8 | 1 / 7 / 0 | words/required 0.83 | 43.7 | 0 / 8 / 0 | words/required 0.48 | 40.1 |
| L2 | 32K | code | 8 | 0 / 8 / 0 | all tests pass 0/8 | 55.0 | 4 / 4 / 2 | all tests pass 4/8 | 59.3 |
| L2 | 32K | reasoning | 8 | 8 / 0 / 0 | correct 8/8 | 69.8 | 8 / 0 / 0 | correct 8/8 | 98.7 |
| L2 | 32K | json | 8 | 2 / 6 / 0 | valid 2/8 | 60.8 | 2 / 6 / 0 | valid 2/8 | 73.4 |
| L3 | 128K | prose | 8 | 8 / 0 / 0 | words/required 0.95 | 41.5 | 8 / 0 / 0 | words/required 1.05 | 39.3 |
| L3 | 128K | code | 8 | 8 / 0 / 6 | all tests pass 7/8 | 55.6 | 8 / 0 / 4 | all tests pass 7/8 | 58.2 |
| L3 | 128K | reasoning | 8 | 8 / 0 / 0 | correct 8/8 | 71.3 | 8 / 0 / 0 | correct 8/8 | 89.2 |
| L3 | 128K | json | 8 | 6 / 2 / 0 | valid 6/8 | 65.5 | 7 / 1 / 0 | valid 4/8 | 81.8 |
| L3s | 128K, 1 stream | prose | 1 | 1 / 0 / 0 | words/required 0.77 | 113.6 | 1 / 0 / 0 | words/required 0.78 | 126.5 |
| L3s | 128K, 1 stream | code | 1 | 1 / 0 / 1 | all tests pass 1/1 | 139.8 | 1 / 0 / 0 | all tests pass 1/1 | 165.4 |
| L3s | 128K, 1 stream | reasoning | 1 | 1 / 0 / 0 | correct 1/1 | 170.3 | 1 / 0 / 0 | correct 1/1 | 238.7 |
| L3s | 128K, 1 stream | json | 1 | 1 / 0 / 0 | valid 1/1 | 156.8 | 1 / 0 / 0 | valid 1/1 | 195.0 |

### K4: precision (top-20 measures)

Run [`results/2026-10-27-k4-vllm-cuteafd/`](results/2026-10-27-k4-vllm-cuteafd/) ([`METHOD.md`](results/2026-10-27-k4-vllm-cuteafd/METHOD.md)); brandonmusic's GLM-5.3-Flash-tr3-4bpw ("K4"; author Local Inference
Lab, Inc.; attribution in [`NOTICE.md`](NOTICE.md)). Its precision numbers are **top-20 measures** (KL20, KL_pb20):
never read them against the full-vocabulary or coarse KL above as the same quantity. CuteAFD against the per-row mean
of two vLLM launches.

| Measure (top-20) | Scored history, tokens (min / median / max) | vLLM (mean of 2 launches) | CuteAFD | CuteAFD − vLLM [95%] | vLLM launch 2 − launch 1 | Reading |
|---|---|---|---|---|---|---|
| P-A, teacher KL20 (25 windows × 2,048 tokens) | 1 / 1,024 / 2,047 | 0.0192 | 0.0219 | +0.0027 [+0.0012, +0.0047] | +0.0000 | differs |
| P-A, top-1 agreement with the teacher | 1 / 1,024 / 2,047 | 95.28% | 94.73% | -0.55 pts [-0.72, -0.37] | +0.00 pts | differs |
| P-A, NLL of the actual token | 1 / 1,024 / 2,047 | 1.0627 | 1.0653 | +0.0026 [+0.0005, +0.0048] | +0.0000 | differs |
| P-B, generated rows, KL_pb20 | 1,084 / 5,751.5 / 14,402 | 0.0305 | 0.0358 | +0.0053 [+0.0033, +0.0076] | -0.0002 | differs |
| P-B 0-2K | 1,084 / 1,735 / 2,361 | 0.0325 | 0.0343 | +0.0018 [-0.0007, +0.0049] | +0.0004 | not resolved |
| P-B 2-8K | 2,083 / 4,254 / 5,781 | 0.0219 | 0.0235 | +0.0015 [+0.0005, +0.0027] | +0.0004 | differs |
| P-B 8-16K | 10,284 / 12,069 / 14,402 | 0.0334 | 0.0424 | +0.0090 [+0.0062, +0.0122] | -0.0009 | differs |
| P-B block B (long code reading; the 8-16K windows) | 10,790 / 12,083 / 13,388 | 0.0372 | 0.0469 | +0.0098 [+0.0064, +0.0137] | -0.0012 | differs |
| P-B, generated rows, top-1 agreement | 1,084 / 5,751.5 / 14,402 | 94.93% | 94.59% | -0.34 pts [-0.62, -0.09] | +0.11 pts | differs |
| Q2, NLL on human-written text, 32K-128K (6 documents, t-interval) | 28,672 / 63,487.5 / 131,071 | 1.2434 | 1.2510 | +0.0076 [-0.0076, +0.0228] | +0.0003 | not resolved |

### K4: throughput

| Input × streams | Contents | Decode per stream, CuteAFD ÷ vLLM (readings) | Aggregate, CuteAFD ÷ vLLM (readings) | First token, s: vLLM / CuteAFD (median over contents) |
|---|---|---|---|---|
| 1K × 1 | code, json, prose, reasoning | 1.12-1.34x (4 faster) | 1.10-1.27x (4 faster) | 0.27 / 0.42 |
| 1K × 4 | code, json, prose, reasoning | 1.15-1.23x (4 faster) | 1.06-1.12x (1 faster, 3 level) | 0.87 / 1.26 |
| 8K × 1 | code, json, prose, reasoning | 1.05-1.38x (3 faster, 1 level) | 1.10-1.28x (4 faster) | 2.20 / 1.84 |
| 8K × 4 | code, json, prose, reasoning | 1.11-1.15x (4 faster) | 1.09-1.18x (4 faster) | 5.72 / 5.30 |
| 32K × 1 | code, prose | 1.12-1.19x (2 faster) | 1.17-1.21x (2 faster) | 9.05 / 7.38 |
| 32K × 4 | code, prose | 1.54-1.59x (2 faster) | 1.12x (2 faster) | 24.02 / 27.56 |
| 128K × 1 | code, prose | 1.06-1.19x (1 faster, 1 level) | 1.18-1.20x (2 faster) | 36.36 / 30.08 |

Detail, K4 against K3.25 under the same top-20 definition, startup, Block L and the follow-ups:
[`results/2026-10-27-k4-vllm-cuteafd/README.md`](results/2026-10-27-k4-vllm-cuteafd/README.md).

<!-- results:end -->

## Running it: observations in detail

Each item is the behaviour as measured or as read in source, with how it is known. None is a claim about output quality.

### Capacity

|  | vLLM fork | CuteAFD |
|---|---|---|
| K3.25, KV cache at startup | 4,707,515 tokens | 4,726,784 tokens |
| K4, KV cache at startup | 1,377,179 tokens | 447,488 tokens (scoring launch 451,584) |
| Requests at once | 16 (`max-num-seqs`) | 16 (`CONCURRENCY` default) |

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

| Launch | To /v1/models | To ready | Capacity at startup |
|---|---|---|---|
| vLLM cold | 249 s | 307 s | 1,377,179 tokens, 16 requests |
| vLLM warm | 200 s | 257 s | 1,377,179 tokens, 16 requests |
| CuteAFD cold | 74 s | 76 s | 447,488 tokens, 16 requests |
| CuteAFD warm | 79 s | 86 s | 447,488 tokens, 16 requests |
| CuteAFD scoring launch | 88 s | 90 s | 451,584 tokens, 16 requests |

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
- **13:03-13:34.** Needle pilot on both engines with K3.25, prompts of 256K, 512K and 1M tokens, one request each (exploratory; [`results/2026-10-27-long-context-pilot`](results/2026-10-27-long-context-pilot/)).

2026-10-27 (evening), K4 checkpoint ([`results/2026-10-27-k4-vllm-cuteafd`](results/2026-10-27-k4-vllm-cuteafd/); no separate review of this run):

- **17:34-17:51.** K4 startup and smoke checks on both engines (one cold and one warm start each, and CuteAFD's scoring
  launch).
- **17:58.** K4 protocol frozen, before any comparison request (`FROZEN.json` sha256 `368e1700…`;
  [`METHOD.md`](results/2026-10-27-k4-vllm-cuteafd/METHOD.md)).
- **18:03-19:48.** K4 Block Q: vLLM launch 1, CuteAFD's scoring launch (every panel twice, byte-identical), vLLM launch 2.
- **19:54-23:25.** K4 Block T: vLLM 19:54-20:47 and its drift subset 20:47-20:58; CuteAFD 22:12-22:57 and
  its drift subset 22:57-23:07; a final vLLM drift subset 23:13-23:25. 264 measured requests per engine, 0 errors.
- **Before 23:31.** Follow-up F1-K4 (W8A16 prefill) declared, after the Block Q results.
- **23:31-00:32.** F1-K4: CuteAFD scoring launch with W8A16 prefill; speed on serving launches 23:50-00:00 (as shipped),
  00:02-00:12 (W8A16), 00:14-00:24 (as shipped).

2026-10-28:

- **From 00:38.** K4 Block L on both engines, vLLM first; analysed afterwards with the frozen K3.25 analyser and the
  review's loop rule.
- **To 12:47.** Follow-up F1-K4b (CuteAFD's other FP8 switches) declared before any of its requests; planner dry runs
  (BF16 KDA projections do not fit a serving launch with K4); the amax and best scale rules captured.
- **13:05-13:10.** F1-K4b amendments B1 and B2: drafter-off scoring launches for the BF16 head and KDA arms, gated by a
  control whose rows were byte-identical to as shipped on all 157,671 scored rows.
- **14:45-15:19.** K4c (W8A16 + amax), declared before any of its requests: speed on serving
  launches 14:45-14:55 (as shipped), 14:57-15:07, 15:09-15:19 (as shipped).
- **17:13-17:47.** K4d (W8A16 + best), declared before any of its requests: speed
  17:13-17:23, 17:25-17:35, 17:37-17:47.


## Other runs

Not part of the comparison above. Exploratory runs and checks are labelled as such in their folders and never share a
table with the measured results.

| Run | Kind | What it is |
|---|---|---|
| [`2026-10-26-cuteafd-setup-checks`](results/2026-10-26-cuteafd-setup-checks/) | check | Core-FP8 expert bytes and FP8 projections checked against K3.25-v1; CuteAFD source audit |
| [`2026-10-26-e1-router-route`](results/2026-10-26-e1-router-route/) | exploratory | CuteAFD router logits across its 160/161-row route switch (one GPU, one kernel) |
| [`2026-10-27-long-context-pilot`](results/2026-10-27-long-context-pilot/) | exploratory | Needle retrieval at 256K, 512K and 1M tokens, both engines, K3.25 (one request per prompt and engine) |
| [`2026-10-27-vllm-startup-cache`](results/2026-10-27-vllm-startup-cache/) | measurement | vLLM v0.9.2 startup time with and without persisted JIT caches, and CuteAFD's for comparison |

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
