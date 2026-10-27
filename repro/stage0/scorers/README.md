# Stage 0 scorers: CuteAFD v3.0.1 vs vLLM v0.9.2, Blocks Q and Q2

CPU only. Nothing here used a GPU, started or stopped a container, or contacted a server. The
one container use is `tests/test_cuteafd_compare.py`, which runs the CuteAFD release image's
`bench fidelity compare` subcommand with `--network none` on two synthetic files.

Python: `<venv>/bin/python -B` (numpy 2.5.3, scipy 1.18.1). Run every script
with `-B` so no bytecode is written anywhere.

| File | What it does |
|---|---|
| `common.py` | Safetensors reader (F32/BF16/F16), engine-row readers, fp64 numerics copied from `kld_score.py`, alignment detector, bootstrap |
| `plans.py` | Writes the CuteAFD plan, the vLLM registry and a metadata file for P-A, P-B and Q2 |
| `score_pa.py` | P-A: full-vocabulary fp64 scoring against the BF16 teacher; single-arm and paired modes |
| `score_pb.py` | P-B: port of tpurtell's top-1024-plus-tail rule; single-arm and paired modes |
| `score_q2.py` | Q2: compares two engines with no teacher, against a within-engine repeat floor |
| `validate_pb.py` | GPU-day check of `score_pb.py` against his CLI, record by record; also compares raw row captures |
| `tests/test_scorers.py` | 27 CPU tests with known answers |
| `tests/test_cuteafd_compare.py` | Checks our paired statistics against his binary |
| `selfcheck.sh` | Runs all of the above, plus the real-data P-A checks |
| `plans/` | The generated P-A and P-B plans (hashes below) |
| `selfcheck/` | Output of the real-data P-A checks |

---

## 1. Input contract (both engines)

**Row convention.** Row *r* of a window is the distribution after `tokens[0..r]`. It predicts
`tokens[r+1]`. This is the same convention used by:

- `glmf-teacher-kl.py`, plan `positions` (docstring lines 28-30);
- our vLLM registry `rows`;
- the P-A teacher files (`PLAN.md` §2).

tpurtell's reference indexes by the **predicted position** *p = r + 1* instead
(`reference.rs:83-96`). `score_pb.py` converts between the two.

**Per-window engine file `<window_id>.safetensors`**:

- **Values.** A tensor named `logprobs` (our plugin) or `logits` (`glmf-teacher-kl.py:159-164`),
  of shape `[n_rows, 154880]` and dtype F32, BF16 or F16. Every scorer log-softmaxes again in
  float64, so raw logits and log-probs both work.
- **Row index.** A tensor named `rows` (our plugin) or `positions` (`glmf-teacher-kl.py`, I32).
  Both hold plan rows *r*, not *r+1*.
- **No row index.** Accepted only when the row count equals the planned count; the rows are then
  taken as 0..n-1. This is the legacy P-A plugin layout, `window-%04d.safetensors`.
- **Token hash.** If the metadata carries `tokens_sha256` (glmf) or `token_ids_sha256_raw`
  (legacy plugin), it is checked against the plan's tokens.

**What CuteAFD actually writes** (checked in source). Everything is F32. There is no BF16 or F16
option.

- **`glmf-teacher-kl.py`** writes `positions` I32 `[k]` and `logits` F32 `[k,V]`. Despite the name,
  `logits` holds log-probs, copied byte for byte from the dump (lines 96-118, 159-164).
- **CLI `--dump-dir`** writes one F32 `log_probs` `[V]` file per row, plus `manifest.jsonl`
  (`probe/rows.rs:59-86`). Each value is `(f64(logit) - lse) as f32` (`probe.rs:446-456`).
  `score_pb.py` and `validate_pb.py` read this layout directly (`--layout cuteafd-dump`).

**For the vLLM plugin:**

