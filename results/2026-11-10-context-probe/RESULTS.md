# Graded task runs: results (measured set, frozen protocol)

Run under `protocol/PROTOCOL.md` as frozen 2026-11-10 19:55 (`protocol/FROZEN.json`); amendments to the frozen run of sections 1 to 8: none
(amendment 1, section 11, adds passes and changes nothing in it). Chain: 2026-11-10 19:55 to
2026-11-11 08:28, nine units, every unit exit 0. Per-request receipts hold reply text and are not published; `analysis/samples.csv` carries their fields. Tables below are the output of
`drivers/analyze_tasks.py summary|compare --set measured`; the `ledger`-only section is an added exploratory
reading (`exploratory/ledger_errors.py`), not part of the frozen protocol. `analysis/posthoc.py` recomputes every
number here from `analysis/samples.csv` (one row per request, no text). Published 2026-11-11; the protocol's line
"results stay local" was written before that decision.

**Added 2026-11-12.** Sections 1 to 8 are the frozen two-pass run and stay as written. Three later sections
extend them: section 11 (amendment 1, four single-message passes per arm), section 12 (distance of each
configuration from the BF16 model) and section 13, a one-table summary of what each configuration trades.
Section 13 is the place to start. Where a later section changes a reading given earlier, the earlier line carries
a dated pointer.

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
- **`hqa` against `compact`: no difference measured**, +0.010 [-0.005, +0.025]. (2026-11-12: with four passes the
  interval is +0.013 [+0.002, +0.024] and the difference is at 127K; strength and caveats in section 11.)
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
  (2026-11-12: it did not repeat. Passes 3-4 alone give +0.002 [-0.017, +0.022] and four passes +0.009
  [-0.003, +0.021]; section 11.)
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

(2026-11-12: the distance of each configuration from the BF16 model is now measured, on reference sets to 14.4K; section 12.)

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

## 11. Amendment 1: four single-message passes per arm (added 2026-11-12)

The frozen run of sections 1 to 8 has no amendment. Amendment 1
(`protocol/AMENDMENT-2026-11-11.md`, written 2026-11-11 16:46:31 -0800, sha256
c3487e41a0194ed57ba968bda809ab8b160d810a02a19b106ec26fe86101d9f8) was written after the two-pass results of
sections 1 to 9 were read and before the first request of the passes it adds. The protocol file is unchanged and
its hash in `protocol/FROZEN.json` still holds.

It adds single-message passes 3 and 4 (`single-rep2`, `single-rep3`) for `anchor`, `hqa`, `compact` and
`exlr8-k4`: same items, lengths, reply cap, concurrency and sampling settings, new seed blocks. The total was
fixed at four passes per arm before the first request of pass 3, so the stopping point does not depend on what
the added passes show. The added passes ran 2026-11-11 17:02 to 2026-11-12 03:59: 1,920 requests, 0 errors, no
seed reused within an arm, prompt tokens equal to `anchor`'s first pass on 1,920 of 1,920 requests.

