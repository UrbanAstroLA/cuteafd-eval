# Graded task runs: results (measured set, frozen protocol)

Run under `protocol/PROTOCOL.md` as frozen 2026-11-10 19:55 (`protocol/FROZEN.json`); amendments: none. Chain: 2026-11-10 19:55 to
2026-11-11 08:28, nine units, every unit exit 0. Per-request receipts hold reply text and are not published; `analysis/samples.csv` carries their fields. Tables below are the output of
`drivers/analyze_tasks.py summary|compare --set measured`; the `ledger`-only section is an added exploratory
reading (`exploratory/ledger_errors.py`), not part of the frozen protocol. `analysis/posthoc.py` recomputes every
number here from `analysis/samples.csv` (one row per request, no text). Published 2026-11-11; the protocol's line
"results stay local" was written before that decision.

One engine (CuteAFD v5.0.0), one model family (GLM 5.3 Flash), K4 experts and the same drafter in every arm, so
nothing here measures expert quantisation. Arms differ in the precision of the tensors outside the experts: the core and,
for `anchor`, the output head, which it keeps at BF16 (PROTOCOL section 2):
`anchor` = every core matrix at original precision, FP8 conversions off (the reference, not a recommendation);
`hqa` = BF16 `q_b_proj` + `o_proj`, rest K6; `compact` = K6 core. Synthetic items; scores are not comparable with
any other model family or fixture.

**Checkpoint availability (2026-11-11).** `hqa` and `compact` load
`wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6-HQA` at revision e0ecc3d55d117e656a03d5790521cad0c4fcb624: K4
experts, K6 core and head, and BF16 copies of two attention projection groups (`q_b_proj`, 12 matrices, and
`o_proj`, 46) beside the K6 ones; `ATTENTION_MODE` selects which copies run. That repository is no longer
available on the hub (checked 2026-11-11). These runs used a local copy downloaded on 2026-11-10. `anchor` is a
locally derived checkpoint and was never a hub release.

## 1. Score by length (share of answer fields right; unfinished replies score 0)

Single message, two passes pooled (60 items, 120 requests per length):

| arm | weights GiB | KV pool | 4K | 16K | 64K | 127K | unfinished at 127K (cap/loop) |
|---|---|---|---|---|---|---|---|
| anchor | 6.21 | 2.10M | 0.983 | 0.977 | 0.956 | 0.903 | 4/1 of 120 |
| hqa | 4.50 | 2.10M | 0.981 | 0.982 | 0.944 | 0.912 | 2/1 of 120 |
| compact | 3.24 | 2.10M | 0.984 | 0.975 | 0.932 | 0.890 | 4/1 of 120 |

Weights: coordinator weights as the load line reports them. KV pool: as admitted in these nine serving launches
(2,097,152 tokens, the configured maximum, in every arm). Corrected 2026-11-11: this table first gave `anchor`
1.32M, which is its pool in the scoring launches of layer 1 (concurrency 16; PROTOCOL section 12), not here.

Every field right: anchor 0.88 / 0.83 / 0.78 / 0.68; hqa 0.88 / 0.88 / 0.73 / 0.67; compact 0.88 / 0.82 / 0.70 / 0.62.

Eight turns, one pass (60 items per length):

| arm | 4K | 16K | 64K | 127K |
|---|---|---|---|---|
| anchor | 0.996 | 0.967 | 0.948 | 0.902 |
| hqa | 0.996 | 0.979 | 0.927 | 0.925 |
| compact | 0.992 | 0.973 | 0.927 | 0.931 |

## 2. Paired differences (item as the unit, 95% interval from resampling items)

Single message, two passes:

| difference | 4K | 16K | 64K | 127K | all lengths |
|---|---|---|---|---|---|
| hqa - anchor | -0.002 [-0.014, +0.008] | +0.005 [-0.004, +0.015] | -0.013 [-0.046, +0.018] | +0.009 [-0.026, +0.047] | +0.000 [-0.012, +0.012] |
| compact - anchor | +0.001 [-0.008, +0.011] | -0.002 [-0.010, +0.006] | -0.024 [-0.056, +0.004] | -0.014 [-0.069, +0.041] | -0.010 [-0.026, +0.006] |
| hqa - compact | -0.003 [-0.015, +0.007] | +0.007 [-0.004, +0.019] | +0.011 [-0.014, +0.040] | +0.023 [-0.026, +0.073] | +0.010 [-0.005, +0.025] |