- Store raw BF16 logits, or F32 log-probs. **Never store BF16 log-probs**: with 8 significant bits,
  a log-prob of −10 carries up to 0.03 nat of error.
- Include the `rows` tensor.

## 2. Plans (`plans.py`)

`plans.py` uses only the standard library, so it runs with the host's plain `python3`. It
produces byte-identical P-A and P-B files under the venv python.

```bash
cd <run>/stage0/scorers
python3 -B plans.py --out plans --panels pa,pb
python3 -B plans.py --out plans --panels q2 --q2-dir <run>/stage0/prompts/q2
```

| File | sha256 |
|---|---|
| `plans/pa.cuteafd-plan.json` | `c7977da1530072eee26600890da0d36cb07988270d867cc91a35e7cd0d5d7165` |
| `plans/pa.vllm-registry.json` | `ce4ab41dcd2d6cbdaec37ff4a855c5b36a8dfac1683953b7667588760a4141a6` |
| `plans/pb.cuteafd-plan.json` | `505033ea97779398f0702e952326ebfc670755a02308421f40a5a71efe8fdc92` |
| `plans/pb.vllm-registry.json` | `f68c31e262a38388d48804ba4675a0988388e20e1071c7c05f4b66ea5f34f010` |
| `plans/q2.cuteafd-plan.json` | `6d3ad9770a1cc5247f2505109a2e7b4f9d47a2383234c83676368b4492bbe25d` |
| `plans/q2.vllm-registry.json` | `bbb17874033cf9028e6f0138a3d7a90bf0dc5e15bbb212e4922978e17613f81b` |

### What the plans contain

**CuteAFD plan.** Exactly the glmf format: `{"vocab", "windows": [{"window_id", "tokens",
"tokens_sha256" (sha256 of LE u32), "positions"}]}`.

**vLLM registry.** `{"schema", "panel", "vocab", "row_convention", "windows": [{"window_id",
"tokens", "rows"}]}`.

**Metadata.** `<panel>.meta.json` holds `score_from`, block, bucket, doc id and type, and hashes.

### Panels

- **P-A.** 25 windows × 2,048 tokens; rows 0..2046; 51,175 rows in total.
  - Window ids are `final-0000` to `final-0024`.
  - Tokens come from `calibration/panel-v1/arrays/final-%04d.tokens.npy`. Each is checked against
    `dataset-manifest.json`.
- **P-B.** 64 windows; rows `score_from-1 .. n-2`, which is 512 per window and 32,768 in total.
  - The order is `windows.json` order, which is also the CLI's full-tier dump order.
  - `windows.json` is checked against `manifest.json` `windows_sha256`.
- **Q2.** Built with `--q2-dir` from the prompt set `stage0/prompts/q2/index.json`: 18 windows,
  that is 6 documents (pg28988, pg7412, pg30754, c0, c1, c2) × 32K/64K/128K, with 4,096 rows each
  and 73,728 rows in total.
  - **The prompt files use tpurtell's POSITION convention.** Position p is scored from tokens 0..p-1,
    and the files list positions L-4096..L-1.
  - `plans.py` converts each position p to row r = p-1, giving rows **L-4097..L-2**. It does this
    the same way for both engines.
  - It asserts that the last row is at most L-2, that `tokens[r+1]` is the scored token, and that
    the positions match the index's `first_row`/`last_row`.
  - A test covers this conversion, and an independent re-check against the source files passed.
  - Fields: `doc_id` = document, `doc_type` = kind, `length_bucket` from L.
  - `--q2-input` still accepts a window list that is already in ROW convention.

### P-B on CuteAFD: use the CLI's own dump, not the glmf plan

`glmf-teacher-kl.py` always sends `score_from: 1` (line 62). The whole window from token 1 on
therefore runs through the scoring path: 8,192-row prefill chunks, or 64-row verify steps.

