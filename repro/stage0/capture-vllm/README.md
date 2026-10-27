# vLLM v0.9.2 capture path: full-vocabulary log-softmax rows at scored positions

Stage 0 (CPU only), 2026-10-26. Nothing here has run on a GPU. No container was started,
stopped or exec'd into. The only containers run were CPU-only
`docker run --rm --network none` of the v0.9.2 image to test the code.
`<kld>/` is unchanged; the old plugin was read and copied from it, not edited.

Target: tpurtell vLLM v0.9.2 image `sha256:ea0430aa772e…`, stack `<vllm-stack>`,
recipe `glm53-flash-exl3-k3.25@tpurtell+v0.9.2`, served as the recipe has it
(DFlash2 K3, prefix caching with mamba `align`, max-num-seqs 16).

## Files

| Path | What |
|---|---|
| `plugin/glm53_capture_plugin/__init__.py` | vLLM general plugin: the hook (V2 `PromptLogprobsWorker.compute_prompt_logprobs`) |
| `plugin/glm53_capture_plugin/core.py` | numpy-only core shared with the driver: registry, token hash, row arithmetic, file layout |
| `plugin/glm53_capture-0.2.dist-info/` | entry point `glm53_capture` (group `vllm.general_plugins`) |
| `start-v092-capture.sh` | launch wrapper; `DRY_RUN=1` renders the full `docker run` with a stub and starts nothing |
| `capture.py` | `register` / `status` / `capture` / `verify` |
| `registry/pa/*.json`, `registry/pb/*.json` | 25 P-A and 64 P-B windows, already registered and checked |
| `tests/` | CPU tests and their outputs (`*.out`) |
| `launch-dryrun.txt`, `launch-compare.txt` | rendered launch, and its diff against the running served container |
| `plugin-load-check.txt` | the image's vLLM loads the plugin through its entry point |

## The window sets

Row `r` is the log-softmax after `tokens[0..r]` inclusive. It predicts `tokens[r+1]`. Valid rows are `0..n-2`.

| Set | Windows | Tokens | Rows dumped | Rule | Dump size per pass |
|---|---|---|---|---|---|
| `pa` | 25 x 2,048 | 51,200 | 51,175 | all rows 0..2046 | 31.7 GB |
| `pb` | 64, 513-14,403 | 342,647 | 32,768 | rows `score_from-1 .. n-2` (last 512) | 20.3 GB |
| `q2` | 18 expected (3 docs x 2 types x 3 lengths) | ~1.34 M | 73,728 | last 4,096 rows | 45.7 GB (+7.6 GB for the 3 repeat docs) |

Each row is 154,880 x 4 B = 619,520 B. Two passes of P-A + P-B (the noise floor) plus Q2 and its
repeats come to about 157 GB. `<data>` has 1.8 TB free.

**P-B convention, checked against his reference files.** I read all 64 reference safetensors.
For every window:
- `positions == score_from .. n-1`;
- `next_token_ids == tokens[positions]`;
- `roles` matches `windows.json` (ctx=0, gen=1; 15,104 gen rows);
- `n - score_from == 512`.

His position `p` (predicts `tokens[p]` from `tokens[:p]`) is therefore our row `p-1`. The registered
rows are `{start: score_from-1, stop: n-1}`. The `legacy` window has `score_from` 1, so its rows are
0..511. Output: `tests/check_registry.out`.

**P-A.** Tokens come from `<runs>/kld/panel-final/final-*.tokens.npy`. Each `.npy` file's SHA-256
equals the dataset manifest's `token_ids_sha256` (that hash is of the `.npy` file, not of the ids).
The plugin's `tokens_sha256` is SHA-256 of the int32 little-endian ids, which is the old plugin's
`token_ids_sha256_raw`.

## What changed versus `glm53_kld_plugin`, and why