Eight turns, all lengths: hqa - anchor +0.004 [-0.023, +0.032]; compact - anchor +0.003 [-0.027, +0.033];
hqa - compact +0.001 [-0.027, +0.028].

Every-field-right outcome, share of the 240 requests that change:

| comparison | pass 1 | pass 2 |
|---|---|---|
| same arm, pass 1 against pass 2 (the floor) | anchor 0.229, hqa 0.229, compact 0.246 | |
| hqa against anchor | 0.192 (p 0.10) | 0.233 (p 0.14) |
| compact against anchor | 0.204 (p 1.0) | 0.221 (p 0.053) |
| hqa against compact | 0.179 (p 0.066) | 0.229 (p 0.79) |

Changing the arm changes no more outcomes than rerunning the same arm with new seeds. Pass 1 alone showed `hqa`
ahead of both by about 0.02; pass 2 did not repeat it.

## 3. Turns against single message (same items)

| arm | 4K | 16K | 64K | 127K |
|---|---|---|---|---|
| anchor | +0.013 [+0.002, +0.024] | -0.010 [-0.050, +0.017] | -0.008 [-0.066, +0.037] | -0.001 [-0.070, +0.060] |
| hqa | +0.015 [+0.003, +0.027] | -0.003 [-0.017, +0.009] | -0.017 [-0.074, +0.030] | +0.013 [-0.047, +0.065] |
| compact | +0.007 [-0.004, +0.019] | -0.002 [-0.040, +0.024] | -0.005 [-0.067, +0.048] | +0.042 [-0.021, +0.100] |

No penalty for splitting the input over eight messages, in any arm. **Scope of this pass (added 2026-11-11):** the
model's own turns (thinking included, which stays in context) are a median 9% of the final prompt at 4K, 2.7% at
16K, 0.7% at 64K and 0.3-0.4% at 127K. At long context more than 99% of the history was written by prefill, so
this pass is close to a third single-message pass with turn boundaries. It does not test a conversation whose
history the model wrote (protocol question 3), and "no turn penalty" must not be read that way.

Delivery turns whose reply was not the bare acknowledgement: anchor 4, hqa 6, compact 17, of 1,920 turns in 240
sessions each. Four in each arm finished on their own; the rest ran to the 4,096 cap: anchor 0, hqa 2 turns in 2
sessions, compact 13 turns in 8 sessions (six of them in one 127K `ledger` session). Descriptive only; the final answers of
those sessions were scored as usual.

## 4. By family (single message, two passes; field score, then every field right of 40)

| family | arm | 4K | 16K | 64K | 127K |
|---|---|---|---|---|---|
| join | anchor | 0.997 (39) | 0.991 (37) | 0.997 (39) | 0.897 (35) |
| join | hqa | 0.997 (39) | 0.994 (38) | 0.994 (38) | 0.947 (37) |
| join | compact | 0.997 (39) | 0.991 (37) | 0.997 (39) | 0.912 (33) |
| ledger | anchor | 0.978 (34) | 0.966 (31) | 0.891 (19) | 0.847 (14) |
| ledger | hqa | 0.981 (35) | 0.975 (33) | 0.850 (14) | 0.841 (14) |
| ledger | compact | 0.975 (32) | 0.963 (31) | 0.825 (12) | 0.787 (10) |
| trace | anchor | 0.975 (32) | 0.975 (32) | 0.981 (35) | 0.966 (32) |
| trace | hqa | 0.966 (32) | 0.978 (34) | 0.988 (36) | 0.950 (29) |
| trace | compact | 0.981 (34) | 0.972 (31) | 0.975 (33) | 0.969 (32) |

A pooled null is not a `ledger` null (PROTOCOL section 13), so `ledger` is read on its own below.

## 5. `ledger` alone (exploratory)

Paired difference in field score, 20 items, single message, two passes:

| difference | 4K | 16K | 64K | 127K |
|---|---|---|---|---|
| hqa - anchor | +0.003 [-0.019, +0.022] | +0.009 [-0.009, +0.031] | -0.041 [-0.138, +0.047] | -0.006 [-0.050, +0.037] |
| compact - anchor | -0.003 [-0.025, +0.019] | -0.003 [-0.022, +0.016] | -0.066 [-0.153, +0.013] | -0.059 [-0.147, +0.034] |
| compact - hqa | -0.006 [-0.022, +0.006] | -0.013 [-0.037, +0.009] | -0.025 [-0.103, +0.044] | -0.053 [-0.153, +0.044] |

Wrong fields that match "one or two of the bin's events left out", stop-finished replies, 64K + 127K:

| arm | pass 1 | pass 2 | 8 turns |
|---|---|---|---|
| anchor | 17 | 16 | 9 |
| hqa | 16 | 17 | 9 |
| compact | 17 | 25 | 13 |

All wrong fields at 64K + 127K, single message, two passes: anchor 68 of 624 finished fields, hqa 75 of 616,
compact 92 of 608. Left-out events are about half of the wrong fields in every arm. The classifier is a heuristic
(a wrong value can match a class by coincidence).

`compact` is nominally about 0.06 below `anchor` on `ledger` at 64K and 127K, with intervals that include zero.
Its left-out-event count differs between its own two passes (17, 25) by as much as it differs from the other arms,
so that reading is inside the floor.

**Extension trigger** (`notes/ledger-extension-hold.md`, written before the measured data): met on its first
condition. `compact - anchor` at 64K and at 127K, and `hqa - anchor` at 64K, have intervals that include both zero
and a loss of 0.10 or more. Twenty `ledger` items cannot tell "K6 core costs nothing on running totals at long
context" from "it costs up to 0.15" at a single length (pooled over 64K and 127K: about 0.13 in field score). The second condition (left-out events beyond the two-pass floor) is not met.
The extension is held: not run.

## 6. Descriptive (single message, two passes)

| arm | thinking chars (median) 4K / 16K / 64K / 127K | output tokens | tok/s per stream | first token s |
|---|---|---|---|---|
| anchor | 7289 / 7266 / 8714 / 11366 | 3344 / 3700 / 4162 / 5518 | 40.5 / 36.6 / 37.7 / 40.5 | 0.7 / 2.8 / 11.1 / 21.8 |
| hqa | 6538 / 6888 / 8966 / 9636 | 3061 / 3808 / 4671 / 4834 | 34.4 / 32.3 / 34.7 / 35.4 | 0.8 / 3.2 / 12.7 / 25.1 |
| compact | 6657 / 7697 / 8478 / 9786 | 3030 / 3664 / 4462 / 5276 | 36.7 / 33.0 / 33.7 / 36.9 | 0.8 / 3.2 / 12.9 / 25.5 |

Speeds are per stream under a mixed concurrency-8 load and are confounded with what else was in the batch; they
are not an arm comparison. Evidence position: accuracy by position bin stays within about 0.05 at every length in
every arm; the [0.10-0.25] bin is the lowest of the three at 64K and 127K in every arm.

## 7. What this decides

- **Accuracy falls with length in every probe arm, `anchor` included** (0.98 at 4K to about 0.90 at 127K). On
  these tasks the long-context loss is not produced by core tensor precision. A third to a half of it is replies that
  did not finish (finished-only score at 127K: 0.942 / 0.936 / 0.928 for anchor / hqa / compact; added 2026-11-11). The
  rest sits in something the arms share: the model, the K4 experts, the engine, the drafter, the sampling settings or
  the reply cap.
- **`hqa` against `anchor`: no difference measured**, +0.000 [-0.012, +0.012] pooled; a loss larger than about 0.012 pooled
  is excluded.
- **`compact` against `anchor`: no difference measured**, -0.010 [-0.026, +0.006] pooled; a pooled loss larger than
  about 0.026 is excluded. Its largest nominal gap is `ledger` at 64K and 127K, undecided at 20 items; `hqa` is nominally lower there too
  (-0.023 [-0.073, +0.023] pooled over the two lengths).