His CLI sends `score_from = window.score_from` (`fidelity_cli.rs:300`). The context then runs as an
ordinary prefix prefill, and only the 512 scored rows go through the scoring path
(`shared/probe.rs:322-335`). These are two different engine geometries.

The CLI keeps its dumps (`fidelity_cli.rs:295-342`). So one CLI run yields three things:

- his own result;
- CuteAFD's P-B rows in his geometry;
- the exact validation input for the port (§6).

`pb.cuteafd-plan.json` exists and is correct as a plan. Using it is a separate capture geometry,
and the run should be labelled as such.

## 3. P-A formulas (`score_pa.py`)

**Notation.** For window *w* and row *r*, *t = tokens[r+1]*. log *p* is `log_softmax_f64` of the
stored row, copied verbatim from `kld_score.py:58-71`.

| Metric | Definition |
|---|---|
| `kl` | Σ_v p_T(v) (log p_T(v) − log p_E(v)) over all 154,880 ids: KL(teacher‖engine), nats (`kld_score.py:74-90`; bit-equal, tested) |
| `nll` | −log p_E(t) |
| `teacher_nll` | −log p_T(t) |
| `dnll` | `nll − teacher_nll` |
| `top1` | argmax p_E = argmax p_T. Ties go to the lower id on both sides; the BF16 teacher has ties, counted as `teacher_top1_ties` |
| `confident_top1` | `top1` over rows with max p_T ≥ 0.5 (`confident_fraction` reports the share) |
| `top3` | argmax p_E ∈ teacher top 3, ordered by (−p, id) |
| `agree_text` | argmax p_E = t |

- **Aggregates.** Position-weighted means: ratio of sums over windows.
- **95% CI.** Windows resampled with replacement, using numpy `default_rng(20260929)` and 20,000
  replicates (`kld_score.py:138-178`).
- **Paired mode.** `--pair A,B` or the `pair` subcommand. It uses the same resampled windows for
  both arms and reports B − A. The arms must have identical rows, tokens and teacher arrays.

## 4. P-B rule (`score_pb.py`): provenance

Paths are under `<cuteafd>/rust/crates/cuteafd-bench/src` unless stated.

A dataset-backed `fidelity run` scores each window in two steps (`fidelity_cli.rs:331-337`):

1. **In-band.** `Window::score` runs on the in-band probe rows (`reference.rs:285-317`). It sets
   agree, confident, top3, agree_text, ref_nll and argmax.
2. **From the dump.** `score_compact` runs on the F32 dump (`fidelity_rows.rs:163-198`). It
   recomputes kl and nll, and requires the dump argmax to equal the in-band argmax.

The port reproduces what those two steps leave in each record.

**About `reference.rs:302`.** The compact in-band tail, `ln(1 − Σq)` clamped at 1e-12, is
overwritten for dataset runs. The tail actually used is the complement logsumexp. A test shows the
difference: `1 − Σq` cancels when the engine tail is about 1e-13.