The rule is the frozen one applied to more passes: request score = correct / fields if the reply finished with
`stop`, else 0; repeats averaged within the item; b - a paired by item; 95% interval from 10,000 item resamples,
seed 5. Three pass sets are shown side by side: passes 1-2 (the frozen protocol's result, sections 1 to 9),
passes 3-4 alone, and all four. **The four-pass reading is an extension decided after the two-pass results were
read.** `analysis/fourpass.py` recomputes every number of this section from `analysis/samples.csv`,
`analysis/samples-reference.csv` and `analysis/samples-extension.csv` into `analysis/FOURPASS.json`.

### Arms, four passes (960 requests each; 240 per length)

| arm | score, all lengths | 4K | 16K | 64K | 127K | every field right, of 960 | unfinished, of 960 (at 127K, of 240) | finished replies only, 127K |
|---|---|---|---|---|---|---|---|---|
| anchor | 0.956 [0.944, 0.966] | 0.985 | 0.972 | 0.946 | 0.918 | 760 | 9 (7) | 0.945 |
| hqa | 0.959 [0.945, 0.970] | 0.984 | 0.981 | 0.945 | 0.924 | 768 | 9 (5) | 0.944 |
| compact | 0.946 [0.932, 0.958] | 0.981 | 0.972 | 0.942 | 0.887 | 739 | 18 (14) | 0.942 |
| exlr8-k4 | 0.955 [0.940, 0.967] | 0.983 | 0.978 | 0.938 | 0.920 | 738 | 8 (4) | 0.936 |

Score per pass, all lengths (passes 1, 2, 3, 4): `anchor` 0.943, 0.967, 0.953, 0.959; `hqa` 0.966, 0.944, 0.957,
0.967; `compact` 0.943, 0.948, 0.944, 0.948; `exlr8-k4` 0.960, 0.962, 0.936, 0.960. At 127K: `anchor` 0.875,
0.931, 0.923, 0.942; `hqa` 0.929, 0.896, 0.927, 0.946; `compact` 0.885, 0.894, 0.892, 0.877; `exlr8-k4` 0.929,
0.940, 0.875, 0.938. A single pass of one arm moves by up to 0.03 over all lengths and 0.07 at 127K.

### Paired differences, score, all lengths

| b - a | passes 1-2 (frozen) | passes 3-4 alone | four passes |
|---|---|---|---|
| hqa - anchor | +0.000 [-0.012, +0.012] | +0.006 [-0.010, +0.021] | +0.003 [-0.005, +0.012] |
| compact - anchor | -0.010 [-0.026, +0.006] | -0.010 [-0.029, +0.007] | -0.010 [-0.021, +0.002] |
| hqa - compact | +0.010 [-0.005, +0.025] | +0.016 [-0.002, +0.036] | +0.013 [+0.002, +0.024] (excludes 0 only at four passes) |
| exlr8-k4 - anchor | +0.006 [-0.007, +0.019] | -0.008 [-0.023, +0.005] | -0.001 [-0.012, +0.009] |
| exlr8-k4 - hqa | +0.006 [-0.008, +0.019] | -0.014 [-0.028, -0.001] | -0.004 [-0.016, +0.007] |
| exlr8-k4 - compact | +0.016 [+0.004, +0.029] | +0.002 [-0.017, +0.022] | +0.009 [-0.003, +0.021] |

### Paired differences by length, four passes

| b - a | 4K | 16K | 64K | 127K |
|---|---|---|---|---|
| hqa - anchor | -0.002 [-0.009, +0.006] | +0.009 [+0.001, +0.018] | -0.002 [-0.023, +0.019] | +0.007 [-0.019, +0.033] |
| compact - anchor | -0.004 [-0.012, +0.005] | -0.001 [-0.013, +0.010] | -0.004 [-0.026, +0.017] | -0.031 [-0.070, +0.008] |
| hqa - compact | +0.003 [-0.007, +0.011] | +0.009 [-0.002, +0.022] | +0.003 [-0.016, +0.022] | +0.037 [+0.004, +0.073] |
| exlr8-k4 - anchor | -0.003 [-0.007, +0.002] | +0.005 [-0.005, +0.016] | -0.009 [-0.029, +0.010] | +0.003 [-0.030, +0.034] |
| exlr8-k4 - hqa | -0.001 [-0.008, +0.006] | -0.004 [-0.016, +0.007] | -0.007 [-0.030, +0.013] | -0.004 [-0.035, +0.025] |
| exlr8-k4 - compact | +0.002 [-0.007, +0.010] | +0.006 [-0.006, +0.019] | -0.005 [-0.023, +0.013] | +0.033 [-0.002, +0.069] |

**How many intervals exclude 0.** Each pass set holds 102 intervals: 6 pairs x 17 (score at four lengths, all
lengths and two length groups; every field right at four lengths, all lengths and 64K + 127K; `ledger` score at
64K + 127K; score in each of three families). The number that exclude 0
is 4 at passes 1-2, 13 at passes 3-4 and 6 at four passes. At a 95% level about 5 of 102 would exclude 0 with no
difference anywhere, so a single interval of this table is not evidence on its own. The six at four passes:
`hqa` - `compact` at all lengths, at 127K and in the `join` family (+0.028 [+0.009, +0.049]); `exlr8-k4` -
`compact` in `join` (+0.027 [+0.010, +0.046]); `hqa` - `anchor` at 16K; `exlr8-k4` - `anchor` on every field right
at 64K + 127K (-0.046 [-0.087, -0.004]). The four at passes 1-2 all involve `exlr8-k4`: its score against
`compact` at 127K, at all lengths and at 64K + 127K, and against `anchor` in `join`. Of the 13 at passes 3-4, nine
involve `exlr8-k4` (six of them against `hqa`), four are every field right at 4K and four are in `join`. No
interval excludes 0 in both two-pass sets. The lists are in `SUMMARY.json` (`four_pass.intervals`).

### Reading

- **`hqa` against `anchor`: no difference measured, and the bound is tighter.** +0.003 [-0.005, +0.012]: the 95%
  interval reaches down to -0.005. Basis: four passes, 60 items, 960 requests per arm; the same reading in both
  pass sets.
- **`compact` is the lowest arm in both pass sets, about one point below the others over four passes, and the
  gap is at 127K.** It is below the next arm by 0.010 in passes 1-2 and by 0.002 in passes 3-4; over four passes
  it scores 0.946 against 0.955 to 0.959. Up to 64K it is level with the others (differences from `anchor` of
  -0.004, -0.001, -0.004). At 127K it scores 0.887 against 0.918 to 0.924, and its four single passes there
  (0.877 to 0.894) vary least of the four configurations. Against
  `hqa` the four-pass interval excludes 0 (all lengths and 127K); against `anchor` it does not (-0.010
  [-0.021, +0.002]; at 127K -0.031 [-0.070, +0.008]). Strength: indicated, not established. It rests on the same
  sign in both pass sets and on the single passes at 127K, not on one interval among 102: there `compact` is
  below `hqa` in every pass (by 0.002 in the closest, pass 2) and below `anchor` in three of four (pass 1
  reverses: 0.875 against 0.885).
- **Where `compact`'s 127K gap comes from is not settled.** Pooled over four passes it matches the unfinished
  replies: 14 of 240 at 127K against 7, 5 and 4, while replies that finished score level (0.942 against 0.936 to
  0.945). The two pass sets do not agree on that split. In passes 1-2 `compact` had as many unfinished replies at
  127K as `anchor` (5 and 5) and a lower finished-only score (0.928 against 0.942); in passes 3-4 it had 9
  unfinished against 2, 2 and 3 and the highest finished-only score (0.956). Of its 18 unfinished replies, 15
  reached the reply cap and 3 ended on repetition. By task family the pass sets disagree as well: over four
  passes `hqa` - `compact` sits in `join` (+0.028 [+0.009, +0.049]; `ledger` +0.008, `trace` +0.003), but passes
  1-2 put it in `ledger` (+0.024, `join` +0.009) and passes 3-4 in `join` (+0.048, `ledger` -0.008). The scoring
  capture (section 10) reads other texts, long and given, in one launch per arm, and samples nothing. It shows no
  deficit for `compact` at predicting text: its NLL minus `anchor`'s is -0.0055
  [-0.0109, -0.0004] (lower is better), share of positions whose top token is the given one +0.0006
  [-0.0019, +0.0032] (exploratory, one capture, 9,728 positions to 128K). The capture does not locate the gap. It
  shows only that `compact` is not worse at next-token prediction on long given text; the gap was seen in
  generated replies at 127K. *Added later on 2026-11-12:* section 14 reads the unfinished replies themselves and
  locates the gap: `join` replies at 127K that did not finish, with an ending every arm shows. What stays unsettled is
  whether the K6 projections raise their rate.
- **The two-pass lead of `exlr8-k4` over `compact` (section 9) did not repeat.** Passes 3-4 alone give +0.002
  [-0.017, +0.022] and the four-pass interval includes 0. At 127K the four-pass difference is +0.033
  [-0.002, +0.069], the same size as `hqa`'s over `compact`.
- **`exlr8-k4` sits with `anchor` and `hqa` on score** (-0.001 and -0.004, intervals within +/-0.016). It has
  fewer replies fully right than those two in count: 738 of 960 against 760 and 768 (`compact` 739). Over all
  lengths those two intervals include 0 (-0.023 [-0.054, +0.008] and -0.031 [-0.067, +0.002], as a share of
  replies); at 64K + 127K pooled the one against `anchor` excludes 0 (-0.046 [-0.087, -0.004]), one of the six
  listed above. On `ledger` at 64K + 127K it has 48 of 160 fully right against 68, 59 and 59 (`anchor`, `hqa`,
  `compact`). In passes 3-4 alone `exlr8-k4` - `hqa` is -0.014 [-0.028, -0.001]; it is one of the 13 intervals
  excluding 0 in that pass set and the sign is the opposite in passes 1-2 (+0.006). Whole-checkpoint difference;
  not attributable to one component.
- **The two-pass lean against the K6 core on running totals (sections 5 and 8) did not repeat.** On `ledger` at
  64K + 127K, `compact` - `anchor` in field score was -0.062 [-0.128, +0.002] in passes 1-2, +0.011 [-0.055,
  +0.072] in passes 3-4 and is -0.026 [-0.070, +0.019] over four; `hqa` - `compact` is +0.012 [-0.034, +0.059]
  over four. Replies with every field right there: 33, 28 and 22 of 80 in passes 1-2, 35, 31 and 37 of 80 in
  passes 3-4 (`anchor`, `hqa`, `compact`). Twenty items; every one of these intervals includes 0. Section 8 gives
  the passes 1-2 interval as -0.062 [-0.127, +0.002]: the same requests, resampled with another seed.
- **Accuracy still falls with length in every arm**: 0.98 at 4K to 0.89-0.92 at 127K over four passes, a fall of
  0.067, 0.060, 0.094 and 0.063 (`anchor`, `hqa`, `compact`, `exlr8-k4`; differences of the figures as shown). About 0.06 of it is common to the four,
  the BF16-core `anchor` included, so that part does not come from the settings that differ between them;
  `compact`'s further 0.03 is its 127K gap above. The four
  share the model family, the engine, the sampling settings, the reply cap and the tasks themselves, whose
  distractor text grows with length. No unquantized model and no other engine ran these tasks, so this run does
  not say where the common fall comes from.
- **Precision gained.** The amendment stated in advance that four passes would narrow paired intervals to about
  0.71 of their two-pass half-width and arm means by 10 to 20%. Measured: 0.71, 0.71 and 0.75 for the three probe
  pairs, 0.79 to 0.90 for pairs with `exlr8-k4`; arm means 0.82 to 0.94 for the probe arms and 1.05 for
  `exlr8-k4` (its third pass was its lowest).

Descriptive, four passes, median per stream under the mixed concurrency-8 load (not an arm comparison under the
protocol): decode tok/s at 4K / 16K / 64K / 127K `anchor` 38.7 / 38.3 / 36.9 / 39.5, `hqa` 34.3 / 32.5 / 33.1 /
35.0, `compact` 36.1 / 33.2 / 33.6 / 37.2, `exlr8-k4` 32.0 / 30.6 / 31.4 / 32.8; first token at 127K 21.8, 25.1,
25.4 and 34.2 s. Of 960 item-length-pass cells, all four arms had every field right in 533 and none did in 42.

## 12. Distance from the BF16 model (added 2026-11-12)

Sections 1 to 11 score tasks, and section 10 compares the arms with each other. Neither says how far a
configuration is from the unquantized model. This stage measures that on two reference sets that hold BF16
outputs. Its plan (`bf16ref/ADDENDUM-BF16REF.md`, hashes in `bf16ref/FROZEN.json`) was written 2026-11-11 17:54,
before its first request and after the two-pass task results were read. Status: descriptive; no gate and no
ranking rule; every interval computed is listed.

Ran 2026-11-12 04:06 to 05:28, one engine at a time, every step exit 0. The engine scores fixed token ids on its
prefill path, so no sampling, seeds or thinking setting are involved. Sources: `bf16ref/BF16REF.json`, which carries the numbers of the stage's score files.

Engine build `v5.0.0-1-g092f2168b`: the v5.0.0 tag plus one local commit, which holds this host's configuration
files and the launcher guard that passes `--device=/dev/infiniband` to the coordinator container only when the
device exists; the coordinator image is the release image, pinned by digest.

| | Fidelity set | Teacher panel |
|---|---|---|
| Source | the engine author's published fidelity set, config `glm5_flash-v2_20261005_bf16root` | published BF16 teacher logits for GLM 5.3 Flash |
| Size | 64 windows, 512 scored positions each; 15,104 generated positions in 53 windows | 25 windows of 2,048 tokens; 51,175 scored rows |
| Measure | KL over the reference's top 1,024 tokens plus the rest (the author's rule), ratio of sums over generated positions | KL over the full vocabulary, mean over rows |
| Context length | to 14.4K; buckets 0-2K, 2-8K, 8-16K | 2K |
| Interval | window bootstrap, 5,000 draws | window bootstrap, 20,000 draws |