- **`hqa` against `compact`: no difference measured**, +0.010 [-0.005, +0.025].
- **No penalty for split input in any arm.** The rule written in advance reads this as "turn check v2 not needed". Read
  against the scope note in section 3 (2026-11-11), the 8-turn design did not test the turn question: decode ran in
  every reply, but almost none of the history the final answer was conditioned on was written by decode. That
  conclusion is withdrawn and the turn design is to be revised.
- **`trace` at 127K is level across arms** (0.966 / 0.950 / 0.969): the collapse-row test stays parked.
- **No arm separated from `anchor`**: the conditional `fp8c` and `core-fp8` task runs are not triggered.
- What the cheaper arms buy: 4.50 or 3.24 GiB of coordinator weights against 6.21. In these serving launches
  every arm was admitted the maximum KV pool (2,097,152 tokens), so on this hardware the saving is memory headroom
  (resident weights per GPU 83,129 / 82,897 MiB for `anchor`, 81,827 / 79,931 for `hqa`, 80,543 / 78,647 for
  `compact`), not pool size. A smaller pool for `anchor` (1,318,400 tokens) was seen only in the
  concurrency-16 scoring launches.

Limits: one model family; K4 experts everywhere; contexts to 127K; synthetic tasks; 60 items per length.

## 8. Post hoc: long context pooled (64K + 127K), added 2026-11-11 after the results were read

Not in the frozen protocol; 48 intervals were computed in this section and two exclude zero (both `compact - anchor`,
`ledger`, every field right), so an interval that excludes zero here is a
lead, not a finding. Item as the unit, single message, two passes (all three passes in brackets where it differs
in kind: it does not).

| difference | all families, field score | `ledger`, field score | `ledger`, every field right |
|---|---|---|---|
| hqa - anchor | -0.002 [-0.025, +0.021] | -0.023 [-0.073, +0.023] | -0.062 [-0.188, +0.075] |
| compact - anchor | -0.019 [-0.051, +0.013] | -0.062 [-0.127, +0.002] | -0.138 [-0.263, -0.025] |
| hqa - compact | +0.017 [-0.011, +0.048] | +0.039 [-0.025, +0.113] | +0.075 [-0.025, +0.175] |

With the 8-turn pass included, `compact - anchor` on `ledger` every-field-right is -0.117 [-0.217, -0.017].
The order on long-context running totals is `anchor`, `hqa`, `compact` on every measure; only `compact`'s gap to
`anchor` reaches an interval that excludes zero, and only on the strict measure. At 4K + 16K all differences are
within +/-0.01 in field score.

## 9. Reference checkpoint `exlr8-k4`: two single-message passes (added 2026-11-11 after the results were read)

`exlr8-k4` is a reference checkpoint added after the results of sections 1 to 8 were read. It is not part of the
frozen comparison. Same 60 items at the same four lengths, same seeds, reply cap, concurrency and sampling
settings as the probe arms; the two single-message passes only, one launch per pass (2026-11-11 13:24 to 16:21);
no 8-turn pass. 480 requests, 0 errors; prompt tokens equal to `anchor`'s on 480 of 480 requests.
`analysis/reference.py` recomputes every number of this section from `analysis/samples.csv` and
`analysis/samples-reference.csv` into `analysis/REFERENCE.json`.

Checkpoint: `kindlingai/glm-5.3-flash-exlr8-k2-k3-k4` at revision 867580abd28d142bb4c56218bb81a752b7dea988,
manifest `k4`: routed and shared experts in a K4 trellis format with E4M3 rounding; attention output, `q_b_proj`
and the dense MLP at K4; attention input projections MXFP8; embedding and head FP8. Same engine release and
image, same drafter. The engine loads a native EXLR8 checkpoint from a content-addressed store; for these
launches the store (SparkNest v0.8.3, one node) ran on the same host and was mounted there. Upstream's status
note says bundled vision and full prefix-continuation exactness are not yet qualified for this checkpoint, which
is why it is run single-message only here.

**`exlr8-k4` is a different checkpoint from the three probe arms, not a setting of the same one. Any difference
from a probe arm is a whole-checkpoint difference and is not attributable to one component.** `anchor` stays the
reference of the probe, not a recommendation.