| Step | Rule | Source |
|---|---|---|
| Reference load | positions = score_from + i, next = tokens[pos], roles U8 match the mask, 512 × 1024 shapes, sha256 of every file | `fidelity_dataset.rs:324-377, 300-316, 349-354, 364-367` |
| Reference renormalise | 1024 f16 log-probs + f32 tail form one 1025-vector; `x − (max + ln Σ exp(x − max))` in f64 | `fidelity_dataset.rs:368-371`; `fidelity_rows.rs:108-116` |
| f16 decode | IEEE half (numpy float16 is identical; his unit vectors tested) | `fidelity_rows.rs:80-89, 203-210` |
| next_lp | f32 next-token log-prob, **not** renormalised; `ref_nll = −next_lp` | `fidelity_dataset.rs:362, 371`; `reference.rs:309` |
| Window validation | unique ids, finite lp ≤ 0, top sorted descending, tail not NaN | `reference.rs:238-273` |
| Engine row | f64 of the stored F32, renormalised the same way | `fidelity_rows.rs:91-105, 176-177` |
| Engine argmax | ties go to the lower id (`then_with(ib.cmp(ia))`); in-band, (Reverse(logit), id) | `fidelity_rows.rs:178-179`; `cuteafd-api/src/openai/probe.rs:466-476` |
| KL top part | Σ_{t ∈ top1024, stored order} exp(t.lp)(t.lp − e[t.id]) | `fidelity_rows.rs:182-186` |
| Engine tail | peak + ln Σ exp(e − peak) over ids **not** in the reference top-1024 (no cancellation) | `fidelity_rows.rs:187-190` |
| Tail term | added only if `tail_lp` is finite: exp(tail_lp)(tail_lp − tail) | `fidelity_rows.rs:191` |
| Guard and clamp | error unless finite and ≥ −1e-10; then `max(0)` | `fidelity_rows.rs:192-193` |
| NLL | `−e[next]` | `fidelity_rows.rs:194` |
| agree | argmax = top[0].id. top[0] is the **stored** first entry: no id tie-break on the reference side | `reference.rs:306` |
| confident | exp(top[0].lp) ≥ 0.5, renormalised | `reference.rs:307` |
| top3_contained | argmax ∈ the first 3 stored entries | `reference.rs:308` |
| agree_text | argmax = next | `reference.rs:309` |
| Which rows | all 512 per window are scored and recorded; the role is the mask at p; gates and verdict use `gen` only | `reference.rs:289-311`; `fidelity.rs:194-213` |
| Block, bucket | the window's stored labels. bucket = 0-2K if score_from ≤ 2048, 2-8K if ≤ 8192, 8-16K if < 16384 (checked) | `reference.rs:305`; `python/reference/fidelity_windows.py:383-384` |
| Aggregation | plain means over records; confident_top1 over confident records | `reference.rs:335-351` |
| Bootstrap | ratio-of-sums window-block bootstrap, SplitMix64, seed 20260829, 5,000 replicates, windows in sorted-id order (BTreeMap) | `fidelity.rs:125-154, 305`; `fidelity_cli.rs:47-50` |
| Paired (his) | top1_loss, top1_upper95 = loss + 1.645·SE, kl_delta, kl_upper95 = q95, clustered SE, McNemar, confident and top-3 tripwire metrics | `fidelity.rs:269-401` |
| Verdict (informational) | top1 ≥ max(0.93, 0.90), KL ≤ min(0.05, 0.06), confident ≥ 0.96, top3 ≥ 0.97, every window's gen top-1 ≥ 0.80 | `fidelity.rs:194-230`; `manifest.json` `expect` |

**Summation order.** `--sum-order rust` is the default. It reproduces Rust's left-to-right f64 sums
with `cumsum`, so the port should differ from his binary only through libm vs numpy `exp`/`ln`
last-ulp effects. Rust order and numpy order differ by under 1e-13 (tested).

**Outputs.** `pb-<arm>.json` has metrics for gen (primary), ctx and all. Each role is reported
overall with a CI, by block (A-E) and by bucket with CIs, and by window. The same file also has his
verdict, alignment, sources and the count of clamped KL values. Alongside it:

- `pb-<arm>.records.json`: records in his `Position` field order;
- `pb-<arm>.rows.npz`.

**Paired output.** `pb-pair-*.json` has the same groupings with two-sided paired CIs of B − A, plus
`cuteafd_compare`: his one-sided statistics, with A = baseline and B = candidate.

**Comparability.** This KL is his coarse "qualified-top1024-plus-tail" KL. It is a lower bound on
full-vocabulary KL. Never report it next to P-A KL as the same quantity.

## 5. Q2 formulas (`score_q2.py`)

There is no teacher. Per row, with log p as the f64 log-softmax:

| Metric | Definition |
|---|---|
| `nll_A`, `nll_B` | engine NLL of the actual next token |
| `dnll` | `nll_B − nll_A`, paired |
| `kl_ab` | Σ p_A (log p_A − log p_B), full vocabulary |
| `kl_ba` | Σ p_B (log p_B − log p_A), full vocabulary |
| `js` | ½KL(A‖M) + ½KL(B‖M), with M = (p_A + p_B)/2; at most ln 2 |
| `top1_agree` | argmax_A = argmax_B |

**Noise floor.** `--a-repeat` / `--b-repeat` point to a second capture of the same engine, which
may cover any subset of windows. The same quantities are computed between the repeat and the
original, plus `dnll_repeat`. The between-engine values on the same rows are printed beside them.

**Groups.** Overall, by length bucket, by doc type, by bucket × type, and by window.

**CIs.** Bootstrap over **documents** (`doc_id` clusters), numpy, seed 20260929, 20,000 replicates.

**Not a result:** which engine is closer to BF16 beyond 14K.

**Protocol mismatch.** PROTOCOL-DRAFT Block Q2 says "KL between the two engines' top-20
distributions". This scorer computes full-vocabulary KL from full rows. The protocol text needs a
dated amendment, or the capture must change to top-20.

## 6. P-B validation plan (GPU day)

1. **Run his CLI on CuteAFD C1.** Use one launch with `ENABLE_BENCH=on`, `API_KEY_FILE`,
   `PROBE_DUMP_ROOT` and `FULL_PREFILL_LOGITS=on`. In the coordinator:
   ```bash
   cuteafd bench fidelity run --url http://127.0.0.1:8001 --tier full --score-path prefill --arm C1 \
     --dataset-config glm5_flash-v2_20261005_bf16root \
     --dataset-revision a7e7d1b4d82329acebe54ca88dc71d47d0d2056d \
     --dump-dir <DUMP_ROOT>/pb-cli-prefill --out <DUMP_ROOT>/pb-cli-prefill.json
   ```
   This writes about 20.3 GB of dumps, kept.
2. **Port on the same bytes:**
   ```bash
   $PY score_pb.py score --engine <DUMP_ROOT>/pb-cli-prefill --layout cuteafd-dump --cli-order full \
     --arm C1-cli --out <RUN>/pb
   $PY validate_pb.py records --cli <DUMP_ROOT>/pb-cli-prefill.json \
     --port <RUN>/pb/pb-C1-cli.records.json --mode same-dump --out <RUN>/pb/validate-C1.json
   ```
   **Expected:**
   - identical keys: 32,768 records;
   - identical role, block, bucket, reference_argmax, ref_nll and confident;
   - identical argmax, agree, top3_contained and agree_text;
   - per-position |Δkl| and |Δnll| ≤ **1e-10**. Expected about 1e-15 to 1e-13: same f64 operations in
     the same order, libm vs numpy ulp only, and serde_json writes f64 that round-trip;
   - aggregates within 1e-12.

   Exit 0 is a pass and exit 3 a fail. **The port is not used on vLLM until this passes.**
3. **Optional geometry check.** Capture C1 again through `glmf-teacher-kl.py` with
   `plans/pb.cuteafd-plan.json`, then compare the raw rows:
   ```bash
   $PY validate_pb.py rows --a <DUMP_ROOT>/pb-cli-prefill --a-order full --b <GLMF_OUT> --out <RUN>/pb/rows-cli-vs-glmf.json
   ```
   This reports the bit-identical fraction, max |Δ log p|, KL both ways and argmax agreement. It
   measures the score_from=1 geometry difference. It asserts nothing.

**His output and dump layout are fully determined from source:**

- **`--out` JSON (full tier).** A `Run` with schema `cuteafd.fidelity.run/2` (`fidelity.rs:8-35`).
  For the standard tier, the Runs sit under `"decode"` and `"prefill"` (`panels/fidelity.rs:73-93`);
  `validate_pb --score-path` selects one.