The two sets use different measures and are not comparable with each other. **Neither reaches past 14.4K: the 64K
and 127K lengths of the task runs have no BF16 reference here.**

### KL from BF16 (nats; 0 is identical, lower is closer)

| Row | Fidelity set, generated positions | 0-2K | 2-8K | 8-16K | Teacher panel |
|---|---|---|---|---|---|
| Official FP8 release (baseline recorded by the engine author in the fidelity set's manifest; quoted, not recomputed here) | 0.0216 | | | | |
| `hqa` | 0.0302 [0.0255, 0.0344] | 0.0287 | 0.0219 | 0.0350 | 0.0316 [0.0238, 0.0410] |
| `compact` | 0.0314 [0.0263, 0.0359] | 0.0310 | 0.0230 | 0.0356 | 0.0297 [0.0236, 0.0364] |
| `anchor` | 0.0328 [0.0275, 0.0377] | 0.0335 | 0.0215 | 0.0378 | 0.0320 [0.0241, 0.0419] |
| `exlr8-k4` | 0.0360 [0.0300, 0.0416] | 0.0351 | 0.0245 | 0.0419 | 0.0305 [0.0244, 0.0374] |
| K3.25 checkpoint on this engine (measured 2026-10-26 on an earlier engine release; same sets and measures) | 0.0484 | | | | 0.0476 |

| arm | top-1 agreement with BF16 (fidelity set / teacher panel) | NLL above BF16, nats | top-1 where BF16 is confident |
|---|---|---|---|
| anchor | 0.9472 / 0.9464 | +0.0226 / +0.0035 | 0.9738 / 0.9903 |
| hqa | 0.9517 / 0.9461 | +0.0178 / +0.0036 | 0.9777 / 0.9906 |
| compact | 0.9499 / 0.9467 | +0.0179 / +0.0055 | 0.9751 / 0.9908 |
| exlr8-k4 | 0.9452 / 0.9444 | +0.0263 / +0.0074 | 0.9728 / 0.9903 |

All four pass the engine CLI's own fidelity gate on this set (KL at most 0.05, top-1 at least 0.93).

**Repeat.** A second launch of each arm reproduced the fidelity-set result exactly: KL difference 0.0 and the same
argmax on 15,104 of 15,104 generated positions, in all four arms. The float64 port used for the intervals and
the engine CLI agree on 32,768 of 32,768 records per arm and launch (largest KL difference 0.0).

### Differences between arms on the same rows (KL, b - a; negative means b is closer to BF16)

| b - a | fidelity set, overall | 0-2K | 2-8K | 8-16K | teacher panel |
|---|---|---|---|---|---|
| hqa - anchor | -0.0026 [-0.0042, -0.0011] | -0.0047 [-0.0078, -0.0019] | +0.0004 [-0.0010, +0.0019] | -0.0029 [-0.0054, -0.0008] | -0.0004 [-0.0014, +0.0006] |
| compact - anchor | -0.0014 [-0.0028, +0.0001] | -0.0025 [-0.0045, -0.0004] | +0.0016 [-0.0002, +0.0039] | -0.0023 [-0.0044, -0.0001] | -0.0023 [-0.0065, +0.0006] |
| compact - hqa | +0.0012 [-0.0002, +0.0026] | +0.0023 [-0.0003, +0.0053] | +0.0012 [-0.0014, +0.0040] | +0.0006 [-0.0013, +0.0025] | -0.0019 [-0.0057, +0.0009] |
| exlr8-k4 - anchor | +0.0032 [+0.0008, +0.0054] | +0.0017 [-0.0022, +0.0058] | +0.0031 [+0.0001, +0.0060] | +0.0041 [+0.0001, +0.0076] | -0.0015 [-0.0056, +0.0018] |
| exlr8-k4 - hqa | +0.0058 [+0.0038, +0.0081] | +0.0064 [+0.0011, +0.0128] | +0.0027 [-0.0003, +0.0059] | +0.0070 [+0.0045, +0.0094] | -0.0011 [-0.0048, +0.0022] |
| exlr8-k4 - compact | +0.0046 [+0.0023, +0.0069] | +0.0042 [-0.0009, +0.0097] | +0.0015 [-0.0011, +0.0034] | +0.0064 [+0.0027, +0.0096] | +0.0008 [-0.0011, +0.0026] |

Thirty intervals are listed (24 on the fidelity set, 6 on the teacher panel); 13 exclude 0, all on the fidelity
set. None was selected.

The two rows from other measurements. The FP8 row is the baseline the engine author recorded in the fidelity
set's manifest (`calibration.baseline_metrics`, prefill path; 0.0216 in both of its repeats): the checkpoint
`zai-org/GLM-5.3-Flash` against the same BF16 root, with this set's measure, on the author's engine build and
hardware. It is quoted, not recomputed here. The K3.25 row was measured here on 2026-10-26 on an earlier engine
release: the fidelity set over the same generated positions with the same measure, the teacher panel over the
full vocabulary.

### Reading

- **All four configurations sit in one band, between the FP8 release and K3.25.** 0.030 to 0.036 on the fidelity
  set: 1.4 to 1.7 times the FP8 baseline and 0.62 to 0.74 of the K3.25 figure.
- **What differs between the three probe arms is a small part of that distance.** They share their K4 experts.
  `hqa` and `compact` differ in `ATTENTION_MODE` alone, and between those two the distance does not move
  measurably (`compact` - `hqa` +0.0012 [-0.0002, +0.0026] on the fidelity set, -0.0019 [-0.0057, +0.0009] on the
  teacher panel). `anchor` differs from them in the rest of the core and in the output head: it is launched with
  the engine's three FP8 conversion settings off, which keeps both at BF16 (FP8 settings as logged: section 13,
  terms). Between the three the distance moves by at most 0.003, under a tenth of the total;
  the rest is common to the three. The plan stated before the first request that `anchor`'s distance would not be zero
  (quantized experts and the engine's numerics; the two are not separated here). `anchor` is also not the closest:
  `hqa` is 0.0026 closer on the fidelity set (interval excludes 0) and level on the teacher panel; `compact` -
  `anchor` is -0.0014 [-0.0028, +0.0001] on the fidelity set, interval includes 0. `anchor` is also a locally
  derived checkpoint; why it measures slightly farther than `hqa` on one set is an open question.
- **`exlr8-k4` is 0.003 to 0.006 farther than each probe arm on the fidelity set and level with them on the
  teacher panel.** The two sets place it differently, and this stage does not say which is nearer. Each set has
  its own provenance. The fidelity set is the engine author's; its relation to the calibration data of either
  checkpoint is not known. The teacher panel is drawn from the corpus the producer of the K4 experts published and
  can favour the experts the three probe arms carry (stated in the plan before the first request); a tilt of that
  kind would run toward the probe arms on that panel, which is the set where the four are level; it does not bear
  on the fidelity set, where `exlr8-k4` is farther. Whole-checkpoint difference.
- **In every arm the 8-16K bucket is the farthest and 2-8K the closest.** The buckets hold different texts (8-16K
  is long code reading), so this is not a length trend on its own.
- **Where both kinds of measurement exist, both show small differences.** Up to 16K the task scores of the three
  probe arms are within 0.01 of one another (section 11) and their distances from BF16 within 0.003. The one
  task difference indicated on this page,
  `compact` at 127K, lies beyond the reach of either reference set, so this stage neither supports nor
  contradicts it.

Limits: one engine build; one checkpoint revision per arm; prefill path only; contexts to 14.4K; the FP8 and
K3.25 rows come from other measurements; the teacher panel can favour K4 experts.

## 13. What each configuration trades (summary of sections 1 to 12, added 2026-11-12)

`anchor` is the reference of the probe, not a recommendation. The table puts cost and measured quality side by
side; every figure is from a section above or, for the memory rows, from the launch logs (`SUMMARY.json`:
`trade_offs`, `launch`, `reference.launch`).

What can be obtained: `hqa` and `compact` are two settings of one checkpoint, K4-Core-K6-HQA. That repository is
no longer available on the hub (checked 2026-11-11); these runs used a local copy downloaded on 2026-11-10. The
`anchor` checkpoint is derived locally and was never a hub release. `exlr8-k4` is a published checkpoint
(section 9).

| | `anchor` | `hqa` | `compact` | `exlr8-k4` |
|---|---|---|---|---|
| Outside the experts | BF16 core and head | BF16 `q_b_proj` and `o_proj`, rest K6 | K6 core and head | its own checkpoint (section 9) |
| Weights outside the experts, both GPUs, MiB | 15,138 | 10,872 | 8,304 | 7,496 |
| Resident weights, both GPUs, MiB | 166,026 | 161,758 | 159,190 | 162,081 |
| KL from BF16, fidelity set, to 14.4K | 0.0328 | 0.0302 | 0.0314 | 0.0360 |
| KL from BF16, teacher panel, 2K | 0.0320 | 0.0316 | 0.0297 | 0.0305 |
| Task score, four passes, all lengths | 0.956 | 0.959 | 0.946 | 0.955 |
| Task score at 127K | 0.918 | 0.924 | 0.887 | 0.920 |
| Every field right, of 960 | 760 | 768 | 739 | 738 |
| Unfinished replies, of 960 | 9 | 9 | 18 | 8 |
| Decode tok/s per stream at 127K, median (descriptive) | 39.5 | 35.0 | 37.2 | 32.8 |
| First token at 127K, s, median (descriptive) | 21.8 | 25.1 | 25.4 | 34.2 |

Terms. Probe arms: `anchor`, `hqa` and `compact`, which share their K4 experts; the four configurations are those
three and `exlr8-k4`. Reference is used for three things: `anchor` is the reference arm of the probe, the all-BF16
core the other arms are read against; `exlr8-k4` is a reference checkpoint in another quantisation format; the
BF16 model is the unquantized model that distance is measured from. `anchor` is not the BF16 model: its experts
are K4. Experts: the model's mixture-of-experts feed-forward weights, most of its size; K4 in the three probe
arms. Core: the attention and other layer weights outside the experts. Head: the output matrix that turns the
last hidden state into token scores. K4 and K6: quantized formats at about 4 and 6 bits per weight (BF16 holds
16). K3.25: a checkpoint of the same model in the same family of formats at about 3.25 bits per weight, with an
FP8 core, measured here on 2026-10-26 on an earlier engine release (CuteAFD v3.0.1); a row for scale, not part of
this comparison (since this was written the checkpoint has become a fifth configuration, `k325-fp8`; section 15
gives measured bits per weight for all five and a short primer on the formats). FP8 settings: the engine has three FP8 conversion settings (`GLM5_FLASH_KDA_FP8`,
`GLM5_FLASH_FP8_HEAD`, `GLM5_FLASH_FP8_PREFILL`). `anchor` is launched with all three off, which keeps its BF16
core matrices and head at BF16. As logged at load, KDA FP8 reads Off in all nine serving launches of the three
probe arms; the FP8 prefill setting reads none in `anchor` and `[Mla, Ffn]` in `hqa` and `compact`; the head reads
BF16 in `anchor` and K6 in the other two. Switching the prefill setting off on `hqa` left every recorded
distribution bit-identical in a check before the graded runs. Passes and pass sets: a pass is one run of an arm's
240 requests (60 items at four lengths); passes 1-2 are the frozen two-pass result, passes 3-4 were added under
amendment 1, and "four passes" pools them. Task score (field score): the share of a reply's eight answer fields that are right, 0 for a reply that did
not finish; higher is better, and one point is 0.01. Every field right: the stricter count of replies with all
eight right. Weights outside the experts: what the engine's startup plan places on the two GPUs outside the
experts, that is the 45 layers' weights (one copy on each GPU; the load line's "coordinator weights", section 7),
the output head and the token embedding table (each on one GPU). In the three probe arms those parts add up to
the plan's figure; in `exlr8-k4` the plan's figure is 505 MiB more than they add up to, and the logs do not
itemize that remainder. The count of 45 layers is the engine's load line; the HQA checkpoint holds 46
BF16 `o_proj` matrices (layer indices 0 to 45) and 12 `q_b_proj`. Both counts are as read, from different sources.
Resident weights: everything held as weights on
the two GPUs after load, experts included. The rest of the resident weights is the same in the three probe arms
(150,888, 150,886 and 150,886 MiB) and 154,585 MiB in `exlr8-k4`, which brings its own experts; that is why its
resident total is not the smallest although its weights outside the experts are. Left under the memory cap: the
engine's per-GPU memory cap minus weights, workspaces, reserve and KV pool. Workspaces and reserve: two items of
the engine's admission line beside weights and KV pool, per GPU; read from each launch's log, not measured here.
KV pool: the tokens of attention cache the engine admits for all simultaneous requests together. KL: how far a
configuration's next-token probabilities are from the BF16 model's at the same position; the fidelity set
computes it over the reference's top 1,024 tokens plus one term for the rest, the teacher panel over the full
vocabulary. Generated positions: the scored positions the fidelity set marks as generated text (15,104), as
opposed to context; its figures here are over those. Where BF16 is confident: positions where the BF16 model gives
its most likely token a probability of at least 0.5.