| | Old (`<kld>/plugin`) | New | Why |
|---|---|---|---|
| Row placement | Wrote logits from **batch row 0** | Uses the request's own `query_start_loc_np[i] .. [i+1]`, minus the last row on the final chunk, exactly as `prompt_logprob.py:91-108` does. This range is intersected with each 1,024-row `logits_fn` slice of `hidden_states[:num_tokens]`. Batch row `qs` is window row `num_computed_prefill_tokens` | The V2 runner sorts batches decode → short extend → prefill (`model_runner.py:2112-2122`), so any decode traffic shifted the old dump. Reproduced on CPU: the old plugin's row 0 is a decode request's logits (`old_plugin_row_offset` test) |
| Windows per batch | Exactly 1, else error | Any number; the same window twice in flight is refused | Correctness no longer depends on it |
| Chunked prefill | Assumed one step (2,048 tokens, speculation off) | Any number of steps. Continuity is checked (`chunk_start == previous end`). Restarts at 0 are handled. A request aborted mid-prefill is superseded by the next request for that window | DFlash runs 2,045 + 3 for a 2,048 window; P-B and Q2 span 1-63 steps |
| Lengths and rows | 2,048 tokens, all 2,047 rows, ids `final-0000..0024` | Any length; any strictly increasing row set; **only registered rows are copied** | P-B: all rows would be 212 GB, scored rows only are 20.3 GB |
| Window source | 25 hard-coded `.npy` files | A directory of JSON `{window_id, tokens, rows}`. It is loaded lazily in the worker and reloaded when its file listing changes; `registry-status.json` reports what was loaded | Generic. Q2 can be registered without a restart |
| Stored values | Raw logits as F32, teacher layout (data at byte 400) | `logprobs` F32 `[n_rows, 154880]` = float64 log-softmax on the host of the native BF16 row, cast to F32. Also `rows` I32 and `tokens_sha256` U8[32] (also in metadata). Named `<set>/<window_id>.safetensors` | As specified. The log-softmax is idempotent, so a KL scorer that log-softmaxes its input gets the same numbers |
| Logs | Receipt only | Receipt, plus `<id>.steps.jsonl` and a global `steps.jsonl` with one line per step: step, chunk start/len, batch rows, batch size, num_tokens, every other request (n, computed, prefill?, drafts), logits_fn calls, rows written | Chunk split and co-batched traffic are part of what is measured |
| Alignment check | none | In-server: for **every dumped row**, `dump[tokens[r+1]]` is compared with vLLM's own prompt logprob for that row, and vLLM's token id is checked against `tokens[r+1]`. The receipt has `chosen_check.max_abs_diff`. The driver adds `--verify-chosen N` against the HTTP API | Catches any off-by-one or row shift |
| Hooks | V2 hook and legacy V1 hook | V2 hook only; if it cannot be installed, it logs and stays inert | The server logs "Using V2 Model Runner" |
| Prefix-cache guard | First chunk must start at 0 | Same | prompt_logprobs requests skip reading the cache (`sampling_params.py:529-533`), but the guard stays |
| Launch | Speculation off, prefix caching off, `PYTHONPATH` replaced, v0.8.0 stack default | Served configuration unchanged; `PYTHONPATH` prepended; `IMAGE` pinned explicitly | Score the engine as served (protocol principle 4) |

GPU memory: the plugin allocates nothing on the GPU. It copies 256-row views of the logits slice that
vLLM already holds directly to the host. Host cost per row is about 0.84 ms for the log-softmax
(8 torch threads, measured in the image) plus about 0.8 ms to write to the page cache. That cost
lands inside the engine step. It is harmless for an idle serial capture, but do not measure anything
else while capture mode is active. The worker's torch thread count is set to 8 for each slice and
restored afterwards (`GLM53_CAP_HOST_THREADS`).

## Launch: differences from the normal start

The rendered launch (`DRY_RUN=1`) was compared with the running served container (`docker inspect`,
read-only), using `tests/compare_launch.py`. The output is in `launch-compare.txt`:

- **Identical:** image digest, every serve argument, container name, `127.0.0.1:8001:8001`, restart
  policy, GPUs, IPC/shm, and all served mounts and env.
- **Added:** three mounts (`plugin:/kld-plugin:ro`, `registry:/kld-registry:ro`, `OUT_DIR:/kld-out`).
- **Changed env:** `VLLM_PLUGINS` (+`,glm53_capture`) and `PYTHONPATH` (`/kld-plugin:` prepended to
  the image default).
- **New env:** `GLM53_CAP_ENABLE=1`, `GLM53_CAP_REGISTRY=/kld-registry`, `GLM53_CAP_OUT=/kld-out/staging`.

How the wrapper builds and guards the launch:
- **IMAGE.** It sources the recipe `env.sh`, then `export IMAGE=sha256:ea0430aa…`, then the stack's
  `local-env.sh`. It refuses to start if IMAGE is not the v0.9.2 digest afterwards. Tested with a
  caller that had exported the v0.9.0 digest: the result was still v0.9.2.
- **start.sh.** It runs a temporary copy of the stack's `start.sh`, pinned by sha256 `e1196cbc…`. The
  copy has exactly one changed line (`SCRIPT_DIR` pointing back at the stack) and three added mount
  lines. The env goes through start.sh's own `DEBUG_ENV`.
- **Overrides.** It refuses caller overrides of speculation, prefix caching, max-num-seqs, cudagraph
  size, KV, model, container name, port, `DEBUG_ENV` and `EXTRA_SERVE_ARGS`.

