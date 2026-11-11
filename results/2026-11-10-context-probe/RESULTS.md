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

- **Accuracy falls with length in every arm, the reference included** (0.98 at 4K to about 0.90 at 127K). On
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