- **BF16 core to `hqa`: 4,266 MiB of weights back over the two GPUs, no quality cost measured.** Task score +0.003
  [-0.005, +0.012] over four passes; distance from BF16 not larger on either set. Strength: the best-supported
  reading here (960 requests per arm, both pass sets, two reference sets). The step changes two things together:
  the core outside the two projection groups and the output head, both BF16 in `anchor` and K6 in `hqa` (FP8
  settings as logged: terms above). It does not separate the two.
- **`hqa` to `compact`: a further 2,568 MiB back; a cost of about one point over all lengths is indicated, and it
  sits at 127K.** The two differ in `ATTENTION_MODE` alone. Over all lengths `hqa` - `compact` is +0.013 [+0.002,
  +0.024] and `compact` - `anchor` -0.010 [-0.021, +0.002]. Up to 64K `compact`'s task score is level with the
  other two, and its overall distance from BF16 is level with theirs on both reference sets (intervals include
  0). At 127K it scores 0.887 against 0.924 (`hqa` -
  `compact` +0.037 [+0.004, +0.073]); against `anchor` the interval includes 0 (-0.031 [-0.070, +0.008]). The
  scoring capture (section 10), on other long given texts, shows no deficit for `compact` at next-token
  prediction; it does not locate the gap, which was seen in generated replies at 127K. Pooled over four passes the
  gap matches unfinished replies: 14 of 240 at 127K against 7, 5 and 4, with finished replies level (0.942 against
  0.936-0.945). The two pass sets do not agree on that split or on the task family, so where the gap comes from is
  not settled. Strength: indicated, not established (section 11). *Added later on 2026-11-12:* section 14 locates
  it. The gap is `join` replies at 127K that did not finish (10 of 80 against 4, 2 and 1
  in `anchor`, `hqa` and `exlr8-k4`); where `compact` answered it was as right as the others. Whether the K6
  projections cause the higher rate is indicated, not established.
