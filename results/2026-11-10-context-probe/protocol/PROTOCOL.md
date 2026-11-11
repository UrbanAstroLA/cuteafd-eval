# Context probe: CuteAFD v5.0.0 attention precision at long context and across turns

**Status: FROZEN 2026-11-10 for the graded task runs (sections 5, 8, 9, 13).** The start check, layer 1, the turn
check, the repeat check and the pilot (sections 10 to 13) were exploratory and are reported as such. Measured
requests begin only after the freeze in section 8. Results stay local.

## 1. Question

CuteAFD v5.0.0 adds a checkpoint (K4-Core-K6-HQA) that carries BF16 copies of two attention projection groups
beside the K6 ones, and three ways to run it. A short, single-turn, cold request is where a precision difference in attention is least likely to show.

This probe asks, on 2 RTX PRO 6000 with local experts:

1. **Where** does each setting's output distribution depart from an all-original-precision reference: is the
   departure flat with depth, or does it grow toward 128K? (Layer 1, deterministic.)
2. **Does it matter to work**: does exact-match accuracy on the same task fall faster with context length under
   one setting than another? (Layer 2, sampled, graded.)
3. **Do turns add anything**: a multi-turn conversation leaves history in the cache that was written by decode
   steps (and by speculative verify), not by the block prefill a cold request uses. Is a conversation continued
   on that state equivalent to the same tokens prefilled cold, in distribution (engine check) and in accuracy
   (Layer 3)?

Each answer is read against one constraint: speed, usable context and precision on fixed hardware.
`hqa` costs about 2.5 GiB over `compact`, `fp8-compact` about 0.5 GiB; on 2 RTX that memory is KV pool, so a
precision setting is only worth its place if the depth profile or the task layer shows what it buys.

## 2. Arms

One engine (CuteAFD v5.0.0, tag d8e566e85, image sha256:6194637e…, stack `<stacks>/cuteafd-v5`), one at a
time on 127.0.0.1:8001. Same K4 experts and drafter in every arm.

