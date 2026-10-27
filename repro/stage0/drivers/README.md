# Stage 0 drivers: Blocks T and L (CuteAFD v3.0.1 vs vLLM v0.9.2)

Written 2026-10-26 in Stage 0 (CPU only). Nothing here has been run against either engine. The drivers were
tested end to end against a local mock server on another port. Prompts, rules and checkers are in
`../prompts/` (see its README). Hashes are in `../prompts/MANIFEST.json`.

| File | What it does | Needs |
|---|---|---|
| `client.py` | Shared streaming client: one `POST /v1/chat/completions` per request, Bearer key, nonce, timings, usage | stdlib |
| `block_t.py` | Block T throughput grid | stdlib |
| `block_l.py` | Block L long-output stages with the error gate | stdlib |
| `analyze_l.py` | Block L analysis: stop vs cap, loop onset and period, decode rate by position, correctness | stdlib on the host; docker for its CPU container and the pytest sandbox |

All three entry points take `--base-url`, `--label` and `--api-key-file` (CuteAFD with `API_KEY_FILE`
set needs a key on every `/v1/*` request). Receipts never contain the key. Each driver records its own SHA256,
the client's SHA256 and the prompt index's SHA256, and refuses to start if any prompt file differs from its
index hash.

Sampling for both blocks is the checkpoint author's `generation_config.json`: temperature 1.0, top_p 0.95
(`--temperature` and `--top-p` override). The protocol
does not fix sampling, so this choice needs the maintainer's sign-off before freezing.

## block_t.py

```bash
python3 block_t.py --base-url http://127.0.0.1:8001 --label C1-r1 --api-key-file KEYFILE \
    --out <run>/C1-r1-block-t.json
python3 block_t.py --label x --out /dev/null --dry-run      # plan and request counts only
```

- **Grid.**
  - Inputs 1K/8K/32K/128K, concurrency 1/4/8/16, 3 replicates, `max_tokens` 1,024.
  - Prose and code at every input length; reasoning (thinking on) and JSON at 1K and 8K only.
  - 128K at 8 and 16 streams is skipped, as declared in the protocol.
  - `--lengths/--levels/--contents/--reps` select a subset, for example the CVC repeat.
- **Batches.**
  - At 1 stream, a replicate is the 4 prompts sent one after another.
  - At c ≥ 4, a replicate is one barrier-released batch of c requests, with stream s using prompt s mod 4.
  - So every prompt appears equally often in every cell.
  - Order: replicate (outermost), then input length, content, concurrency. Replicates are spread over the
    run rather than adjacent.
- **Extra cells.**
  - One warm-up batch first (1K prose, 4 streams), flagged.
  - One cached cell last (8K prose prompt 0, the same nonce 4 times: 1 primer and 3 measured).
- **Counts per engine run.** 1,008 measured requests, 4 warm-up and 4 cached, 1,016 in total. That is
  16,158,594 prompt tokens, about 6.3M of them in the 32K cells.
- **Per request.**
  - Seed and nonce, TTFT, and `usage` (prompt, completion and cached tokens).
  - Prefill tok/s = prompt_tokens / TTFT. At c > 1 this includes queueing behind other prefills.
  - Decode tok/s = (completion − 1) / (last − first token).
  - Finish reason and error.
  - Content and reasoning character counts, and whether content contained `</think>`.
- **Per replicate.**
  - Medians of the per-request numbers.
  - Aggregate tok/s, defined as in `throughput.py`.
  - Aggregate prefill tok/s.
- **nvidia-smi.** A read-only `nvidia-smi` snapshot is taken before and after. It misses graphics clients, so also check the full `nvidia-smi` output.

## block_l.py

```bash
python3 block_l.py --base-url http://127.0.0.1:8001 --label C1 --api-key-file KEYFILE \
    --out <run>/C1-block-l.json --stages L1
# check engine logs and memory, then:  --stages L2   then  --stages L3 L3s
```

- **Stages.**
  - L1, L2 and L3 have caps of 8,192, 32,768 and 131,072 tokens.
  - Each has 32 requests: 4 contents × 4 prompts × 2 seeds, queued through 8 worker threads (the semaphore).
  - L3s is the 1-stream subset: prompt 0 of each content, one at a time, at the L3 cap.
  - In total, 100 requests per engine.