- **What the memory buys on this hardware.** Of the first step, 3,510 MiB is in the 45 layers (1,755 MiB on each
  GPU) and 756 MiB is the output head (1,210 MiB in BF16 against 454 MiB in K6), which `ATTENTION_MODE` does not
  select; the second step is all in the layers (1,284 MiB on each GPU). Resident weights fall by the same amounts
  to within 2 MiB (4,268 and 2,568 MiB). Not all of it arrives as free memory: `hqa` and `compact` hold larger
  workspaces (1,221 and 1,331 MiB more than `anchor` over both GPUs), so the memory left under the engine's cap
  after weights, workspaces, reserve and KV pool rises by 3,096 MiB from `anchor` to `hqa` (which also holds 49
  MiB less reserve) and by a further 2,458 MiB to `compact`. The cap is per GPU (about 97,250 MiB, of which the KV
  pool holds 7,603 MiB); the smaller of the two per-GPU figures is 1,201, 2,753 and 3,982 MiB (`anchor`, `hqa`,
  `compact`).
  In the serving launches, with eight requests at once, every arm was admitted the maximum KV pool (2,097,152
  tokens), so there the saving stayed as unused memory, not as pool size (section 7). It was seen to convert
  once: in the
  exploratory scoring launches, with 16 requests at once, `anchor` was admitted 1,318,400 tokens and `hqa` and
  `compact` the maximum. No launch here showed `compact` admitted a larger pool than `hqa`. That is one launch
  setting read from logs; pool and batch size were not varied as a measurement.
- **Speed is not an arm comparison under the protocol.** As run, `anchor` had the highest median decode speed and
  the shortest first-token time at 127K in both pass sets, and `exlr8-k4` the longest first-token time. These are
  medians under one mixed load; the protocol did not isolate speed and no cause is claimed.
- **`exlr8-k4`: task score level with `anchor` and `hqa`; fewer replies fully right in count (over all lengths
  those intervals include 0); 0.003 to 0.006 farther from BF16 on one set and level on the other.** It differs in
  the whole checkpoint, so none of this is attributable to one component.