- **Records.** `score.records[]` with window, block, bucket, role, position (the predicted *p*),
  agree, confident, top3_contained, agree_text, finite, kl, nll, ref_nll, argmax and
  reference_argmax (`reference.rs:320-325`).
- **Dump leaves.** `window-%03d` for the full and quick tiers, or `window-<path>-%03d` for the
  standard tier (`fidelity_cli.rs:295-299`). The index is the window's place in the tier list:
  - full: `windows.json` order (`reference.rs:99-119`);
  - quick: the windows.json order filtered by `QUICK_WINDOWS` (`fidelity_dataset.rs:46-56`);
  - standard: the `STANDARD_DECODE`/`STANDARD_PREFILL` order (`fidelity_dataset.rs:69-78, 107-108, 135`).

  Each leaf holds `manifest.jsonl` (`position, vocab_size, file, tensor:"log_probs", dtype:"F32",
  byte_order:"little"`) and `row-%08d.safetensors` (`probe/rows.rs:59-86`). The dump order is
  `--cli-order`.

## 7. Test results

**`tests/test_scorers.py`: 27/27 pass** (`tests/results.json`, about 80 s).

- **Numerics:**
  - KL of identical rows is exactly 0; JS of identical rows < 1e-15.
  - `log_softmax_f64` and `kl_rows_f64` are bit-equal to the original `kld_score.py`, and so is
    score_pa's inline form.
  - Analytic uniform-vs-tilted at V = 154,880: error < 1e-14.
  - Two-point KL and JS are exact; disjoint supports give JS = ln 2 exactly.
  - Matches scipy `rel_entr` to 1e-10 relative.
  - Tie rules: argmax and top-3 go to the lower id. BF16 decode is checked.
- **Alignment (off-by-one) detector.** It compares the NLL of tokens[r+1] with tokens[r] and
  tokens[r+2]. It passes aligned rows and flags rows that are one ahead or one behind. It runs on
  every window in all three scorers, and on the teacher, and fails the run.
- **Bootstrap:**
  - The SplitMix64 seed-0 vector is 0xE220A8397B1DCDAF.
  - The Python index draws equal a gcc-compiled C transcription for 4,000 draws.
  - The paired diff of identical arms is 0 with CI [0, 0]; a constant shift is recovered exactly.
- **P-A (small V, real code path):**
  - The teacher as its own engine gives KL = 0 exactly, NLL = teacher NLL exactly, argmax equal.
  - The same holds for BF16-logit storage.
  - glmf layout with F32 log-probs: KL < 1e-12. F16: < 1e-12.
  - A planted teacher tie resolves to the lower id.
  - Planted top-1-miss/top-3-hit and top-3-miss rows give exact flags, and KL equals
    `kl_rows_f64` for those rows.
  - Missing rows and a token hash that does not match are refused. A shifted engine is flagged.
- **P-B rule, hand-computed cases:**
  - Identical partition: KL = 0.
  - Tail cases: reference (0.5, 0.3 | tail 0.2) against engine tails 0.2 and 0.1 match the closed
    form to 1e-15. How the engine spreads its tail mass does not change the coarse KL.
  - A zero reference tail skips the tail term.
  - The complement-LSE tail is correct at an engine tail of 1e-13.
  - His Rust unit vectors pass (`fidelity_rows.rs:203-267`).
  - Clamp: −1e-13 is clamped to 0, −1e-6 raises.
  - Engine tie goes to the lower id while the reference top[0] stays the stored first entry.
  - Non-finite rows are refused.
- **P-B on the real reference** (all 64 files re-hashed):
  - 64 windows, 32,768 positions, 15,104 gen.
  - Windows per bucket 30/16/18; gen rows per bucket 4,035/3,547/7,522. Every bucket label equals
    bucket(score_from).
  - Every gen next-token is in the reference top-1024, with the f32 next_lp equal to that entry
    (95.6% overall; human ctx text 91.8%).
  - Renormalised partitions sum to 1 within 1e-12.
