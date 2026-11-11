# CuteAFD v5.0.0 core precision at long context (2026-11-10/11)

CuteAFD v5.0.0 adds a checkpoint that carries BF16 copies of two attention projection groups beside the K6 ones, and
`ATTENTION_MODE` to choose between them. This run asks what that precision buys as context grows: three arms that differ in the
precision of the tensors outside the experts (the core and, for `anchor`, the output head) answer the same 60 synthetic items at 4K, 16K, 64K and 127K tokens, as a single message (two passes)
and delivered over eight turns (one pass). K4 experts and the same drafter in every arm, so nothing here measures expert
quantisation. Site page: [CuteAFD v5](../../docs/v5.html).

| arm | what runs | checkpoint |
|---|---|---|
| `anchor` | every core matrix and the output head at original precision (BF16), FP8 conversions off: the reference, not a recommendation | locally derived BF16-core checkpoint (not a producer release) |
| `hqa` | BF16 `q_b_proj` and `o_proj`, rest of the core and the head K6 | K4-Core-K6-HQA, default mode |
| `compact` | K6 core and head | the same checkpoint, `ATTENTION_MODE=compact` |

**Checkpoint availability.** `hqa` and `compact` load `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6-HQA @ e0ecc3d55d117e656a03d5790521cad0c4fcb624`: K4 experts, K6 core and head, and BF16 copies of two attention projection groups (q_b_proj, 12 matrices; o_proj, 46) beside the K6 ones; ATTENTION_MODE selects which copies run.
The K4-Core-K6-HQA repository is no longer available on the hub (checked 2026-11-11). These runs used a local copy downloaded on 2026-11-10. The anchor checkpoint is derived locally and was never a hub release.

**Scope of the eight-turn pass.** Decode ran in every reply of every pass. What the 8-turn pass did not exercise is history written by decode: the model's own turns (thinking included, which stays in context) are a median 9% of the final prompt at 4K, 2.7% at 16K, 0.7% at 64K and 0.3-0.4% at 127K, so at long context more than 99% of the history the final answer was conditioned on was written by prefill. The pass measures split delivery of the same input. It does not test a conversation whose history the model wrote (protocol question 3). The turn design is to be revised.

- `RESULTS.md`: the result as read, with its corrections dated. `SUMMARY.json`: the numbers of the page's tables, the launch facts
  (weights, memory admission, KV pool) and the estimators in words; the figures of the exploratory checks are in the protocol text.
- `protocol/`: the protocol as frozen and `FROZEN.json` (hashes of the protocol, item index and drivers at the freeze). The
  published protocol differs from the hashed file by path placeholders and a few wording edits (local tool names, scheduling);
  its line "Results stay local" was written before the decision of 2026-11-11 to publish. Sections 10 to 13 report the
  exploratory checks that came first (start check; depth profile, which includes the FP8 prefill switch and the launch-to-launch
  comparison; turn check, the page's "cache path"; repeat check, the page's "batching"; pilot); their numbers are in the
  protocol text and are not measurements.
- `analysis/`: `samples.csv` (one row per request, 7,920 rows: arm, pass, cell, item, family, length, rep, turn, final, seed,
  status, finish class, fields, fields correct, prompt, completion and cached tokens, thinking and content characters, time to
  first token, decode speed, and for delivery turns `ack_ok`, 1 when the reply was the requested acknowledgement; no text), `make_samples.py`, and
  `posthoc.py`, which recomputes the scores, differences and intervals of `RESULTS.md` from the CSV into `POSTHOC.json`
  (`python3 analysis/posthoc.py`, standard library only). Launch figures come from the launch logs and the left-out counts from
  reply values; neither is in the CSV.
- `tasks/`: the frozen analysis output (`drivers/analyze_tasks.py summary|compare`): one summary per arm and one comparison
  per pair.
- `exploratory/`: wrong `ledger` fields by kind of arithmetic slip (a heuristic reading). `notes/`: the extension that was
  written before the data and is held.
- `drivers/`: generator, request driver, analysis and the exploratory check drivers. `items/measured/index.json`: the item
  index (seeds, token counts and hashes). The item texts are not stored here; `drivers/gen_tasks.py` regenerates them from
  the index parameters and the tokenizer.
- `chain.sh`, `turncheck-plan.sh`, `configs/`: how each arm was launched (local paths as placeholders).

## Reproducing this

1. **Recompute.** `python3 analysis/posthoc.py` (standard library only) rebuilds the scores, differences and intervals from
   `analysis/samples.csv` and writes `analysis/POSTHOC.json`; `python3 tools/verify.py` at the repository root checks
   `docs/findings.json` against the same table. Run from a clean copy of this folder on 2026-11-11: same output.
2. **Rebuild the inputs.** `python3 drivers/gen_tasks.py --out <dir> --items 20 --first 100` regenerates the 240 rendered
   items from their seeds. It needs the `tokenizers` package and the model's `tokenizer.json` (set `TOKENIZER` at the top of the
   script; its SHA-256 is checked). Compare `content_sha256` and `file_sha256` with `items/measured/index.json`. Regenerated
   from the published script on 2026-11-11: 240 of 240 match.
3. **Re-measure.** `chain.sh`, `drivers/run_tasks.py` and `configs/` are what ran; the image digest and checkpoint revisions
   are in `RUN.json`. The HQA checkpoint is no longer on the hub, so `hqa` and `compact` cannot be re-measured without a copy
   of it; `anchor`'s checkpoint is assembled locally, with every core matrix taken from the original BF16 weights, and was
   never a release. The items and the scoring do not depend on the engine.

Not published: reply and reasoning texts and the values replies gave (model output), per-request receipts, launch logs, and
the full-vocabulary dumps and receipts of the exploratory checks.