- **The larger differences are outside this comparison.** Between these four, distance from BF16 moves by 0.006
  at most. The K3.25 checkpoint, measured on an earlier release of this engine, sits 0.012 to 0.018 farther than they do and the FP8 release 0.009 to 0.014
  closer (section 12; rows from other measurements). Task accuracy falls with length in every arm, `anchor`
  included, by 0.06 to 0.09 from 4K to 127K (`compact`'s is the largest, section 11); the largest difference
  between two arms at one length is 0.037. The
  tasks and the engine are shared too, and no unquantized model ran these tasks, so the run does not say where
  the common fall comes from.

Limits: one model family; one engine release; synthetic tasks; 60 items per length; K4-class checkpoints only;
BF16 reference to 14.4K only.

## 14. How the replies ended, four passes (post hoc, added 2026-11-12)

Sections 11 and 13 leave open where `compact`'s lower score at 127K comes from. This section counts how each of
the 3,840 replies of the four passes ended and, for those that did not finish, what their reasoning was made of.
It is descriptive and post hoc: the classification was written on 2026-11-12 after the four-pass results were
read, and its intervals come on top of the 102 per pass set of section 11. The counts are from
`analysis/endings.py` (`analysis/ENDINGS.json`), which reads the per-request tables and `analysis/endings.csv`;
that file holds counts over each reply's reasoning, made by `analysis/make_endings.py` from the saved replies. No
reply text is published.

How each request ended, four passes (of 960 per arm):

| arm | every field right | 1 field wrong | 2 wrong | 3 or more wrong | reply cap | loop abort |
|---|---|---|---|---|---|---|
| anchor | 760 | 133 | 45 | 13 | 7 | 2 |
| hqa | 768 | 132 | 40 | 11 | 7 | 2 |
| compact | 739 | 151 | 39 | 13 | 15 | 3 |
| exlr8-k4 | 738 | 164 | 35 | 15 | 8 | 0 |

The same at 127K (of 240 per arm):

| arm | every field right | 1 field wrong | 2 wrong | 3 or more wrong | reply cap | loop abort |
|---|---|---|---|---|---|---|
| anchor | 165 | 41 | 20 | 7 | 5 | 2 |
| hqa | 167 | 38 | 24 | 6 | 4 | 1 |
| compact | 159 | 41 | 18 | 8 | 13 | 1 |
| exlr8-k4 | 154 | 56 | 18 | 8 | 4 | 0 |

`reply cap`: the reply reached the 32,768-token cap (finish class `cap`). `loop abort`: the engine stopped it for
repetition (finish class `repetition`). Both score 0 under the frozen rule; "unfinished" means one of the two.

**All 44 unfinished replies ended inside the reasoning; none had written any answer text.** They sit in four of
the twelve family-length cells:

| arm | `join` 127K | `ledger` 64K | `ledger` 127K | `trace` 16K | all |
|---|---|---|---|---|---|
| anchor | 4 | 2 | 3 | 0 | 9 |
| hqa | 2 | 4 | 3 | 0 | 9 |
| compact | 10 | 3 | 4 | 1 | 18 |
| exlr8-k4 | 1 | 4 | 3 | 0 | 8 |

`ledger` has 5, 7, 7 and 7 over its two lengths: level across the arms. `compact`'s excess is `join` at 127K: 10
of 80 against 4, 2 and 1.

**What the unfinished reasoning was made of.** A `join` item is a list of records of three kinds in no order
(courier carries parcel, parcel routes via hub, hub ships from dock); the question names eight couriers and asks
for each one's dock, three lookups per answer. At 127K the prompt holds about 8,660 records. A *step line* is a
line of the reasoning that carries the record following, in the prompt, the record of the previous such line: the
reply is writing the prompt's records out in the prompt's order. A reply counts as *copying* when step lines make
up at least half of its reasoning by characters, and a *copy run* is 20 or more step lines in a row. The 44
replies are listed with their shares in `ENDINGS.json`, so another threshold can be applied.

| arm | `join`: copying | `join`: other | `ledger`: copying | `ledger`: other | `trace`: other |
|---|---|---|---|---|---|
| anchor | 4 | 0 | 3 | 2 | 0 |
| hqa | 1 | 1 | 0 | 7 | 0 |
| compact | 9 | 1 | 1 | 6 | 1 |
| exlr8-k4 | 1 | 0 | 5 | 2 | 0 |

Of the 17 unfinished `join` replies, 15 are copying. One more (`hqa`) has a copy run and a share just under the
threshold (0.49); the last (`compact`) has no copy run and is 116 thousand characters of other reasoning. In
`ledger` the make-up differs by arm (none of `hqa`'s 7 is copying, 5 of `exlr8-k4`'s 7 are) on counts of 5 to 7;
no reading is taken from that.

`join` at 127K, 80 requests per arm, every reply whether it finished or not:

| arm | unfinished, of 80 | by pass | replies with a copy run | of those, finished | of those, unfinished | unfinished with all 8 answers written before the run | items with an unfinished reply, of 20 |
|---|---|---|---|---|---|---|---|
| anchor | 4 | 3 / 1 / 0 / 0 | 8 | 4 | 4 | 3 | 4 |
| hqa | 2 | 0 / 2 / 0 / 0 | 5 | 3 | 2 | 0 | 2 |
| compact | 10 | 1 / 2 / 4 / 3 | 11 | 2 | 9 | 9 | 8 |
| exlr8-k4 | 1 | 0 / 0 / 1 / 0 | 4 | 3 | 1 | 1 | 1 |

The 15 copying replies have the same shape in every arm, `anchor` included. The reasoning runs for 3.7 to 13.5
thousand characters, then starts writing the prompt's records out in order and goes on until the reply cap (one
`anchor` reply was stopped by the loop abort at 25,575 tokens). In 13 of the 15, all eight correct docks had
already been written in the reasoning before the copy run started; in the other two, seven had. That is a text
match on the dock identifiers (four characters, about 2,900 distinct ones in a 127K prompt); it does not check
that each dock was attached to the right courier. A copy run is not always the end of a reply: 4, 3, 2 and 3
replies with one went on to finish, and scored 1.000, 1.000, 1.000 and 0.958. In `join`, copy runs occur at 127K
only, apart from one `compact` reply at 64K that finished. `compact` has more replies with a copy run than the
other arms (11 against 8, 5 and 4) and fewer of them finished (2 against 4, 3 and 3). Across the four arms, 11 of
the 20 `join` items have at least one unfinished reply at 127K.

**Where it answered, `compact` was as right as the others.** Score at 127K by family, four passes, and the score
of the finished replies alone:

| arm | `join` | `ledger` | `trace` | all | finished only: `join` | finished only: `ledger` | finished only: `trace` | finished only: all |
|---|---|---|---|---|---|---|---|---|
| anchor | 0.945 | 0.839 | 0.969 | 0.918 | 0.995 | 0.872 | 0.969 | 0.945 |
| hqa | 0.972 | 0.836 | 0.966 | 0.924 | 0.997 | 0.869 | 0.966 | 0.944 |
| compact | 0.866 | 0.820 | 0.975 | 0.887 | 0.989 | 0.864 | 0.975 | 0.942 |
| exlr8-k4 | 0.980 | 0.828 | 0.953 | 0.920 | 0.992 | 0.860 | 0.953 | 0.936 |

