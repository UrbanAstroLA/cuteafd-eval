# Addendum: distance from the BF16 model for the four configurations

Written 2026-11-11, before any request of this stage. It adds a measurement to the context probe; it changes
nothing in `protocol/PROTOCOL.md` or `protocol/AMENDMENT-2026-11-11.md` and is not part of the frozen task comparison.

## What it answers

How far each of the four configurations sits from the unquantized BF16 model, on reference sets that hold BF16
outputs. The scoring capture of this run compared the arms with each other and with the text; neither is a distance
from BF16.

## Arms

`anchor`, `hqa`, `compact`, `exlr8-k4`, launched exactly as in `chain.sh` (`arm_cfg`, score form: the serve
configuration plus `ENABLE_BENCH`, `API_KEY_FILE`, `FULL_PREFILL_LOGITS=on`, a dump root, prefix cache off).
One engine at a time on 127.0.0.1:8001. No sampling is involved: the engine scores fixed token ids, so there are
no seeds and no thinking setting.

## Reference sets

| | P-A (teacher panel) | P-B (fidelity set) |
|---|---|---|
| Source | published BF16 teacher logits for GLM 5.3 Flash | the engine author's published fidelity set, config `glm5_flash-v2_20261005_bf16root`, revision `a7e7d1b4d82329acebe54ca88dc71d47d0d2056d` |
| Size | 25 windows x 2,048 tokens (2,047 scored rows each) | 64 windows x 512 scored positions |
| Reference holds | full vocabulary (154,880 ids) | top 1,024 ids plus tail mass |
| Context length | 2K | up to 14.4K; buckets 0-2K, 2-8K, 8-16K |
| Plan | `pa.cuteafd-plan.json` sha256 `c7977da1...d7165` | the CLI's own full tier; fallback plan `pb.cuteafd-plan.json` sha256 `505033ea...dc92` |

Neither set reaches past 14.4K. The run's task lengths of 64K and 128K have no BF16 reference here.

## Capture

Round r0, one launch per arm, order `exlr8-k4`, `anchor`, `hqa`, `compact`:

1. **P-A, full vocabulary.** `scripts/bench/glmf-teacher-kl.py --plan pa.cuteafd-plan.json --path prefill`
   (`POST /v1/bench/probe`, cold, no speculation, `score_from` 1). F32 log-probabilities for every scored row.
2. **P-B, the author's rule.** In the coordinator: `cuteafd bench fidelity run --tier full --score-path prefill
   --dataset-config ... --dataset-revision ... --dump-dir ...`. The CLI scores with its own rule and keeps a
   full-vocabulary F32 dump of every scored row.
3. **Fallback.** If the CLI does not accept an arm, that arm and every arm after it also capture P-B through
   `glmf-teacher-kl.py` with `pb.cuteafd-plan.json`. That is a different capture geometry (`score_from` 1: the
   whole window runs through the scoring path, where the CLI prefills the context ordinarily and scores only
   the 512 rows). Results from the two geometries are labelled and never mixed in one column.

Round r1, a separate launch of each arm: P-B again by the route(s) that completed in r0. This is the
launch-to-launch repeat.

Scoring uses the prefill path only. The decode path is not captured in this stage.

## Scoring (CPU, after the engine is stopped)

- **P-A:** `score_pa.py` as used since 2026-10-26: per row KL(teacher || engine) over all ids in float64, NLL of
  the next token, top-1 agreement with the teacher; mean over rows with a window bootstrap (20,000 replicates,
  the scorer's default seed). Paired differences between arms on the same rows from the same scorer.
- **P-B:** two figures per arm and round. (a) The CLI's own result as it reports it. (b) `score_pb.py`, the
  float64 port of the author's rule on the kept dump: ratio-of-sums over `gen`-role rows, window-block bootstrap
  (SplitMix64, seed 20260829, 5,000 replicates), overall and by bucket. `validate_pb.py records` compares (a)
  and (b) record by record; the port was written against v3.0.1, so a mismatch is reported, not corrected.
- **Repeat:** r1 against r0 per arm, same scorer: difference in mean KL and the largest per-window difference.

## What is reported

One table, KL from BF16 per arm: P-B overall and by bucket with intervals, P-A beside it, and the r0-r1
difference as the floor. Paired arm differences with intervals (six pairs per panel). Beside the table, as
context and marked as not measured in this stage: the published figure for the official FP8 release on the
fidelity set, and this repository's earlier BF16-referenced figures for other checkpoints.

Status: descriptive. No gate, no ranking rule. Every interval computed is listed; none is selected.

## Limits known before the first request

- P-A is drawn from the corpus the K4 producer published and can favour K4 experts. `anchor`, `hqa` and
  `compact` all carry K4 experts; `exlr8-k4` does not carry those experts.
- The two panels use different measures (full-vocabulary KL; top-1,024-plus-tail KL) and are not comparable
  with each other.
- `anchor` is a BF16 core with quantized experts. Its distance from BF16 is the experts' quantization plus the
  engine's numerics, not zero.
- One engine build (v5.0.0), one checkpoint revision per arm, one launch-to-launch repeat.

## Stops

A launch that does not come up is logged and skipped. A capture that exits non-zero is logged; the stage goes on
to the next step. Every exit path stops the engine, shreds the bench key, restores the machine's usual serving setup and checks it
by request. Needs 450 GB free under the run's dump root before starting, otherwise it does not start.

## Kept and removable

Kept: the CLI JSON, P-A and P-B score files and row tables. Removable after scoring (listed for removal
by hand): the full-vocabulary P-A row files and the P-B dump directories.