| arm | checkpoint | launch | what it is |
|---|---|---|---|
| `hqa` | K4-Core-K6-HQA e0ecc3d5 | hqa config, default | BF16 `q_b_proj` (12) and `o_proj` (46) at every row count |
| `hqa-bf16pre` | same | `--set GLM5_FLASH_FP8_PREFILL=off` | `hqa` with FP8 prefill off (added after the start check: `hqa`'s load line reports `fp8_prefill=[Mla, Ffn]`); separates the prefill precision from the weights |
| `compact` | same | `--set ATTENTION_MODE=compact` | the parent K6 projections everywhere |
| `fp8c` | same | `--set ATTENTION_MODE=fp8-compact` | BF16 projections converted to FP8 at load; W8A8 at prefill |
| `core-fp8` | derived BF16core 049c0180 | bf16core config, default | all 316 core matrices from BF16, v5's default FP8 conversions |
| `anchor` | same | `--set GLM5_FLASH_KDA_FP8=off --set GLM5_FLASH_FP8_HEAD=off --set GLM5_FLASH_FP8_PREFILL=off` | all original precision in the core: the reference |

`core-fp8` is the positive control: a known, larger precision change. If the probe cannot see `core-fp8` against
`anchor`, a null between `hqa` and `compact` means nothing. The start check settled that v5 loads the derived checkpoint (`kda_fp8=Off fp8_prefill=[None] head="BF16"`,
KV pool 1,318,400 tokens against 2,097,152 for `hqa`). The BF16attn checkpoint is refused by v5.

Experts are K4 in every arm, so nothing here measures the expert quantisation. NLL is per tokenizer and the
texts are not comparable with other model families.

## 3. Layer 1: depth profile (deterministic)

`drivers/depth_profile.py`. Five texts of about 127K tokens (two Block T documents: prose, code; three generated
task documents: ledger, join, trace), tokenised once (`depth/texts/`, hashes recorded). Every arm scores the same
token ids through `POST /v1/bench/probe` with `cold` scoring (no cache lookup, nothing retained, no speculation).

- **Prefill path** (`score_path: prefill`, needs `FULL_PREFILL_LOGITS=on`): one request per text; 64 recorded
  positions in every 4,096-row unit from 4K to 123K (32 consecutive, 32 spread), plus a shallow request for 1-4K.
  9,728 rows per arm-run.
- **Decode path** (`score_path: decode`, 64-row steps): one request per depth in {4K, 16K, 32K, 64K, 96K, 120K},
  64 positions each. 1,920 rows per arm-run. `--verify-rows` repeats it at another step width.

Each row is dumped full-vocabulary (154,856 F32 log-probabilities), so KL is exact, not a top-k bound. Each arm is
captured twice, each in its own launch (`r0`, `r1`); `compare` of the two gives the launch-to-launch floor on this
path (within one launch the start check found the decode path and a cold prefill bit-identical). Reported
per depth band (1-4K … 96-128K): mean KL(a‖b), top-1 flip rate, ΔNLL of the given token, hash-equal fraction; 95%
intervals from resampling (text, unit) clusters.

Comparisons: every arm against `anchor`; `compact` against `hqa`; `fp8c` against `hqa`; each arm against itself.
Reading: a setting whose KL to the anchor rises with depth is losing precision in something that accumulates
with context; one that is flat costs the same at 4K as at 128K. Prefill and decode paths are read separately:
they use different kernels and, in `fp8c`, different activation precision.

## 4. Layer 3 engine check: is decode-written history equivalent to prefilled history?

`drivers/turn_check.py`. Serving launch with the prefix cache on and the bench route enabled. Per conversation:

| leg | what runs | isolates |
|---|---|---|
| history turns | served normally (drafts on, protocol sampling), replies fed back verbatim | builds the live cache state |
| `live` | last user message on that state, greedy, 32 recorded rows | the real continuation |
| `cold-a`, `cold-b` | the same token ids, cold block prefill, twice | reference and its floor |
| `replay-p` | cold, prefill chunks cut at every reply boundary | the effect of cut positions alone |
| `replay-64`, `replay-1` | cold, earlier replies re-run as decode steps of 64 / 1 rows | decode-written history, no cache, no drafts |

Pairs: cold-a/cold-b (floor), cold-a/replay-p (cuts), replay-p/replay-w (decode-written history), replay-w/live
(the live cache and speculation path against a deterministic replay), cold-a/live (total). Rows are compared up
to the first differing generated token. Per turn the driver also records whether the re-rendered history equals
the tokens the engine generated (round trip) and how much of the prompt was restored from cache; a round-trip
break or a partial restore is itself a finding about multi-turn cost.

Upstream's own `cache_exact` baseline (`POST /v1/bench/probe {"body": …, "cache_exact": true}`) checks that a
snapshot restore is bit-exact against the state it was taken from, at short length. It does not compare
decode-written history with the same tokens prefilled; this check does. The remote route's `cache_exact` is a
media fixture check (it requires one image or audio part; these launches run with vision off), so it is not run
here; `cold-a` against `live` covers the restore at the conversation's real length.

Sizing: 12 conversations per arm (3 families × lengths 16K and 64K × single+follow-up and 8 parts), on `hqa`,
`hqa-bf16pre`, `compact`, `fp8c`. `replay-1` is skipped where it needs more than 20,000 decode steps (the bench client's
loopback read times out after 900 s of silence).

### 4a. Repeat check: alone and in a batch (added 2026-11-10)

`drivers/repeat_check.py`, run in the turn-check launch of each arm after its conversations. Every other
bit-identity check here is single-stream; this one asks whether greedy output survives the decode batch. One
byte-identical prompt (pilot item `trace-000-16k`, no nonce), temperature 0, thinking on, replies cut at 768
tokens: 4 requests one at a time (the reference and the single-stream floor), then 256 at concurrency 8 (the
launches resolve a boot concurrency of 16). Reported: distinct outputs, how many equal the reference, and for
each variant the character offset of its first difference. Exploratory. A variant is a numerics observation
about batch composition, read with the single-stream floor beside it; it says nothing about answer quality.

## 5. Layers 2 and 3: graded tasks

`drivers/gen_tasks.py`, `tasklib.py`, `run_tasks.py`, `analyze_tasks.py`. An item is a set of records carrying the
answer, near-miss records, a question with 8 fields and an exact answer. The same item is rendered at 4K, 16K,
64K and 127K: signal, near-misses, question and answer are byte-identical and only the number of distractor
records changes, so length is a dilution dial and every item is its own control across lengths and arms.
Families: `ledger` (running totals over scattered events), `join` (three keyed lookups at unrelated depths),
`trace` (a call chain through scattered Python functions). Every rendered item is re-derived by an oracle.

- **single**: one cold prompt per item. Measured set: 60 items × 4 lengths = 240 requests per arm per seed
  (12.8 M prompt tokens).
- **turns**: the same records delivered as `parts` user messages, each acknowledged by the engine, then the
  question; replies fed back verbatim. Primary `parts=8` at every length; `parts=32` at 64K and 127K secondary.

Request settings, identical in every arm: thinking on, temperature 1.0, top_p 0.95, top_k −1 (sent explicitly),
`clear_thinking: false`, a distinct recorded seed per request (same index → same seed and nonce in every arm),
loop abort at the v5 default, prefix cache at the serving default, concurrency fixed across arms.

Score: fields correct / fields from the last `ANSWER:` line. A reply that hits the cap or is ended by the loop
abort scores 0 and is counted in its own class. Unit of analysis: the item. Repeats are averaged within item;
arm differences are paired on (item, length, mode, repeat) with a 95% interval from resampling items; the length
effect is the difference at 127K minus the difference at 4K. Beside every score: finish classes, reasoning and
completion tokens, decode tok/s, time to first token, cached fraction, acknowledgement compliance, accuracy by
family and by how far back a field's earliest evidence sits.

Two request-level readings on "every field correct" sit beside the interval (added 2026-11-10; `analyze_tasks.py
compare`). **Flip floor**: the share of (length, item) pairs whose outcome differs between two repeats of the
same arm (distinct seeds, same engine setting). **Exact McNemar** per repeat on the paired requests of two arms
(same item, length, seed). A between-arm discordance at or under the floor with balanced off-diagonal counts is
no measured difference; the test is read per repeat because requests of one item are not independent across
repeats. The floor needs two repeats of an arm in the cell being read, so every arm that is compared in `single`
runs two; an arm with one `turns` repeat is read against the floor of the arm it is compared with.

60 items per cell resolves an arm difference of roughly 6 to 7 points in one cell, and about half that pooled
over the four lengths.

## 6. Launch forms

Bench key (scoring and turn-check launches only), created per chain and shredded on every exit path:

```
umask 077; mkdir -p <secrets>; head -c 32 /dev/urandom | base64 | tr -d '/+=\n' > <secrets>/bench-api-key
shred -u <secrets>/bench-api-key
```

| layer | config | extra `--set` |
|---|---|---|
| 1 | `…-hqa-2rtx-score.config` / `…-bf16core-2rtx-score.config` | arm settings; `PROBE_DUMP_ROOT=<runs>/2026-11-10-context-probe/depth/dumps` |
| turn check | `…-hqa-2rtx.config` (cache on) | arm settings; `ENABLE_BENCH=on`; `API_KEY_FILE=…/bench-api-key`; `PROBE_DUMP_ROOT=…/turncheck/dumps` |
| tasks | `…-hqa-2rtx.config` / `…-bf16core-2rtx.config` | arm settings only |

All from `<stacks>/cuteafd-v5` with `HF_HOME=<hf-home>`. The chain runs under `systemd-run --user`,
stops the vLLM recipe on :8001 first, and restores and request-checks it on every exit path. GPUs are checked
idle (full `nvidia-smi` listing, graphics clients included) before the first request of each launch.

## 7. Order, stop points, cost

| step | what | GPU time (estimate) | decides |
|---|---|---|---|
| S | **Start check** (exploratory): each arm launches; pool size and VRAM per arm; `cache_exact`; one probe of each kind; one 2-turn conversation | 1 h | whether `anchor` loads; `generated`/stop-token and round-trip behaviour; replay timing; verify capacity |
| A | **Layer 1**, 6 arms × 2 captures (separate launches), both paths | 3–4 h | the depth profile; which arms are worth task time |
| B | **Turn check**, 4 arms × 12 conversations | 2–3 h | whether turns are a distinct engine path at all |
| B′ | **Repeat check** (4a), same 4 launches | about 10 min each | whether batching changes greedy output |
| P | **Pilot** (exploratory, pilot item set, `hqa` only): cap, concurrency, parts, difficulty | 2–3 h | the frozen task settings; measured items regenerated if difficulty moves |
| C | **Tasks, single**, per arm per seed | 2–3 h each | accuracy × length |
| D | **Tasks, turns p8**, per arm per seed | 3–5 h each | accuracy × delivery |

S, A and B are deterministic or near it and cheap; they report before any task run. **Stop point after B**: the
task arms and repeats are chosen from what A and B show, then frozen. Full grid if nothing is pruned: 5 arms ×
(2 single + 1 turns) ≈ 35–55 GPU-h. Task-run times are estimates from v4 speeds (about 20–25 s to first token at
128K) and an assumed 3–5K reasoning tokens per reply; the pilot replaces them with measurements.

Disk: full-vocabulary dumps are 0.62 MB per row: about 7 GB per arm-capture in layer 1 (72 GB for 5 arms × 2),
under 1 GB for the turn check. `<data>` has 1.7 TB free. Dumps are removed afterwards by hand,
with a manifest; the receipts (hashes, top-20, per-row KL) stay.

Downloads needed before S: the v5 coordinator image (36 GB class, most layers shared with v4), and 4.2 GiB of
HQA files (the 49 blobs identical to the parent K4-Core-K6 repo are hard-linked from the local cache first).

## 8. Freeze

After the pilot and before the first measured request: this file is renamed `PROTOCOL.md` with the pilot's
choices written in, the measured item set is final, and `FROZEN.json` records the hashes `run_tasks.py` checks:

```
cd <runs>/2026-11-10-context-probe && python3 -B -c "import json,sys;sys.path.insert(0,'drivers');import probelib as P;fs=['PROTOCOL.md','items/measured/index.json']+['drivers/'+n for n in ('run_tasks.py','probelib.py','tasklib.py','analyze_tasks.py','depth_profile.py','turn_check.py','gen_tasks.py')];P.write_json_atomic('FROZEN.json',{'frozen_at':P.now_iso(),'sha256':{str((P.RUN/f).resolve()):P.sha256_file(P.RUN/f) for f in fs}})"
```

Any later change to a listed file is a declared amendment with its own entry here, not a silent edit.

**Frozen 2026-11-10** with the settings of §13, before the first measured request. This file was
`PROTOCOL-DRAFT.md` until then; driver docstrings and earlier notes that name the draft mean this file.
Amendments: none.

## 9. Reading rules (fixed before data)

- A difference is read only against its own floor: run-to-run for layer 1 and the turn check, the item bootstrap
  for tasks. `core-fp8` against `anchor` must be visible in a layer before a null in that layer is read.
- Layer 1 says where distributions differ, not whether answers do. Layer 2 says whether answers do, not why.
  A claim about a setting needs the two to agree, or says which one it rests on.
- Cap hits and loop aborts are outcomes, reported per arm and length, never dropped.
- Every table names its arms, item set, seeds and whether it is exploratory.
- Findings are tagged by what they depend on: the 2-RTX placement, the shared attention kernels (which other
  CuteAFD layouts also run), or the checkpoint.

## 10. Start check (2026-11-10, exploratory; arm `hqa` unless stated)

- **Loads.** `hqa` ready in about 60 s, pool 2,097,152 tokens, 94.2 / 93.2 GiB used. `anchor` ready in about
  80 s, pool 1,318,400 tokens, BF16 head, no FP8. Other arms are first launched by step A.
- **Row alignment.** From the dumps, row p holds the distribution that selects `ids[p]`: mean log-probability at
  shift 0 is −5.1 (decode path) / −4.6 (prefill path), against −11.6 to −14.9 at shifts ±1 and ±2. Rows are
  normalised.
- **Determinism within a launch.** Decode-path capture twice: 64 of 64 rows hash-equal. Cold prefill twice at
  22K: 32 of 32 rows hash-equal.
- **Reply round trip.** `generated` ends with the stop token (`<|user|>`, 154827); the next turn's rendered prompt
  reproduces prompt + generated exactly, and the cache restored 22,431 of 22,452 tokens.
- **Replay.** Width-1 replay of a 6,012-token reply: 83 s (about 72 steps/s), so the 20,000-step limit is about
  280 s, inside the 900 s read timeout. Width 64: 9 s.
- **First turn-check reading** (one conversation, 16K ledger item, single + follow-up; not a measurement):
  `live` is bit-identical to both decode replays (32 of 32 rows, widths 1 and 64). `cold-a` against `replay-p`
  (same tokens, all prefill, different chunk cuts) is not: KL mean 5.9e-3, greedy text diverges at token 7.
  `cold-a` against `live`: KL mean 9.7e-3, diverges at token 12. So the served cache path is reproducible, and
  what differs is which tokens were written by prefill and how the prefill was cut.
- **Not settled:** KV pool pressure from 128K prefix snapshots under concurrency; `record_state` (not used).

## 11. Layer 1, first round (2026-11-10, exploratory): the user-turn frame cannot separate arms

One capture of each arm with the section 3 texts placed inside a user turn (`r0`; all six arms loaded and
captured). Read on `anchor`, `core-fp8` and `hqa`, prefill path, 9,408 rows:

- All three pairwise KLs are the same size: `anchor`‖`core-fp8` 0.588, `anchor`‖`hqa` 0.583, `core-fp8`‖`hqa`
  0.589 (means; medians 0.012–0.025; top-1 differs on 14.5% of rows; no row hash-equal). The decode path is alike.
- It does not depend on depth (1–4K as 96–128K) or on position inside a prefill unit.
- It is concentrated where the model is unsure. Rows where all three arms give the true token p ≥ 0.9
  (n = 3,531): KL about 0.003, no top-1 difference. Rows where all three give it p < 0.5 (n = 4,578): KL about
  0.8, top-1 differs on 23.6%.
- Per-arm NLL on the true tokens is the same in the three arms and high (prose 4.4, code 3.5, ledger 2.7, join
  3.0, trace 2.3). Decoded top predictions are often not continuations of the text.
- Within one arm and launch, prefill and decode paths at the same 891 positions agree on top-1 at 0.88.

Reading: positions inside a user turn are not next-token prediction the model was trained to do well, so its
distributions there are broad and any numerical change moves them by a large, arbitrary amount. The positive
control is "visible" but so is everything else, at the same size: section 9's first rule cannot be met in this
frame. The start check's reading on the model's own reply was 6e-3 to 1e-2, on-distribution.

Amendment to section 3: the same five documents are re-tokenised as the visible content of an assistant turn
(`depth/texts/<name>.asst.json`; frame `asst` = system line, a one-line request to write the document out, a
short think block, then the document, rendered as the checkpoint template renders an assistant message). Step A
becomes: user frame `r0` on six arms and `anchor` `r1` (launch-to-launch floor); assistant frame `a0` on six
arms and `a1` on `anchor` and `hqa`. The first `asst` capture is checked (within-launch path agreement, NLL)
before the rest is read; if the instability is still there the chain stops.

### 11a. Assistant frame, first reading (2026-11-10, exploratory; one capture per arm)

`drivers/depth_strata.py`. `anchor`, `core-fp8`, `hqa`, prefill path, 9,728 rows: KL mean 0.0150 / 0.0168 /
0.0173 for anchor‖core-fp8, anchor‖hqa, core-fp8‖hqa (medians 6.3e-4, 5.4e-4, 7.9e-4; top-1 differs 6.1%, 5.1%,
6.7%). Rows where all three give the given token p ≥ 0.9 (n = 4,943): about 5e-4 to 7e-4, no top-1 difference,
rising about twofold from 1–4K to 96–128K. 136 rows where the arms straddle p = 0.5 carry over half the mean.

Path floor, same 891 positions: prefill against decode path inside one launch is KL mean 0.0051 (`anchor`, both
paths BF16) and 0.0071 (`hqa`), median 1.65e-4, top-1 differs 3.6%, no row hash-equal. Each path repeats
bit-exactly (section 10) and two `anchor` launches are bit-identical, so this is a difference between the two
paths' arithmetic, not noise. Section 3's "decode path and a cold prefill bit-identical" meant each path against
its own repeat. Arm differences are read against this path floor as well as against the launch floor (zero).

### 11b. `hqa-bf16pre` is `hqa`; the tail of the KL is isolated collapse rows (2026-11-10, exploratory)

**`hqa-bf16pre` equals `hqa` bit for bit**: all 11,648 rows, both score paths, in the user frame (r0) and the
assistant frame (a0). The load line does change (`fp8_prefill=[Mla, Ffn]` against `[None]`), but in v5.0.0
`mla_producer`, `mla_output` and `ffn_on` (`glm5_flash/engine.rs`) return into the `core_*` / `native_*` functions
before `fp8_prefill` is read, and those take no prefill/decode precision argument. On a Core-K6 checkpoint the
setting is inert, so the arm is a second launch of `hqa`, not a precision arm. It gives `hqa`'s launch-to-launch
floor: zero, as for `anchor`. Section 2's row for the arm and section 3's "separates the prefill precision" no
longer hold; the arm's turn check and repeat check are kept as a second-launch replicate of the serving path.

**Intervals** (`drivers/strata_boot.py`, resampling runs of consecutive rows within each text): the three pairs'
mean KL on the prefill path are 0.0150 [0.0092, 0.0228], 0.0168 [0.0107, 0.0245], 0.0173 [0.0100, 0.0297]; every
difference between pairs includes 0. The path floor (0.0051 [0.0018, 0.0093]) is below each arm-to-arm pair on
the same 891 positions (differences exclude 0). Mean KL does not rank these arms.

**Tail.** Ten of 9,728 rows carry 40% of the mean. 28 rows have a pair KL above 1 nat: 27 in `code`, 18 of them
at 96–128K, none shallower than 16K. The given token is fixed by the local pattern (for example 14 earlier
identical continuations), and one arm gives it p near 0 with an unrelated top-1. The odd arm is `anchor` 7 times,
`core-fp8` 11, `hqa` 11. Rows where an arm gives p < 0.05 to a token another arm gives p >= 0.9: 2 / 2 / 7 on the
prefill path, 1 / 0 / 2 on the decode path. They reproduce bit-exactly across the two `hqa` launches. Candidate
mechanism, untested: the DSA layers' top-k token selection (`index_topk` 2048, pooled by 4) is a hard cut, and a
numerical difference moves a needed token across it. Reported separately from the body of the distribution
(median, sure rows) from here on.


### 11c. Five arms, relative and absolute (2026-11-10, exploratory; one capture per arm)

Readers: `depth_strata.py` (five a0 captures, both paths; `logs/strata-a0-5arms.*.log`) and an inline scoring of
each arm against the text itself (`logs/arms-a0-absolute.log`). What each arm loads (server logs): `anchor`
17.84 GB dense source, coordinator 6.21 GiB, head BF16; `core-fp8` same source, 4.66 GiB, head FP8, KDA Row128;
`hqa` 10.77 GB, 4.50 GiB; `compact` 8.08 GB, 3.24 GiB; `fp8c` 10.77 GB, 3.49 GiB (K6 head on the last three).

**Relative (prefill path, 9,728 rows; KL mean / median / top-1 differs).** To `anchor`: `core-fp8` 0.0150 /
0.00063 / 6.1%; `hqa` 0.0168 / 0.00054 / 5.1%; `compact` 0.0176 / 0.00055 / 5.2%; `fp8c` 0.0184 / 0.00066 / 5.7%.
Closest pair `hqa`|`compact` 0.0159 / 0.00038 / 4.2%; `core-fp8` is the furthest from the three K6 arms (median
0.0008–0.0009). Sure rows (4,916): every pair 0.0004–0.0007, top-1 never differs. Decode path (1,920 rows): same
order, medians 0.0004–0.0010. Path floor for scale: median 0.00017.

**Absolute (NLL of the given token / top-1 = given; difference to `anchor` with a 95% run-bootstrap interval).**
Prefill path: `anchor` 1.4509 / 66.2%; `core-fp8` −0.0012 [−0.0057, +0.0034]; `hqa` +0.0017 [−0.0040, +0.0081];
`compact` −0.0055 [−0.0109, −0.0000]; `fp8c` −0.0013 [−0.0065, +0.0039]; top-1 within ±0.2 points for every arm.
Decode path: `anchor` 1.5881 / 64.4%; `core-fp8` −0.0090 [−0.0172, −0.0013]; `hqa` −0.0001 [−0.0063, +0.0062];
`compact` −0.0085 [−0.0192, −0.0006]; `fp8c` −0.0033 [−0.0220, +0.0112]. Top-1 = given is flat across arms in
every depth band up to 96–128K. No arm is measurably worse than `anchor` at predicting the text, at any depth;
the two intervals that exclude 0 favour the cheaper arm by under 0.01 nat and are not read as an improvement
(one capture, five texts, no multiplicity correction).

**Collapse rows (arm p < 0.05 where at least 3 of the other 4 arms give p >= 0.9).** Prefill path: `anchor` 2,
`core-fp8` 1, `hqa` 4, `compact` 0, `fp8c` 1; all in `code`, mostly at 96–128K. Decode path: 0 for every arm.

**Reading.** On this measure the arms are perturbations of each other of about the same size, not a ladder with
`anchor` at the top: the differences are symmetric (no arm loses likelihood), and the rare large rows hit every
arm including `anchor`. Layer 1 therefore does not price the cheaper arms; whether the 5–6% of rows whose top-1
moves matter is a generation question (turn check, repeat check, then the task runs).

**Launch floor, assistant frame (15:27).** `anchor` a0 against a1 and `hqa` a0 against a1: 11,648 of 11,648 rows
bit-identical in each (dump hash and given-token log-probability, both paths). With `hqa` ≡ `hqa-bf16pre` that is
three independent launch pairs at zero: every difference in 11a–11c is between arms, none is launch noise.

## 12. Turn check and repeat check, results (2026-11-10, exploratory; one run per arm)

Reader: `drivers/turn_summary.py <arm>`. Arms `hqa`, `hqa-bf16pre`, `compact`, `fp8c`; 12 conversations each.
`anchor` was not in this step.

**Exact.** Cold prefill twice: bit-identical in all 46 completed conversations. Replays written by 1-row and by
64-row decode steps: identical. Live cache-resumed path against the replay: bit-identical in 45 of 46. Round
trip of the previous turn: exact in every turn. Repeat check (greedy, 4 serial + 256 at concurrency 8): one
output text in all 260 requests on every arm; 259 of 260 resumed from the prefix cache, so this is batched decode
from a restore, not concurrent prefill. `hqa-bf16pre` reproduces `hqa` line for line (same reply lengths, same
KL values, same repeat output hash): a relaunch changes nothing in generation either.

**The one non-exact conversation is a harness artifact.** `compact`, `join-000-64k`, 8 parts: live against replay
differs on all 32 rows (KL mean 0.0012, max 0.012, no top-1 change). In turn 0 the model ended its turn inside
the thinking block (`ACK 1` then the stop token, 4 generated tokens, empty content). The template renders that
history with a `</think>` the model never generated; the live path prefills it, `reply_spans()` counts it as
reply and the replay writes it by a decode step. Of 214 replies in the 46 conversations this is the only one
whose replayed span (4) differs from what the engine holds in its cache for that reply (3). Not re-run.
Descriptive: in that conversation all seven acknowledgement replies had empty content (the text sat in the
thinking block); `hqa` and `fp8c` answered in content. One sampled conversation per arm.

**Not exact, in every arm.** Cold in one prefill against prefill cut at turn frontiers: never bit-equal, KL mean
0.001–0.02 (two conversations higher where the first compared row already differs). Prefill-written against
decode-written replies: 0.002–0.045. Live against cold: 0.002–0.04. The greedy 32-token continuation diverges
between live and cold in 5 of 11 (`hqa`), 4 of 12 (`compact`), 5 of 12 (`fp8c`) conversations. Same size as the
layer 1 path floor (11a); `anchor` showed the same floor there, so this reads as an engine property and not a
precision effect, by inference from layer 1.

**Descriptive.** Per-stream decode at concurrency 8 (one measurement each): `hqa` 69.4, `hqa-bf16pre` 69.3,
`compact` 71.3, `fp8c` 73.0 tok/s. `hqa` (both launches) ran `ledger-000-64k` single to the 16,384 cap; `compact`
finished it at 10,967 generated tokens and `fp8c` at 10,141 (sampled replies, one each: not an arm comparison).
KV pool admitted (score launches, concurrency 16, context 262,144): `anchor` 1,318,400 tokens, `core-fp8`
2,057,216, `hqa` / `compact` 2,097,152 (the configured maximum); serving launches of `hqa`, `compact`, `fp8c` also
2,097,152.

**Design limits of this check (for a second version).** (1) Rows are compared up to the first differing token,
so a diverged pair keeps 1–28 rows and "top-1 differs" cannot exceed 1: it detects a divergence, it does not
measure a rate. (2) Decoded history is small: under 6% of the context in the 8-part form (all but one conversation under 3%), 2.5–36% in the
single-reply form. (3) Only the last turn is scored. (4) History replies are sampled live, so inputs differ per
arm. (5) Stops at 64K. (6) No reference arm. (7) Reply spans come from the rendered prompt, not from what the
engine decoded (the artifact above). (8) The 1-row replay is redundant. A second version: frozen conversations
replayed as fixed tokens, teacher-forced scoring of a fixed continuation at every turn boundary, decoded history
as the varied quantity out to 128K, legs cold / cuts only / decode-written, `anchor` included.

End state 17:25: vLLM restored and request-checked, bench key shredded, machine status checks pass.

## 13. Pilot (2026-11-10, exploratory) and the frozen task settings

Pilot item set (indices 0–5 per family: 18 items × 4 lengths = 72 requests per pass), run tag `p0`, cap 32,768,
acknowledgement cap 4,096, concurrency 8. `hqa`: two `single` passes and one `turns` pass with 8 parts. `anchor`:
the 127K length only, one pass per mode, as a capacity check for the smallest KV pool. All five runs finished
with no request error. One run per cell; nothing here is a measured result.

**`hqa`, single, two passes pooled (36 requests per length)**

| | 4K | 16K | 64K | 127K |
|---|---|---|---|---|
| field score | 0.979 | 0.990 | 0.972 | 0.823 |
| every field correct | 0.83 | 0.92 | 0.83 | 0.61 |
| stop / cap | 36 / 0 | 36 / 0 | 36 / 0 | 33 / 3 |
| completion tokens, median | 2,981 | 3,587 | 4,992 | 5,405 |
| decode tok/s per stream, median | 34.1 | 30.5 | 30.9 | 38.2 |
| time to first token, median (s) | 0.8 | 3.2 | 12.7 | 25.1 |
| every field correct, `join` | 12/12 | 12/12 | 12/12 | 11/12 |
| every field correct, `ledger` | 6/12 | 11/12 | 6/12 | 1/12 |
| every field correct, `trace` | 12/12 | 10/12 | 12/12 | 10/12 |

**`hqa`, turns with 8 parts (18 per length):** field score 0.993 / 0.979 / 0.972 / 0.861; every field correct
0.94 / 0.83 / 0.89 / 0.78; caps 0 / 0 / 0 / 2; cached fraction 0.96–1.00. Acknowledgements: 576 part turns, 98.3%
exact, 9 hit the 4,096 cap (8 of them in one `ledger` 64K conversation).

**`anchor`, 127K only (18 per mode):** single: field score 0.875, every field correct 0.56 (`join` 6/6, `ledger`
1/6, `trace` 3/6), no caps, time to first token 51 s. Turns: 0.806, 0.67 (`join` 6/6, `ledger` 1/6, `trace` 5/6),
3 caps, all `ledger`. Concurrency 8 fits `anchor` at 127K in both modes.

**Flip floor in the pilot** (`hqa`, pass 0 against pass 1, every field correct): 2, 3, 2 and 4 of 18 at the four
lengths, 11 of 72 in all (`ledger` 6, `trace` 4, `join` 1). `single` pass 0 against `turns` disagrees in 11 of
72, the same as the floor: no turn effect is visible at this size.

**Capped replies** are all finish class `cap`, none `repetition`. In each the model copies the context record by
record inside its thinking (54–83K reasoning characters, no repeated window). A higher cap would not turn them
into answers.

**What the pilot fixes**

- Reply cap 32,768; acknowledgement cap 4,096; concurrency 8 for every arm; `parts=8`. The `parts=32` secondary
  is not run.
- Arms: `anchor`, `hqa`, `compact` (chosen at the stop point after §12). `fp8c` and `core-fp8` are added only if
  one of the three separates from `anchor`, as a declared amendment.
- Passes per arm: `single` rep 0, `single` rep 1, `turns` p8 rep 0. Run tag `m0`. Order: by pass across the three
  arms (`anchor`, `hqa`, `compact`), so that every cross-arm reading is complete before the next pass starts.
- The measured item set (`items/measured`, indices 100–119 per family) is used as generated. Difficulty was not
  moved: two harder `trace` settings were tried through `--params` and the generator could not fit either at the
  short lengths (`superseded/pilot-variants`).
- Thinking length is reported as reasoning characters (the engine reports no reasoning token count with
  `USAGE=off`).

**What the pilot says about sensitivity, stated before the measured data.** `join` is at ceiling at every length
and `trace` nearly so below 127K; they are read as sentinels for gross breakage, and `trace` at 127K bears on the
collapse rows of §11. The arm comparison's resolving power sits mostly in `ledger`, and to a lesser degree in
`trace` at 127K. The pooled-over-families figure in §5 (6 to 7 points per cell) therefore overstates what one
family resolves: with 20 `ledger` items per cell the resolution within that family is roughly ±0.14 in one cell
and ±0.07 pooled over lengths. Every table is reported by family as well as pooled, and a pooled null is not read
as a `ledger` null. Adding `ledger` items (a separate set with its own freeze) is the remedy if the measured
intervals are too wide to decide; it is not part of this freeze.

Measured cost from the pilot's timings: about 85 min per arm per `single` pass and 97 min per arm for `turns`,
about 4.5 h per arm, 14–15 h for the three arms with launches.