The plugin loads through vLLM's entry-point mechanism in the image (`plugin-load-check.txt`), and
b12x still imports with the prepended `PYTHONPATH`.

## Commands for the GPU stage

Use the venv Python on the host; system `python3` has no numpy.
`PY=<venv>/bin/python; cd <run>/stage0/capture-vllm`

```bash
# 0. Before stopping anything (CPU only). Register Q2 once its token files exist.
#    A bare JSON id list takes window_id from the file name; an object may carry its own rows.
$PY capture.py register --set q2 --json '<run>/stage0/prompts/q2/*.json' --last-rows 4096
$PY capture.py status
DRY_RUN=1 ./start-v092-capture.sh > launch-dryrun.txt 2>&1 && python3 tests/compare_launch.py launch-dryrun.txt
#    The GPUs must be free of anything but the served vLLM: check the full nvidia-smi output.

# 1. Stop the normal server.
<vllm-stack>/stop.sh

# 2. Start capture mode (about 12 min to ready).
OUT_DIR=<run>/vllm-v092-dumps ./start-v092-capture.sh
until docker logs glm53-flash-exl3-b12x-vllm 2>&1 | grep -q "startup warmup complete; container is ready"; do sleep 10; done
docker logs glm53-flash-exl3-b12x-vllm 2>&1 | grep glm53_capture     # must show "patched PromptLogprobsWorker..."

# 3. Capture. Each window goes serially, waiting for /metrics to show 0 running and 0 waiting.
#    First a 4-token probe makes the plugin load the registry; the driver then confirms the
#    plugin's registry signature matches. P-A first: its 25 windows also validate the path.
$PY capture.py capture --set pa --run-tag v1-r1 --verify-chosen 8
$PY capture.py capture --set pb --run-tag v1-r1 --verify-chosen 8
$PY capture.py capture --set q2 --run-tag v1-r1 --verify-chosen 8
#    Within-arm repeats (noise floor; Q2 one document per length):
$PY capture.py capture --set pa --run-tag v1-r2
$PY capture.py capture --set pb --run-tag v1-r2
$PY capture.py capture --set q2 --run-tag v1-r2 --only <32k-id>,<64k-id>,<128k-id>
$PY capture.py verify --set pa --run-tag v1-r1     # offline re-check, any time

# 4. Stop capture mode and restore the served recipe (about 12 min to ready).
<vllm-stack>/stop.sh
cd <vllm-stack> && source <recipes>/glm53-flash-exl3-k3.25@tpurtell+v0.9.2/env.sh && ./local-start.sh
```

Outputs:
- `OUT_DIR/runs/<tag>/<set>/<window_id>.safetensors`, plus `.receipt.json`, `.steps.jsonl` and
  `capture-manifest.json` (per window: seed, timing, steps, chunk lengths, steps shared with other
  requests, both chosen-token checks, usage).
- The plugin writes into `OUT_DIR/staging/`. After verifying a window, the driver moves its files
  out. Stale staging files stop the run.
- A rerun with the same tag skips windows that are already done.

A window fails, and the driver stops with the files left in staging, if any of these hold:
- the receipt is missing or incomplete, or a plugin error file exists;
- sha or row count differs from the registry;
- the in-server chosen-token check is above 1e-3 or the token ids disagree;
- `usage.prompt_tokens` is not n, or any prompt tokens were served from the prefix cache;
- the file's shape, rows or sha do not match;
- a sampled row's logsumexp is not within 1e-4 of 0;
- with `--verify-chosen`, the dump differs from the API by more than 1e-3.

## Time estimate

These are estimates [I]. The capture writes per-window timings, so the first P-A window gives real
numbers.

| Item | Estimate | Basis |
|---|---|---|
| Stop, then start in capture mode | ~12.5 min | recipe `ready_seconds` 738 with speculation on |
| P-A request time | ~2-2.5 min | v0.8.0 capture 80 s (already included the 30 GB F32 write), plus host log-softmax 51,175 x 0.84 ms ≈ 43 s; DFlash adds a 3-token second step per window |
| P-B | ~3-6 min | 342,647 prompt tokens; prefill rate at 2-14K is unmeasured (`prefill_tok_s` n/a); 20.3 GB of writes; 28 s of log-softmax |
| Q2 | ~10-15 min | ~1.34 M tokens at an assumed 2-4K tok/s at 32-128K (sparse attention, unmeasured); 45.7 GB of writes; 62 s of log-softmax |
| Repeats (P-A, P-B, 3 Q2 docs) | ~8-12 min | same rates |
| Stop, then restore the normal server | ~12.5 min | |
| **Total wall** | **~1-1.2 h, both GPUs** | consistent with the protocol's Q + Q2 line (0.5-0.6 h per engine excluding switches) |

## Test results (CPU only, in image `ea0430aa…`, `--network none`)