- **Gate.**
  - Any HTTP error stops the stage. Queued requests are not started and are listed in `not_started`.
  - In-flight requests finish, no later stage runs, and the exit status is 2.
  - The protocol's other gates (clean logs, no memory warnings) are the maintainer's to check, so run one stage
    per invocation. A repeated `--out` overwrites the receipt, so give each stage its own file. Texts go to
    `<out stem>-texts/`.
- **Per request.**
  - Seed, nonce, finish reason, completion tokens, reasoning and content character counts, TTFT and decode
    tok/s.
  - Approximate decode tok/s per 2,048-token bucket.
  - Error.
  - The full text, saved gzip-compressed with its SHA256: reasoning, content, and chunk timestamps, sizes and
    kinds.

## analyze_l.py

```bash
python3 analyze_l.py C1-block-l-L1.json V1-block-l-L1.json --out <runs>/.../analysis/L1.json
```

**Containers.**
- It re-runs itself with `--inner` in a `--network none` container of the CuteAFD image (`392db7c0`, CPU
  only, no GPU flag). The receipt directory is mounted read-only.
- It then runs the code checker. That runs pytest in a separate `--network none`, 2-CPU, 2 GB, 256-pid
  container per reply, with a 300 s limit.

**Methods ported from the long-reply investigation**
(`<runs>/investigations/2026-10-glm53-completion/long-reply/discovery/scripts/`):
- **Onset** (`trajectory.py`):
  - R50 is the share of positions in a 4,096-token window whose 50-gram occurred earlier.
  - Onset is the start of the final run with R50 ≥ 0.5. It is reported only for a terminal loop, with
    sensitivity at 0.3 and 0.7.
  - Replies under 4,146 tokens are not assessed and say so.
- **Period** (`periods.py`):
  - The lag-match screen: FFT, 3 random phases, the top 40 lags computed exactly.
  - Exact period = the smallest lag with m ≥ 0.8, computed on the post-onset region, plus the longest
    repeated substring.
- **One addition, in its own field.** `exact_period_m08_divisor_refined` also tests the divisors of the
  period. On a short exact loop every multiple ties at m = 1.0, and the top-40 screen can miss the period
  itself. The mock's 7-token loop came back as 28 from the ported rule.

**Other outputs.**
- **Tokens.** The saved reasoning and content are re-tokenized in generation order. Drift against
  `completion_tokens` is reported.
- **Decode rate by position.** Uses exact token positions.
- **Correctness:**
  - math: last `\boxed{}` in the final text, normalized, compared with the MATH-500 answer;
  - JSON: schema, count, ids and unique skus;
  - code: hidden pytest suite;
  - prose: words over required words, reported as a ratio, not pass/fail.
- **Pairing.** With two or more receipts, requests are paired by (stage, content, prompt, rep).

## Thinking-off differs between the engines (read before running T or L)

Stated from source; not measured, because no requests were allowed in Stage 0.

- **The template.** The checkpoint's chat template is byte-identical to vLLM's
  `/opt/glm53/templates/glm53-zai-a5b45eb.jinja`. It has no thinking switch: it always ends the prompt with
  `<|assistant|><think>`.
- **CuteAFD** renders `enable_thinking: false` as an empty `<think></think>`
  (`cuteafd-api/src/openai/chat/glm5/prompt.rs`, `GlmThinkingOff::Empty`). That is one more prompt token:
  148 versus 147 in the earlier run.
- **vLLM** renders the same prompt for on and off. Its `glm47` reasoning parser (`--reasoning-parser glm45`)
  starts in CONTENT state when thinking is off, so the model's reasoning is streamed as `content`, followed
  by `</think>` (not a special token) and the answer.

**What this means for the comparison.**
- In thinking-off cells, vLLM very likely generates reasoning and CuteAFD does not. Text, length and
  acceptance can then differ for reasons other than the engine's arithmetic.
- The drivers record `content_has_think_close` per request.
- The checkers score only the text after the last `</think>`.
- This is a protocol decision, not a driver fix. For example: run thinking on for every content; or accept
  the difference and report it per cell; or render thinking-off identically on both engines. The last option
  would be a local delta that the protocol has to declare.
