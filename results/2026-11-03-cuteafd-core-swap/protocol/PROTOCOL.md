# CuteAFD core swap: is K4-Core-K6's longer thinking on CuteAFD the core or the experts?

Written 2026-11-03 before any GPU use; frozen in FROZEN.json (with every script, config and input it names) before the
first request. Decisions before the freeze: a derived checkpoint served by the unmodified launcher; 2 concurrent in step 1 (as
Block L). [V] verified, [I] inferred.

## Why
- Block L on CuteAFD v4.0.0 (2026-10-30/31, 130K stage, 2 runs, same seeds per checkpoint): K4-Core-K6 thought longer
  than K4 on 10 of 11 prompts. Seed-paired reasoning-token ratio K4-Core-K6 / K4: code 1.43 (prompt-clustered
  [1.20, 1.59]), prose 1.19 [1.06, 1.39], JSON 1.07 [0.99, 1.21] [V; post hoc read of a run not designed for it,
  4 prompts per content].
- K4 and K4-Core-K6 differ in the core (BF16 -> FP8 at load vs native 6-bit) AND in the routed experts (different
  quantization runs, same size). The vLLM swap (2026-11-02-thinking-length) tested only the core, on another engine,
  with launch noise as large as the effect, and found nothing measurable.

## Arms (CuteAFD v4.0.0, coordinator index sha256:e257bc61..., 2x RTX PRO 6000, local experts, no Sparks)
| Arm | Checkpoint | Core at runtime | Experts |
|---|---|---|---|
| C-K6 | wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6 @ 5d3fffe1 | native 6-bit EXL3 (K6 head) | K4-Core-K6's |
| C-K6x | derived/GLM-5.3-Flash-EXL3-K4-Core-K6-BF16core @ 049c0180 | BF16 originals -> FP8 at load, exactly as K4 | K4-Core-K6's |
| C-K4 | brandonmusic/GLM-5.3-Flash-tr3-4bpw @ a5fee929 | BF16 -> FP8 at load | K4's |

- C-K6x core bytes = K4's core bytes, all 316 tensors (prep/core-hash.json) [V]. Derived checkpoint build and checks:
  prep/build_derived.py, prep/derived-manifest.json [V].
- CuteAFD's planner (dry run, `--network none`) gives C-K6x the same plan as C-K4 (FP8 KDA row-K128, FP8 block MLA and
  shared experts, FP8 head, W8A8 prefill, pool 1,111,040 tokens) except the MTP layer, which is not run (DFlash2 drafter)
  [V logs/dryrun-*.log].
- Contrasts: **core** = C-K6 vs C-K6x (same experts); **experts** = C-K6x vs C-K4 (same core bytes and arithmetic);
  **total** = C-K6 vs C-K4 (repeats Block L's comparison).
- Caveat: "BF16 core" on CuteAFD means FP8 from BF16 (no BF16 path for MLA and FFN projections in v4.0.0). That is how
  CuteAFD serves K4, so it is the comparison behind the observation.

## Step 1: free generation (the observation itself)
- Driver: the v4 run's frozen Block L driver (drivers/block_l3.py), stage L3: cap 130,048, 2 concurrent, thinking on,
  same prompts and salt as Block L, contents **code and prose** (JSON not repeated: smallest observed difference, and
  its p3 prompt is bounded by the answer cap).
- Seeds: new, distinct per request, the same across arms (rep offsets +20 and +30: no seed shared with Block L r1/r2).
  Per arm: 2 runs x 4 prompts x 2 reps x 2 contents = 32 requests.
- Order: C-K6x, C-K6, C-K4 (one launch each; serving configs differing only in MODEL_ID/REVISION; both seed sets per
  launch). Runs after step 2.
- Primary measure: reasoning tokens per finished reply, by re-tokenization of the saved texts with the frozen K3.25 Block
  L analyzer (stage0/drivers/analyze_l.py, CPU-only no-network containers), as the v4 run. Capped replies are counted
  and listed, not imputed; a loop is a capped reply with a terminal repetition onset (finished code replies also show an
  onset because the answer repeats code from the reasoning; reported separately, descriptive).
- Reading (frozen at freeze): per contrast, mean of seed-paired log ratios; 95% bootstrap over prompts (the question as
  the unit, 8 prompts) as primary, over pairs as secondary; reported as a ratio. A difference is detected when the
  prompt-level interval excludes 1. Direction and size are reported first; "not detected" is not "no effect".
- Resolution [I]: within-prompt sd of log reasoning tokens 0.20-0.29 in Block L; 32 pairs per contrast give ~80% power
  for about 1.16-1.2x on the pair-level analysis; the 8-prompt analysis is coarser.

## Step 2: fixed traces (the stop decision, deterministic); runs first
- Traces: the 93 traces of the vLLM investigation (77 finished, 16 not; up to 95,362 tokens; 3.1M tokens per arm),
  token ids unchanged, so CuteAFD and vLLM results pair trace by trace.
- Endpoint: POST /v1/bench/probe on the scoring configs (ENABLE_BENCH, FULL_PREFILL_LOGITS, no prefix cache),
  `prompt_ids`, `cold`, `no_speculation`, `score_path=prefill`, `score_positions` = the rows the vLLM captures stored
  (every 64th + the last 512 before each close), `top_k` 64, `want` token 154842 (`</think>`) at every scored row.
- Arms, in order: C-K6, C-K6x, C-K4, then a second C-K6 launch (C-K6r2): cross-launch bit-identity checked per row by
  the logits hash (drivers/s2_identity.py). The bench API key is generated per launch (umask 077) and shredded after.
- Driver: drivers/probe_traces.py writes each trace as a plugin-0.3 reduced dump, so the thinking-length run's
  analysis/score_stop.py scores CuteAFD unchanged: base C-K6 (ref C-K6x: core and total contrasts, C-K6r2 as the launch
  check) and base C-K6x (ref C-K4: experts). CPU-tested against a stub of the probe reply (dryrun/stub_probe.py).
- Measures (as G2, analysis/score_stop.py conventions): log p(</think>) at the close, mean p over the 512 rows before it,
  </think> top-1 at the close, max p on unfinished traces, top-64 KL between arms, chosen-token log-prob.
- Reading: per contrast, paired over traces, 2,000-replicate bootstrap; a difference is detected when the interval
  excludes 0 and, if the second launch is not bit-identical, exceeds its difference (as Amendment 1).
- A probe that fails (e.g. a 95K-token trace over a timeout) stops that arm's run at the failing trace; traces already
  scored are kept. Any change of handling is an amendment recorded before any score is read.


## Run
`chain-cs.sh` under systemd: step 2, step 1, analysis; vLLM
K3.25 serving restored at the end and on every exit path. Dry run: dryrun/chain-cs.dry.log. Analysis tested on Block L's
own records (reproduces the post hoc ratios above).

## Scope
One engine (CuteAFD v4.0.0), one machine, code and prose prompts from Block L, the 93 fixed traces. Routed experts are
compared as two whole quantizations, not tensor by tensor.