Score by length (share of answer fields right; unfinished replies score 0; two passes pooled, 120 requests per
length):

| arm | 4K | 16K | 64K | 127K | all lengths | 127K, pass 1 / pass 2 |
|---|---|---|---|---|---|---|
| anchor | 0.983 | 0.977 | 0.956 | 0.903 | 0.955 [0.942, 0.967] | 0.875 / 0.931 |
| hqa | 0.981 | 0.982 | 0.944 | 0.912 | 0.955 [0.941, 0.967] | 0.929 / 0.896 |
| compact | 0.984 | 0.975 | 0.932 | 0.890 | 0.945 [0.929, 0.960] | 0.885 / 0.894 |
| exlr8-k4 | 0.987 | 0.977 | 0.947 | 0.934 | 0.961 [0.947, 0.973] | 0.929 / 0.940 |

Every field right (requests of 120 per length, of 480 in all) and the finished-only score at 127K:

| arm | 4K | 16K | 64K | 127K | all | finished replies only, 127K |
|---|---|---|---|---|---|---|
| anchor | 105 | 100 | 93 | 81 | 379 | 0.942 |
| hqa | 106 | 105 | 88 | 80 | 379 | 0.936 |
| compact | 105 | 99 | 84 | 75 | 363 | 0.928 |
| exlr8-k4 | 109 | 101 | 88 | 77 | 375 | 0.942 |

How each request ended (of 480):

| arm | every field right | 1 field wrong | 2 wrong | 3 or more wrong | reply cap | loop abort |
|---|---|---|---|---|---|---|
| anchor | 379 | 69 | 22 | 4 | 5 | 1 |
| hqa | 379 | 68 | 20 | 8 | 4 | 1 |
| compact | 363 | 79 | 22 | 9 | 5 | 2 |
| exlr8-k4 | 375 | 80 | 16 | 7 | 2 | 0 |

`reply cap` is finish class `cap` and `loop abort` is finish class `repetition` in the per-request tables; both
score 0.

Paired differences, the frozen estimator applied to the added arm (b - a per item, repeats averaged within the
item, 95% interval from 10,000 item resamples, seed 5; 60 items):

| difference | all lengths | 4K + 16K | 64K + 127K | every field right, all lengths |
|---|---|---|---|---|
| exlr8-k4 - anchor | +0.006 [-0.007, +0.019] | +0.002 [-0.006, +0.009] | +0.011 [-0.013, +0.035] | -0.008 [-0.048, +0.033] |
| exlr8-k4 - hqa | +0.006 [-0.008, +0.019] | +0.000 [-0.009, +0.009] | +0.013 [-0.011, +0.035] | -0.008 [-0.060, +0.042] |
| exlr8-k4 - compact | +0.016 [+0.004, +0.029] | +0.002 [-0.006, +0.009] | +0.030 [+0.006, +0.056] | +0.025 [-0.017, +0.065] |

`exlr8-k4 - compact` at 127K alone: +0.045 [+0.009, +0.085]; on `ledger` at 64K + 127K (20 items):
+0.047 [-0.008, +0.108]. `analysis/reference.py` computes 84 intervals (six pairs, 14 each: field score per
length, over all lengths, at 4K + 16K and at 64K + 127K; every field right per length, over all lengths and at
64K + 127K; field score on `ledger` at 64K + 127K); three exclude zero, all three `exlr8-k4 - compact` on field score (all
lengths, 127K, 64K + 127K). Half of the 84 (42) are pairs among the three probe arms. `reference.py` applies
the frozen estimator (seed 5, percentile indices 250 and 9749) to every interval, the pooled ones included, so its
pooled intervals for the probe-arm pairs can differ in the third decimal from the post hoc ones of section 8
(seed 7, indices 250 and 9750).

Run-to-run floor and disagreement (every field right; of 240 item-lengths):

| | anchor | hqa | compact | exlr8-k4 |
|---|---|---|---|---|
| outcome differs between the arm's own two passes | 55 | 55 | 59 | 51 |

| pair, same pass and seed | pass 1: right in first only / second only | pass 2 |
|---|---|---|
| exlr8-k4 vs anchor | 26 / 24 | 18 / 24 |
| exlr8-k4 vs hqa | 22 / 32 | 32 / 26 |
| exlr8-k4 vs compact | 27 / 24 | 30 / 21 |