- **P-B end to end** on synthetic engine rows built from the real reference (legacy, a00, c00):
  - `--layout files` and `--layout cuteafd-dump` give identical records.
  - KL < 1e-6, and agree matches an independent tie-aware expectation.
  - Shifted rows are refused (exit 2).
  - `validate_pb records` passes on equal records and fails on a 1e-9 perturbation.
  - `validate_pb rows` reports 100% bit-identical rows.
  - An arm paired with itself gives exactly 0.
- **Q2 end to end:**
  - Per-window KL matches `kl_rows_f64` to 1e-15.
  - A repeat equal to A gives a floor of KL 0, agree 1 and dnll 0, on exactly the windows that have
    a repeat.
  - JS ≤ ln 2. Bootstrap clusters are documents.
- **Plans (real data):**
  - The plan keys are exactly glmf's.
  - glmf's own `probe_spec` turns P-B plan rows into `score_positions` equal to the reference
    positions.
  - glmf's own `collect()` + `write_safetensors()` output and a dump leaf in his byte layout are
    both read back exactly.

**`tests/test_cuteafd_compare.py`: pass.** It builds synthetic paired records on the real P-B
structure and runs his binary (`cuteafd bench fidelity compare B.json A.json --bootstrap 5000 --seed
20260829`, image `392db7c0…`, `--network none`). The port's `cuteafd_compare` matches all of:

- positions, windows, discordant counts, top1_loss, top1_upper95, SE, kl_delta, kl_upper95,
  clustered SE and McNemar p;
- the confident-top-1 and top-3 tripwire metrics.

The maximum |difference| is **8.7e-19** (`tests/cuteafd-compare-check.json`).

**Real-data P-A checks:** see §8 (`selfcheck/pa/`).

## 8. Real-data P-A checks

`selfcheck.sh`, last step: one pass over all 25 windows with two arms, `--jobs 8`. It took **188 s**
of CPU wall time.

| Check | Result |
|---|---|
| **CuteAFD C1 P-A capture, glmf-teacher-kl layout** (`q/rows/pa-C1-rep{1,2}`; `selfcheck/pa-C1-readcheck/`) | Read correctly: `positions` I32 + `logits` F32, plan sha matches `pa.cuteafd-plan.json`, `tokens_sha256` checked on all 25 windows, every window aligned, no errors. The two repeats give identical numbers and a paired ΔKL of 0 with CI [0, 0], as the byte-identical files require. C1 values: KL 0.0475563 (CI [0.03641, 0.06046]), NLL 1.073046 vs teacher 1.062728, top1 0.93153, confident top1 0.98483, top3 0.98951. These are a read check, not the frozen result. |
| **Teacher scored as its own engine** (`selfcheck/pa/pa-teacher.json`) | KL = **0.0 exactly** at all 51,175 rows, CI [0, 0]. `nll` equals `teacher_nll` exactly at every row (NLL 1.062728), so dnll = 0. top1, confident-top1 and top3 are all 1.0. Alignment: offset-0 NLL 1.82 vs 13.7 (−1) and 10.9 (+1) in window 0, and every window passes. |
| **Regression: re-scoring the v0.8.0 K3.25 capture** (`<runs>/kld/glm53-flash-exl3-k3.25@tpurtell+v0.8.0/candidate-logits`, legacy layout) | KL **0.049391187616914654**, bit-identical to that run's `kld.json` (0.049391187616914654). The CI is identical: [0.037778, 0.062449] (same seed and replicates). Per-window means agree within 1.5e-16, since the old file used `k.mean()` and the new one a ratio of sums. Also reported for that capture: NLL 1.078662 vs teacher 1.062728 (dnll +0.0159, CI [0.0075, 0.0261]), top1 0.93192, confident-top1 0.98380 (CI [0.97877, 0.98805], 79.5% of rows confident), top3 0.98904. |
| **Teacher top-1 ties** | **918 of 51,175 rows (1.8%)** have tied BF16 teacher maxima. For those rows, top-1 agreement depends on the tie rule; ours is lower id on both sides. This is reported as `teacher_top1_ties`. |

