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

**Reference checkpoint, added after the results were read.** `exlr8-k4` (`kindlingai/glm-5.3-flash-exlr8-k2-k3-k4 @ 867580abd28d142bb4c56218bb81a752b7dea988, manifest k4`) ran the two single-message passes on
2026-11-11: 480 requests, 0 errors, prompt tokens equal to `anchor`'s on 480 of 480. exlr8-k4 is a different checkpoint from the three probe arms, not a setting of the same one. Any difference from a probe arm is a whole-checkpoint difference and is not attributable to one component.
It is outside the frozen comparison and its intervals are post hoc; `anchor` stays the reference of the probe, not a
recommendation. The engine loads a native EXLR8 checkpoint from a content-addressed store; for these launches the store (SparkNest v0.8.3, one node) ran on the same host and was mounted there. Upstream's status note says bundled vision and full prefix-continuation exactness are not yet qualified for this checkpoint, which is why it is run single-message only here.
A scoring capture on it (exploratory, one capture) is read beside the same capture of the three probe arms. Sections 9 and 10
of `RESULTS.md`.

**Amendment 1 (2026-11-11 16:46).** `protocol/AMENDMENT-2026-11-11.md` (sha256 c3487e41a0194ed57ba968bda809ab8b160d810a02a19b106ec26fe86101d9f8), written after the two-pass results were
read and before the first request of the passes it adds, adds single-message passes 3 and 4 for the four arms. They ran
2026-11-11 17:02 to 2026-11-12 03:59: 1,920 requests, 0 errors. Section 11 of `RESULTS.md` reads all four passes with the frozen
comparison rule; the two-pass tables stay as the result of the frozen protocol.

**Distance from the BF16 model (2026-11-12).** A separate stage scored each of the four configurations against BF16 outputs on
two reference sets: the engine author's published fidelity set (contexts to 14.4K; coarse KL) and a panel of published BF16
teacher logits (2K windows; full-vocabulary KL). Its plan, `bf16ref/ADDENDUM-BF16REF.md`, was written before its first request
and is descriptive: no gate, no ranking rule, every interval listed. Neither set reaches the 64K and 127K lengths of the task
runs. Section 12 of `RESULTS.md`; section 13 puts cost and measured quality side by side.

**How the replies ended (2026-11-12, post hoc).** Section 14 of `RESULTS.md` counts how each of the 3,840 replies of the four
passes ended and what the reasoning of the 44 unfinished ones was made of. `compact`'s lower score at 127K is `join` replies
that did not finish (10 of 80 against 4, 2 and 1), an ending every arm shows, `anchor` included; where
`compact` answered it was as right as the others. Whether the K6 projections raise the rate of that ending is indicated, not
established. The classification was written after the four-pass results were read.

**Bits per weight, and a fifth configuration (2026-11-12).** Section 15 of `RESULTS.md` puts the checkpoints on one unit,
bits per weight counted from the checkpoint files, whole model and by component, with a short primer on the formats. It
includes `k325-fp8` (`wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-Core-FP8 @ d31ebc921f1f098b4a56d37aaccb3cdef4096184`: EXL3 routed experts at K3.25 with, as the engine runs it by default, FP8 attention, dense and shared-expert blocks (as stored, the files hold part of the attention, the output head and the embedding at BF16); the checkpoint of the engine's own starting config for two RTX cards), which amendment 2 (`protocol/AMENDMENT-2026-11-12.md`, written
2026-11-12 11:57:02 -0800 before its first request) adds as a fifth configuration with four single-message passes. The published amendment differs from the file as written
(sha256 9d90da18dede0283fff10c34277a59997f3d0effdb2564b362bb57db53521449) by a path placeholder; its stage script, like the BF16-reference stage's launcher, is not published.