All four arms had every field right on 273 of 480 requests, none of them on 23.

Cost and speed (single message, two passes; speeds are per stream under a mixed concurrency-8 load and are not an
arm comparison):

| arm | resident weights MiB (GPU 0 + GPU 1) | KV pool tokens | tok/s per stream, median 4K / 16K / 64K / 127K | first token s, 127K | pass wall s |
|---|---|---|---|---|---|
| anchor | 166,026 (83,129 + 82,897) | 2,097,152 | 40.5 / 36.6 / 37.7 / 40.5 | 21.8 | 4,633, 4,306 |
| hqa | 161,758 (81,827 + 79,931) | 2,097,152 | 34.4 / 32.3 / 34.7 / 35.4 | 25.1 | 4,786, 4,943 |
| compact | 159,190 (80,543 + 78,647) | 2,097,152 | 36.7 / 33.0 / 33.7 / 36.9 | 25.5 | 5,025, 4,968 |
| exlr8-k4 | 162,081 (81,763 + 80,318) | 2,097,152 | 33.5 / 29.5 / 31.7 / 32.1 | 34.3 | 5,060, 5,325 |

Reading:

- **`exlr8-k4` against `anchor` and against `hqa`: no difference measured**, +0.006 [-0.007, +0.019] and
  +0.006 [-0.008, +0.019] pooled. Basis: two passes, 60 items, 480 requests per arm.
- **`exlr8-k4` against `compact`: higher field score, post hoc**, +0.016 [+0.004, +0.029] pooled and
  +0.030 [+0.006, +0.056] at 64K + 127K; at 4K + 16K +0.002 [-0.006, +0.009]. The arm was added after
  the results were read and this is one of 84 intervals, so it is a lead and not a finding. It is on the
  partial-credit score only: on every field right the pair does not separate (+0.025 [-0.017, +0.065]).
  Being a whole-checkpoint difference, it does not say which component carries it.
- **Accuracy falls with length in the reference checkpoint as in the probe arms** (0.987 at 4K to
  0.934 at 127K; finished replies only at 127K 0.942, `anchor` 0.942).
- `ledger` every field right at 64K and 127K (of 40 each): `anchor` 19 and 14; `hqa` 14 and 14; `compact` 12 and 10; `exlr8-k4` 13 and 10.

Limits as in section 7, and: two passes; one checkpoint of the EXLR8 family; single message only.

## 10. Scoring capture on `exlr8-k4` (exploratory, one capture; added 2026-11-11)

One teacher-forced capture of the reference checkpoint in the assistant frame (tag `a0`), prefill and decode
paths, on the five texts and the positions of protocol section 11a, read beside the `a0` captures of the three
probe arms. The engine scores a given text; nothing is sampled. Exploratory: one capture per arm, five texts, no
correction for the number of comparisons. The whole-checkpoint statement of section 9 applies.

**Distance from the unquantized BF16 model is not measured for these four configurations in this run.** All four
are quantized: `anchor` has a BF16 core and K4 experts, so a difference from `anchor` is a difference from another
quantization. The repository's BF16-referenced panels (README, "Does the precision difference matter?", texts to
14.4K tokens) cover other checkpoints. What this capture references to something fixed is the given text, which
comes first below; the distances between arms follow under their own heading.

`exploratory/capture_pairs.json` and `exploratory/capture_abs.json` hold every number of this section; the dumps
and per-row files they were computed from are not published.

Against the text itself (NLL of the given token in nats, and how often the arm's most likely token is the given
one; differences are arm minus `anchor`, 95% interval from resampling runs of consecutive positions within each
text):