Each family is a third of the requests at 127K, so a difference in score there splits into three parts (the
family's own difference divided by 3):

| difference in score at 127K | all | from `join` | from `ledger` | from `trace` |
|---|---|---|---|---|
| `anchor` - `compact` | +0.031 | +0.027 | +0.006 | -0.002 |
| `hqa` - `compact` | +0.037 | +0.035 | +0.005 | -0.003 |
| `exlr8-k4` - `compact` | +0.033 | +0.038 | +0.003 | -0.007 |

Paired differences in the share of unfinished replies (b - a per item, repeats averaged within the item, 95%
interval from 10,000 item resamples: Python `random.Random(5)`, the sorted draws at indices 250 and 9,749; 60
items in the all-families rows, 20 in the `join` and `ledger` rows). Post hoc: the table shows 27 of the 60
intervals of this kind in `ENDINGS.json` (5 pairs, 3 pass sets, 4 cells); 9 of the 60 exclude 0, 8 of them here,
and no correction is applied:

| difference in the share of unfinished replies | passes 1-2 | passes 3-4 | four passes |
|---|---|---|---|
| `compact` - `anchor`, 127K, all families | +0.000 [-0.050, +0.050] | +0.058 [+0.000, +0.125] | +0.029 [-0.008, +0.067] |
| `compact` - `hqa`, 127K, all families | +0.017 [-0.025, +0.067] | +0.058 [+0.008, +0.117] | +0.037 [+0.008, +0.071] |
| `compact` - `exlr8-k4`, 127K, all families | +0.033 [+0.000, +0.075] | +0.050 [+0.000, +0.108] | +0.042 [+0.008, +0.079] |
| `compact` - `anchor`, 127K, `join` | -0.025 [-0.150, +0.100] | +0.175 [+0.050, +0.325] | +0.075 [-0.013, +0.163] |
| `compact` - `hqa`, 127K, `join` | +0.025 [-0.075, +0.125] | +0.175 [+0.050, +0.325] | +0.100 [+0.025, +0.175] |
| `compact` - `exlr8-k4`, 127K, `join` | +0.075 [+0.000, +0.150] | +0.150 [+0.050, +0.275] | +0.113 [+0.050, +0.175] |
| `compact` - `anchor`, 127K, `ledger` | +0.025 [-0.050, +0.100] | +0.000 [-0.100, +0.100] | +0.013 [-0.050, +0.075] |
| `compact` - `hqa`, 127K, `ledger` | +0.025 [-0.050, +0.100] | +0.000 [-0.075, +0.075] | +0.013 [-0.037, +0.062] |
| `compact` - `exlr8-k4`, 127K, `ledger` | +0.025 [-0.050, +0.100] | +0.000 [-0.100, +0.100] | +0.013 [-0.062, +0.087] |

Finished replies at 127K are about as long in every arm: median 4.8 to 5.0 thousand tokens, 99th percentile 25 to
29 thousand, and 11, 5, 9 and 7 of them longer than half the cap.

### Reading

- **`compact`'s 127K gap is `join` replies that did not finish, not answers that were wrong.** Of the 0.037 between
  `hqa` and `compact` at 127K, 0.035 is `join`; of the 0.031 between `anchor` and `compact`, 0.027. The finished
  replies score level in every family (`join` 0.989 against 0.992 to 0.997, `ledger` 0.864 against 0.860 to
  0.872, `trace` 0.975 against 0.953 to 0.969). Basis: 960 requests per arm, every unfinished reply classified.
  Strength: this is a count of what happened, not an estimate; it holds for these four passes.
- **The ending is one every arm shows, the BF16-core `anchor` included.** The reasoning has written all
  or all but one of the answers, starts copying the records and does not come back. `anchor` has 4 such replies
  of 80, `hqa` 1 and one just under the copying threshold, `exlr8-k4` 1, `compact` 9 and one of another kind. It is a way this model's reasoning fails to terminate on a long lookup
  task under these settings, seen at every core precision measured here; `compact` shows it more often.
- **Whether the K6 `q_b_proj` and `o_proj` raise its rate is indicated, not established.** For: `hqa` and
  `compact` are one checkpoint and differ in those two projections alone, and `compact` has 10 unfinished of 80
  against 2 (+0.100 [+0.025, +0.175]), over 8 items against 2. Against: `anchor`, whose projections are BF16 as
  `hqa`'s are, has 4, and the interval against it includes 0 (+0.075 [-0.013, +0.163]); by pass the counts are 1,
  2, 4 and 3 for `compact` against 3, 1, 0 and 0 for `anchor`, so the first two passes alone show no excess. The
  event is rare (17 replies of 320), the items are 20 and the classification is post hoc.
- **What this changes in sections 11 and 13.** The size of the gap stands. Its nature is narrower than "a cost of
  about one point" suggests: about one `join` reply in eight at 127K did not return an answer (the other arms:
  one in 20 to one in 80), and no loss of accuracy is measured on the replies that did. A reply that runs to the
  cap takes 14 to 17 minutes at the median decode rates of section 11 and returns nothing.
- **Not measured:** a larger reply cap, so whether these replies would have ended on their own is not known;
  other sampling settings; a limit on reasoning length; natural documents. `trace` and the shorter lengths show
  no excess for `compact` (one loop abort at 16K).

Limits: post hoc; 20 items per family; one threshold for "copying" (0.5) and one for a copy run (20 lines), both
chosen after the replies were seen; the dock check is a text match.

## 15. Bits per weight: one unit for the five configurations (added 2026-11-12)

The configurations here mix several storage formats inside one model, and their names ("K4", "K3.25", "Core-K6",
"FP8") each describe one part. This section puts them on one unit, **bits per weight**, counted from the files.

### A short primer

- **Weights and bits.** A language model is a set of matrices of numbers, its weights. This model's language
  part has 320.8 billion of them. Bits per weight is how many bits of storage each weight gets, on average: the
  storage for a part of the model divided by the number of weights in it. It sets the size of the files and,
  closely, of the model in memory, and lower values are coarser copies of the original.
- **BF16** is 16 bits per weight, the format the model was released in. It is "full precision" here and the 100%
  mark. At 16 bits the language model would be 597 GiB.
- **FP8** is an 8-bit floating-point number per weight plus a small table of scales: 8.0 to 8.3 bits per weight
  as stored in these files.
- **EXL3 and the K numbers.** EXL3 is a trellis-coded format: a matrix is stored as a code of K bits per weight
  plus two short scale vectors. K4 is 4 bits per weight (4.01 as stored), K6 is 6 (6.01).
- **Mixed widths.** A fractional K is an average over matrices, not a width. In the K3.25 checkpoint three
  quarters of the expert matrices are stored at 3 bits and one quarter at 4 (27,216 and 9,072 matrices). Which
  matrix gets which width is the checkpoint author's allocation and is not examined here.
- **EXLR8** is another trellis-coded format by another author. Its K4 experts are 4.00 bits per weight; the same
  nominal width in a different design is not the same code, so `exlr8-k4` is read as a whole checkpoint.
- **Where the weights are.** 94.9% of the weights are the routed experts: 288 small feed-forward blocks in each
  of 42 layers, of which a token passes through 8 per layer. Everything else in the main layers (attention,
  shared experts, the dense feed-forward of the first three layers, the output head, the embedding) is 2.8%, and
  every token passes through all of it. A further 2.3% is a multi-token-prediction block stored after the main
  layers. So the name on a checkpoint describes its experts and nearly fixes its size, while `anchor`, `hqa` and
  `compact` differ inside the 2.8% (and, for `hqa`, in a 0.1 GiB part of the multi-token-prediction block).
- **Names of the parts.** The core is everything in the main layers outside the routed experts. The shared
  experts are a feed-forward block beside the routed ones that every token passes through. `o_proj` and
  `q_b_proj` are two of the attention projection matrices of a layer, the two that `ATTENTION_MODE` selects the
  precision of. The output head turns the last hidden state into token scores. KDA is the engine's name, in its
  load line (the line it logs when a checkpoint is loaded), for a group of attention matrices it can hold as FP8.
- **Configurations and checkpoints.** There are five configurations and four checkpoints: `hqa` and `compact`
  are two settings of one checkpoint.
- **Stored is not the same as run.** The table counts what the files hold. The engine can hold a matrix in
  another form in memory; where it does, that is said below the table. Memory in use is in section 13.

### Bits per weight by component

From `analysis/bpw.py` (`analysis/BPW.json`): it reads the header of every checkpoint file (tensor names, types
and sizes; no weight is loaded) and counts, for each matrix, the stored bits of its payload and of its scale and
sign vectors against rows x columns of the matrix they stand for. Alignment padding, checksums and index records
are left out, and so is the vision tower (every configuration ran with vision off). `hqa` and `compact` are two
readings of one checkpoint, which stores `o_proj` and `q_b_proj` twice: `hqa` counts the BF16 copy, `compact` the
K6 copy.