Estimated P-B cost (not measured at full scale): about 32,768 rows per arm, about 2-4 min CPU
with `--jobs 8`.

## 9. Commands after capture

```bash
cd <run>/stage0/scorers; PY="<venv>/bin/python -B"
RUN=<run>/<capture-run>
# P-A, each arm captured twice (noise floor); one pass reads the teacher once for all arms
$PY score_pa.py score --arm C1=$RUN/pa/C1-1 --arm C1r=$RUN/pa/C1-2 --arm V1=$RUN/pa/V1-1 --arm V1r=$RUN/pa/V1-2 \
  --pair C1,C1r --pair V1,V1r --pair V1,C1 --out $RUN/score/pa --jobs 8
# P-B: CuteAFD from the CLI dump (validated first, §6); vLLM from the plugin's <window_id>.safetensors
$PY score_pb.py score --engine <DUMP_ROOT>/pb-cli-prefill --layout cuteafd-dump --arm C1 --out $RUN/score/pb
$PY score_pb.py score --engine $RUN/pb/V1-1 --arm V1 --out $RUN/score/pb
$PY score_pb.py score --engine $RUN/pb/V1-2 --arm V1r --out $RUN/score/pb
$PY score_pb.py pair --a $RUN/score/pb/pb-V1.rows.npz --b $RUN/score/pb/pb-C1.rows.npz --out $RUN/score/pb/pb-pair-V1-C1.json
$PY score_pb.py pair --a $RUN/score/pb/pb-V1.rows.npz --b $RUN/score/pb/pb-V1r.rows.npz --out $RUN/score/pb/pb-pair-V1-V1r.json
# Q2
$PY score_q2.py --plans plans --a C1=$RUN/q2/C1-1 --b V1=$RUN/q2/V1-1 \
  --a-repeat $RUN/q2/C1-2 --b-repeat $RUN/q2/V1-2 --out $RUN/score/q2
```

- **Exit codes.** Every scorer exits non-zero on an alignment failure, non-finite rows, row or plan
  mismatch, or a token-hash mismatch.
- **Within-engine floor.** Read between-arm differences against the C1-vs-C1r and V1-vs-V1r pairs.
- **Scoring cost:**
  - P-A: about 1.3 GB per window per arm read from disk.
  - P-B: 20.3 GB per arm (F32).
  - Q2: 4,096 × 154,880 × 4 B ≈ 2.5 GB per window per arm. That is 46 GB per arm for 18 windows,
    92 GB with repeats.

## 10. Caveats and open items

- **P-B geometry.** CuteAFD P-B rows taken from glmf-teacher-kl.py are a different geometry from
  his CLI (§2). The recommendation is to use the CLI dump.
- **The engine shapes still differ:**
  - vLLM chunks prefill at 2,048 (2,045 + 3 with DFlash).
  - CuteAFD prefills the prefix, then runs the 511 remaining scored rows in one chunk.

  These are recorded, not forced (protocol principle).
- **Q2 protocol text** says top-20 KL; this scorer uses full-vocabulary KL (§5). That needs an
  amendment.
- **Q2 needs CuteAFD to accept 128K-token `prompt_ids`.** This is not checked here. The 64 MiB body
  limit is fine (about 1 MB of JSON).
- **Not comparable across panels.** P-A KL is full-vocabulary against a BF16 teacher on
  brandonmusic text. P-B KL is the coarse top-1024+tail, on FP8-generated text plus human context.
  Q2 has no teacher. NLL is per tokenizer and per text in each.
- **vLLM plugin output** must follow §1: a `rows` tensor, and BF16 logits or F32 log-probs.