**Amendment 2: `k325-fp8`, four passes and distance from BF16 (2026-11-12).** Section 16 of `RESULTS.md`. The four passes ran
11:58 to 16:54, one launch per pass: 960 requests, 0 errors, prompt tokens and seeds equal to `anchor`'s on 960 of 960. Read by
the frozen rule beside the other four, `k325-fp8` is level with them to 16K. At 127K it scores 0.867 against
0.918, 0.924 and 0.920 for `anchor`, `hqa` and `exlr8-k4` (the three paired intervals exclude 0) and
0.887 for `compact` (the interval includes 0). Most of that gap is `join` replies that did not finish (11 of 80), the
ending section 14 describes. Against BF16 it is farther than each of the four on both reference sets (fidelity set
0.0485 against 0.0302 to 0.0360; teacher panel 0.0476 against 0.0297 to 0.0320; contexts to 14.4K) and passes the
engine's fidelity gate. Its files hold 3.55 bits per weight against 4.08 to 4.35. `k325-fp8` differs from every other arm in the whole checkpoint: K3.25 routed experts where the others' are 4-bit, and its own tensors outside them. No difference from another arm is attributable to one component. Its four passes ran alone on 2026-11-12, after the other arms' and not interleaved with them, so a session effect cannot be excluded by design. No
direction was predicted. The four earlier arms' tables are unchanged.

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
  reply values; neither is in the CSV. For the reference checkpoint: `samples-reference.csv` (480 rows, the same columns),
  `make_samples_reference.py`, and `reference.py`, which recomputes section 9 of `RESULTS.md` from the two CSVs into
  `REFERENCE.json` (`python3 analysis/reference.py`, standard library only). For amendment 1: `samples-extension.csv` (1,920
  rows, passes 3 and 4 of the four arms, the same columns), `make_samples_extension.py`, and `fourpass.py`, which recomputes
  section 11 of `RESULTS.md` from the three CSVs into `FOURPASS.json` (`python3 analysis/fourpass.py`, standard library only).
  For section 14: `endings.csv` (3,840 rows, one per reply of the four passes: counts of lines and characters of the
  reasoning, of the lines that carry the next record of the prompt, of repeated lines, where a run of such lines starts and
  how many of the item's correct answers occur before it; no text), `make_endings.py`, which made it from the saved replies and
  so documents the computation without rerunning from this folder, and `endings.py`, which recomputes section 14 from the four
  CSVs into `ENDINGS.json` (`python3 analysis/endings.py`, standard library only). For section 15: `bpw.py`, which reads the
  headers of checkpoint files and writes `BPW.json` (`python3 analysis/bpw.py ARM=SNAPSHOT_DIR ...`, standard library only; it
  needs a local copy of each checkpoint and loads no weight). For section 16: `samples-amend2.csv` (960 rows, the four passes
  of `k325-fp8`, the columns of `samples.csv`) and `endings-amend2.csv` (960 rows, the columns of `endings.csv`), the two
  scripts that made them from the saved replies (`make_samples_amend2.py`, `make_endings_amend2.py`; they document the
  computation and do not rerun from this folder), and `amend2.py`, which recomputes the task figures of section 16 from the
  six CSVs into `AMEND2.json` and requires its figures for the four earlier arms to equal `FOURPASS.json` and `ENDINGS.json`
  (`python3 analysis/amend2.py`, standard library only).
- `bf16ref/`: `ADDENDUM-BF16REF.md`, the plan of the BF16-reference stage, and `FROZEN.json`, its hashes at the freeze. The
  hashes are of the files as they were on the measuring machine: the published plan differs from the hashed one by a few
  wording edits (file locations, the machine's usual serving setup), and the scorers it names are published, with path
  placeholders, under `repro/stage0/scorers/`. The stage's launcher script, the two capture plans and the engine author's
  capture script are hashed there and not published. `BF16REF.json`: the numbers of section 12 of `RESULTS.md` (per
  configuration and per pair, both sets, with the estimators in words, the repeat and the port-against-CLI check), and per
  window the positions and each configuration's mean KL, from which every fidelity-set value and interval can be recomputed.
  `BF16REF-AMEND2.json`: the same for `k325-fp8` (section 16), measured later the same day under amendment 2 with the same
  plans and scorers, with its per-window figures.
- `tasks/`: the frozen analysis output (`drivers/analyze_tasks.py summary|compare`): one summary per arm and one comparison
  per pair.
- `exploratory/`: wrong `ledger` fields by kind of arithmetic slip (a heuristic reading); `capture_pairs.json` and
  `capture_abs.json`, the numbers of the scoring capture (section 10 of `RESULTS.md`), with the scripts that wrote them. Those
  two scripts read dumps and per-row files that are not published, so they document the computation and do not rerun from
  this folder. `notes/`: the extension that was written before the data and is held.
- `drivers/`: generator, request driver, analysis and the exploratory check drivers. `items/measured/index.json`: the item
  index (seeds, token counts and hashes). The item texts are not stored here; `drivers/gen_tasks.py` regenerates them from
  the index parameters and the tokenizer.
- `chain.sh`, `turncheck-plan.sh`, `configs/`: how each arm was launched (local paths as placeholders). `chain.sh` is the
  file as it stands, with the arm definition amendment 2 added.

## Reproducing this

1. **Recompute.** `python3 analysis/posthoc.py` (standard library only) rebuilds the scores, differences and intervals from
   `analysis/samples.csv` and writes `analysis/POSTHOC.json`; `python3 tools/verify.py` at the repository root checks
   `docs/findings.json` against the same table. Run from a clean copy of this folder on 2026-11-11: same output.
   `python3 analysis/reference.py` does the same for the reference checkpoint, from the two CSVs into `analysis/REFERENCE.json`,
   and `python3 analysis/fourpass.py` for the four-pass reading, from the three CSVs into `analysis/FOURPASS.json` (the export
   reruns it on the published copies and requires the published file), and `python3 analysis/endings.py` for section 14,
   from the four CSVs into `analysis/ENDINGS.json` (rerun by the export in the same way), and `python3 analysis/amend2.py`
   for the task figures of section 16, into `analysis/AMEND2.json` (rerun by the export in the same way). The fidelity-set figures of `bf16ref/BF16REF.json`
   follow from its per-window table; `tools/verify.py` recomputes the ones `docs/findings.json` cites.
2. **Rebuild the inputs.** `python3 drivers/gen_tasks.py --out <dir> --items 20 --first 100` regenerates the 240 rendered
   items from their seeds. It needs the `tokenizers` package and the model's `tokenizer.json` (set `TOKENIZER` at the top of the
   script; its SHA-256 is checked). Compare `content_sha256` and `file_sha256` with `items/measured/index.json`. Regenerated
   from the published script on 2026-11-11: 240 of 240 match.
3. **Re-measure.** `chain.sh`, `drivers/run_tasks.py` and `configs/` are what ran; the image digest and checkpoint revisions
   are in `RUN.json`. The HQA checkpoint is no longer on the hub, so `hqa` and `compact` cannot be re-measured without a copy
   of it; `anchor`'s checkpoint is assembled locally, with every core matrix taken from the original BF16 weights, and was
   never a release. `exlr8-k4` loads a public checkpoint (revision in `RUN.json`, `configs/glm53-flash-exlr8-k4-2rtx.config`).
   The items and the scoring do not depend on the engine.

Not published: reply and reasoning texts and the values replies gave (model output), per-request receipts, launch logs, and
the full-vocabulary dumps and receipts of the exploratory checks and of the scoring capture. Of the BF16-reference stage:
its dumps, per-row tables and score files (their numbers are in `bf16ref/BF16REF.json`), and its launcher script.