| component | share of weights | `anchor` | `hqa` | `compact` | `exlr8-k4` | `k325-fp8` |
|---|---|---|---|---|---|---|
| routed experts | 94.90% | 4.01 | 4.01 | 4.01 | 4.00 | 3.26 |
| shared experts | 0.33% | 16.00 | 6.01 | 6.01 | 4.00 | 8.00 |
| dense MLP (layers 0-2) | 0.14% | 16.00 | 6.01 | 6.01 | 4.01 | 8.00 |
| attention: o_proj and q_b_proj | 0.67% | 16.00 | 16.00 | 6.01 | 4.01 | 12.23 |
| attention: other projections | 1.22% | 16.00 | 7.00 | 7.00 | 8.26 | 15.81 |
| output head | 0.20% | 16.00 | 6.00 | 6.00 | 8.01 | 16.00 |
| embedding | 0.20% | 16.00 | 16.00 | 16.00 | 8.01 | 16.00 |
| other | 0.03% | 16.00 | 16.00 | 16.00 | 16.00 | 16.00 |
| multi-token-prediction block | 2.32% | 4.05 | 4.20 | 4.05 | 4.04 | 3.33 |
| outside the routed experts, main layers | 2.78% | 16.00 | 9.66 | 7.25 | 6.55 | 13.65 |
| **whole language model** | 100% | **4.35** | **4.17** | **4.10** | **4.08** | **3.55** |
| share of BF16 (bits per weight / 16) |  | 27.2% | 26.1% | 25.6% | 25.5% | 22.2% |
| stored, GiB |  | 162.3 | 155.8 | 153.2 | 152.2 | 132.7 |

`k325-fp8` is a fifth configuration, the K3.25-Core-FP8 checkpoint (`wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-Core-FP8`,
revision d31ebc92), which the engine's own starting config for two RTX cards uses. Its four task passes and
its distance from BF16 are running under amendment 2 (`protocol/AMENDMENT-2026-11-12.md`, written before their first request); this section holds
its file accounting only.

What the rows mix. `hqa` and `compact`, other attention projections at 7.00: 90% K6 and 10% BF16. `k325-fp8`:
shared experts and dense feed-forward FP8; `o_proj` and `q_b_proj` 53% BF16 and 47% FP8; other attention
projections 97% BF16; head and embedding BF16. `exlr8-k4`: `o_proj`, `q_b_proj`, shared experts and dense
feed-forward in its 4-bit trellis; other attention projections FP8 with block scales (8.26); head and embedding
FP8 with one scale per row (8.01). The multi-token-prediction block is stored almost wholly at the experts'
width in every checkpoint, `anchor`'s included; its BF16 part is largest in `hqa` (1.6% of the block), whose
reading counts that block's `o_proj` and `q_b_proj` at BF16 too. Whether the engine uses that block when serving
was not checked.

As run, from each launch's load line. `anchor`: no FP8 conversion, head BF16. `hqa` and `compact`: head K6, as
stored. `exlr8-k4`: head FP8 with row scales, as stored. **`k325-fp8`: under the engine's defaults the load line
reports the attention group it calls KDA held as FP8, converted at load (`kda_fp8=Row128`: 2,844 MiB as FP8, 0 MiB
as BF16), and an FP8 output head (624 MiB, against 1,210 MiB for the BF16 head in `anchor`).** So part of what
this file stores at BF16 is run at FP8, and its 13.65 bits outside the routed experts is a property of the file,
not of the launch. An as-run figure is not computed, because the logs do not itemize the conversion by matrix.

### Size beside what was measured

| | `anchor` | `hqa` | `compact` | `exlr8-k4` | `k325-fp8` |
|---|---|---|---|---|---|
| Bits per weight, whole language model | 4.35 | 4.17 | 4.10 | 4.08 | 3.55 |
| Share of BF16 | 27.2% | 26.1% | 25.6% | 25.5% | 22.2% |
| Bits per weight outside the routed experts, as stored | 16.00 | 9.66 | 7.25 | 6.55 | 13.65 |
| Stored, GiB | 162.3 | 155.8 | 153.2 | 152.2 | 132.7 |
| KL from BF16, fidelity set, to 14.4K (section 12) | 0.0328 | 0.0302 | 0.0314 | 0.0360 | running |
| Task score, four passes, all lengths (section 11) | 0.956 | 0.959 | 0.946 | 0.955 | running |
| Task score at 127K | 0.918 | 0.924 | 0.887 | 0.920 | running |
| Replies at 127K that did not finish, of 240 (section 14) | 7 | 5 | 14 | 4 | running |

### Reading

- **Every configuration here is a 22% to 27% copy of the BF16 model by bits.** The four measured ones span 4.08
  to 4.35 bits per weight, 0.27 bits end to end, because their experts are all at 4 bits and the experts are 95%
  of the weights.
- **`hqa` to `compact` moves 0.67% of the weights from 16 bits to 6** in the main layers: 4.17 to 4.10 bits per
  weight, 2.6 GiB of files, 0.1 GiB of it the same two projections in the multi-token-prediction block.
  `anchor` to `compact` moves 2.4% of the weights from 16 bits to about 6 or 7: 4.35 to 4.10, 9.1 GiB.
  The embedding stays at BF16 in all three.
- **`k325-fp8` is the one that changes the experts**: 3.26 bits against 4.01 there. Its files are 20.5 GiB
  smaller than `compact`'s in all: the experts are smaller by more than that, and its core is stored at more bits
  than `hqa`'s or `compact`'s (stored; see "as run" above).
- **`exlr8-k4` is the smallest of the four measured, though its head and most of its attention projections are
  FP8**, more bits than `compact`'s K6 there. It stores `o_proj`, `q_b_proj`, the shared experts and the dense
  feed-forward in its 4-bit trellis where `compact` has K6, and its embedding at FP8 where `compact`'s is BF16:
  6.55 bits outside the routed experts against 7.25. Its files are 1.0 GiB smaller in all, 0.3 GiB of that in the
  experts (4.00 bits against 4.01).
- **How the whole-model figure is formed.** It pools every part, so each part counts by its share of the
  weights. For `compact`: 94.90% x 4.01 (routed experts) + 2.78% x 7.25 (rest of the main layers) + 2.32% x 4.05
  (multi-token-prediction block) = 4.10, and 4.10 / 16 = 25.6% of BF16. The published page draws this part by
  part for the five configurations (its layout figure).
- **Bits per weight is a size, not a quality score.** Among the four measured configurations distance from BF16
  and task score do not follow it: `hqa` at 4.17 is no farther from BF16 than `anchor` at 4.35 on either set
  (section 12), and `exlr8-k4` at 4.08 scores level with `anchor`. The unit says what was spent; sections 11 to
  14 say what it bought.

Limits: file accounting, not memory in use and not arithmetic precision at run time; the vision tower is not
counted (every configuration ran with vision off); whether the engine uses the multi-token-prediction block when
serving was not checked; the HQA checkpoint is no
longer on the hub and `anchor`'s is derived locally, so the script can be rerun by a reader on `exlr8-k4` and
`k325-fp8` only.