The tests run the image's real `PromptLogprobsWorker.compute_prompt_logprobs` (file sha256
`4cf22d39…`, identical to the discovery scratch copy). Only its two Triton helpers are replaced by
CPU torch versions written from the kernels' source. Synthetic BF16 logits are a deterministic
function of (request, position), so every expected row is known independently of batch layout. Every
test also checks that the hooked method's return value is bit-identical to the unhooked method's.

`tests/test_capture_cpu.py`, output in `tests/test_capture_cpu.out`; ALL PASS:

| Test | Shows |
|---|---|
| core_units | row arithmetic, row specs, hash |
| decode_first | 3 decode/verify requests (K3, 4 rows each) ahead of the window, so the window sits at batch rows 12..1511; 1,499 rows bit-exact; in-server chosen check max diff 1.9e-6 |
| multi_prefill | 2 registered windows, 1 unregistered prompt-logprobs request and 1 decode in one batch, ordered `d0, U, A, B`. B spans the 1,024-row `logits_fn` boundary; both windows exact; nothing written for U |
| chunked_across_steps | a 4,300-token window over 3 steps (2,045 / 2,045 / 210) with changing decode traffic (batch offsets 0, 8, 13). The last 512 rows straddle a chunk boundary (303 + 209 rows); exact |
| full_vocab | 154,880 wide, 600 rows behind 2 decodes, 256-row copy slices; exact; the `safetensors` library reads it |
| guards | 7 cases: plain steps never touch the filesystem; non-zero first chunk refused; registry reload; stale staging file refused; same window twice in a batch refused; bad registry file reported; aborted request superseded |
| rank1_inert | TP rank 1 writes nothing |
| old_plugin_row_offset | the old plugin on a decode-first batch: its dump row 0 equals decode request d0's logits (row-offset issue reproduced) |

`tests/test_driver_e2e.py`, output in `tests/test_driver_e2e.out`; ALL PASS. `capture.py` runs
against a fake OpenAI server in the container that runs the same real worker with the plugin armed.
Every step carries a decode request with 3 drafts, and chunks are 2,041 tokens.
- Generic registration of a bare id list (`--last-rows`) and of an object with an explicit row list;
  duplicate tokens refused.
- Capture with `--verify-chosen 6`: the API value equals the dump within 1e-6, and the rows equal the
  independent expectation.
- Resume skips finished windows; a new run tag recaptures; `verify` passes, and flags a row corrupted
  by +0.5 nats.

`tests/check_registry.py` (host), output in `tests/check_registry.out`: P-B 64/64 and P-A 25/25 match
the source data.

## Risks and open items

1. **Not yet run on a GPU.** By source, prompt_logprobs works with DFlash2 on (discovery §4) [I]. The
   first P-A window settles it, along with the logits dtype (recorded in each receipt, BF16 expected)
   and memory headroom. The plugin adds no GPU allocation; vLLM's own 1,024-row logits slice is
   needed with or without it.
2. **The engine step stalls while rows are written:** about 1.5-3.5 s per 2,045-row step. Harmless
   idle and serial: rank 1 waits in its next collective, far below any timeout. Do not run Block T
   or Block L in capture mode; restore the normal server first.
3. **Chunk boundaries are the served engine's.** DFlash reserves 3 slots, so chunks are 2,045 tokens.
   With prefix caching in `align` mode, windows over 4,352 tokens also stop at multiples of 4,352.
   Both are logged per step, not forced. They differ from CuteAFD's shapes, as the protocol records.
4. **Load condition.** The offset fix makes correct capture under concurrent load possible, but the
   driver requires an idle server, matching the protocol ("Load condition: not run").
5. **The scorer reads the old layout.** `kld_score.py` expects raw logits at offset 400 in
   `window-XXXX.safetensors`. It needs a reader for `logprobs` via the safetensors header. That is
   Stage 0 item 2 and not done here. The arithmetic carries over, because log-softmax is idempotent.
6. **Root-owned outputs.** The container runs as root, so dump files are root-owned (0644). The
   wrapper and driver pre-create the staging directories as `<user>`, so moving and deleting work.
7. **Restart policy.** The container keeps `--restart unless-stopped`: a reboot in capture mode comes
   back in capture mode. Always finish with step 4.
8. **Pinned to these files.** The hook is tied to `prompt_logprob.py` sha256 `4cf22d39…`, and the
   wrapper to `start.sh` sha256 `e1196cbc…` (it refuses otherwise). On any other image, rerun
   `tests/` first.
9. **Response size.** Each response carries the per-token prompt logprob: about 10-15 MB of JSON at
   128K tokens, detokenized by the API server. That is tolerable; `--verify-chosen` uses it.