| arm | prefill: NLL | top-1 = given | NLL - anchor | top-1 - anchor | decode: NLL | top-1 = given | NLL - anchor | top-1 - anchor |
|---|---|---|---|---|---|---|---|---|
| anchor | 1.4509 | 0.6618 | reference | reference | 1.5881 | 0.6438 | reference | reference |
| hqa | 1.4527 | 0.6600 | +0.0017 [-0.0039, +0.0080] | -0.0019 [-0.0042, +0.0006] | 1.5880 | 0.6438 | -0.0001 [-0.0061, +0.0060] | +0.0000 [-0.0042, +0.0047] |
| compact | 1.4454 | 0.6624 | -0.0055 [-0.0109, -0.0004] | +0.0006 [-0.0019, +0.0032] | 1.5796 | 0.6464 | -0.0085 [-0.0193, -0.0004] | +0.0026 [-0.0026, +0.0078] |
| exlr8-k4 | 1.4375 | 0.6611 | -0.0134 [-0.0199, -0.0070] | -0.0007 [-0.0037, +0.0023] | 1.5755 | 0.6448 | -0.0126 [-0.0263, +0.0001] | +0.0010 [-0.0036, +0.0057] |

Prefill path by depth band (NLL, then top-1 = given; per-band values are shown without intervals):

| arm | 1-4K | 4-16K | 16-32K | 32-64K | 64-96K | 96-128K |
|---|---|---|---|---|---|---|
| anchor | 1.365, 0.662 | 1.312, 0.688 | 1.443, 0.670 | 1.525, 0.648 | 1.464, 0.654 | 1.425, 0.671 |
| hqa | 1.367, 0.669 | 1.312, 0.684 | 1.439, 0.666 | 1.521, 0.647 | 1.464, 0.653 | 1.441, 0.668 |
| compact | 1.369, 0.669 | 1.313, 0.682 | 1.437, 0.672 | 1.519, 0.650 | 1.453, 0.653 | 1.423, 0.673 |
| exlr8-k4 | 1.365, 0.659 | 1.315, 0.685 | 1.434, 0.665 | 1.510, 0.648 | 1.454, 0.655 | 1.398, 0.670 |

Where the lower mean NLL of `exlr8-k4` comes from (prefill path; per-position difference d = NLL(arm) - NLL(anchor)):
the sum of d is -130.40 nat over 9,728 positions and its median is +0.000000. 99 positions
(1.0%) have |d| over 1 nat and sum to -91.48, 70% of the sum; 84 of them are in the `code` text
(-87.02; `code` as a whole -115.82). With 1% of positions trimmed from each side the mean of d is
-0.00579; the arm has the lower NLL on 47.5% of positions. By text, NLL is `code` 0.821 / 0.763; `join` 1.860 / 1.865; `ledger` 1.418 / 1.418; `prose` 2.206 / 2.195; `trace` 0.946 / 0.945 (`anchor` / `exlr8-k4`).

Collapse rows (the arm gives the given token under 0.05 where every other arm gives it 0.9 or more), prefill
path: `anchor` 2, `hqa` 1, `compact` 0, `exlr8-k4` 1; all in `code`. Decode path: `anchor` 0, `hqa` 0, `compact` 0, `exlr8-k4` 0.

### Between arms (not a distance from the BF16 model)

The three probe arms share their experts, so the distance between two of them reflects the settings outside the
experts alone (the core and, for `anchor`, the output head).
`exlr8-k4` has its own experts, so its distance to any probe arm includes both expert quantizations and does not
rank it against the probe arms by closeness to the BF16 model.

Exact KL between the two next-token distributions (first-named arm as the reference distribution, nats) and the
share of positions whose most likely token differs:

| pair | prefill path, 9,728 positions: KL mean | median | 95th pct | top-1 differs | decode path, 1,920 positions: KL mean | median | top-1 differs |
|---|---|---|---|---|---|---|---|
| anchor vs hqa | 0.0168 | 0.00054 | 0.0251 | 5.07% | 0.0100 | 0.00062 | 5.47% |
| anchor vs compact | 0.0176 | 0.00055 | 0.0252 | 5.15% | 0.0104 | 0.00073 | 5.68% |
| hqa vs compact | 0.0159 | 0.00038 | 0.0219 | 4.20% | 0.0094 | 0.00044 | 5.47% |
| anchor vs exlr8-k4 | 0.0323 | 0.00167 | 0.0668 | 8.85% | 0.0314 | 0.00215 | 10.31% |
| hqa vs exlr8-k4 | 0.0381 | 0.00161 | 0.0670 | 8.83% | 0.0309 | 0.00190 | 10.57% |
| compact vs exlr8-k4 | 0.0306 | 0.00147 | 0.0582 | 8.88% | 0.0261 | 0.00186 | 10.05% |

By how sure the arms are of the given token (prefill path; lowest probability any arm gives it):

| stratum | positions | probe-arm pairs: KL median | top-1 differs | pairs with `exlr8-k4`: KL median | top-1 differs |
|---|---|---|---|---|---|
| sure (0.9 or more in every arm) | 4,918 | 0.000002 to 0.000003 | never | 0.000005 to 0.000006 | never |
| fair (0.5 to 0.9) | 836 | 0.002708 to 0.003494 | never | 0.008824 to 0.009807 | never |
| unsure (under 0.5 in every arm) | 3,796 | 0.002285 to 0.003759 | 9.6 to 11.9% | 0.008032 to 0.008564 | 20.6 to 20.9% |
| mixed (arms straddle 0.5) | 178 | 0.010300 to 0.014357 | 24.2 to 28.1% | 0.030894 to 0.050958 | 39.3 to 43.8% |

On the sure positions the most likely token never differs in any pair, in any depth band, on either path. Mean KL
there, across bands: prefill path (six bands from 1K to 128K) 0.0003 to 0.0019 for pairs with `exlr8-k4` and
0.0002 to 0.0013 for probe-arm pairs; decode path (five bands from 4K to 128K) 0.0004 to 0.0029 and 0.0002 to 0.0014.

Reading (exploratory):

- **`exlr8-k4` is not measurably worse at predicting the text than `anchor`**: over the whole capture its
  most likely token is the given one as often as for `anchor` (the difference's interval spans zero on both
  paths, as it does for `hqa` and `compact`). By depth band its NLL is below `anchor`'s or within 0.003 of it; the
  per-band values carry no interval.
- **The lower mean NLL (prefill path) is carried by about 1% of positions, most of them in one text, and is not
  read as an improvement**: 99 of 9,728 positions carry -91.48 of the -130.40 nat, 70% of the sum (84 of them in
  `code`); the median per-position difference is zero and the arm is ahead on fewer than half of the positions.
  `compact`'s smaller sum also sits mostly in `code` (-53.78 nat in all, -41.72 of it in `code`; median +0.000000)
  but is less concentrated in single positions (46 positions over 1 nat carry -16.75 of it).
- **Distance from the unquantized BF16 model: not measured here**, for any of the four configurations.
- **Between arms**: on the prefill path the probe arms sit at median KL 0.0004 to 0.0006 from one another and differ
  in the most likely token on 4.20 to 5.15% of positions; `exlr8-k4` sits at 0.0015 to 0.0017 from a probe arm and
  differs on 8.83 to 8.88%. The second pair of figures also contains the difference between two expert
  quantizations, which the first does not, so the two do not rank the reference checkpoint against the probe arms
  by closeness to the BF16 model.

## 11. Amendment 1 (2026-11-11): two further single-message passes per arm, in progress

The head of this file says "amendments: none"; that describes the frozen run of sections 1 to 8. Amendment 1
(`protocol/AMENDMENT-2026-11-11.md`, written 2026-11-11 16:46:31 -0800, sha256
c3487e41a0194ed57ba968bda809ab8b160d810a02a19b106ec26fe86101d9f8) was written after the two-pass results of
sections 1 to 9 were read and before the first request of the passes it adds. The protocol file is unchanged and
its hash in `protocol/FROZEN.json` still holds.

It adds single-message passes 3 and 4 (`single-rep2`, `single-rep3`) for `anchor`, `hqa`, `compact` and
`exlr8-k4`: same items, lengths, reply cap, concurrency and sampling settings, new seed blocks. The total is fixed
at four single-message passes per arm before the first request of pass 3, so the stopping point does not depend
on what the added passes show. The comparison rule is the frozen one applied to four passes; the two-pass tables
above stay as the result of the frozen protocol, and the four-pass tables will be reported beside them, labelled
as an extension decided after the two-pass results were read. No 8-turn pass and no items are added. The
amendment also records the scoring capture of section 10 as exploratory.

Status: passes 3 and 4 are in progress. No number from them is in this file.
