# Amendment 1 to PROTOCOL.md (2026-11-11)

Written after the results of the frozen run were read, and before the first request of the passes it adds.
PROTOCOL.md is unchanged; its hash in FROZEN.json still holds. The items, the drivers and the request settings
are the frozen ones (the driver refuses a measured pass if any of them has changed).

## A1. What had been read when this was written

- The three probe arms (`anchor`, `hqa`, `compact`): two single-message passes and one 8-turn pass each
  (RESULTS.md sections 1 to 8). Under the frozen rule no pair separates on the single-message cell.
- A reference checkpoint, `exlr8-k4`, added after those results were read: two single-message passes, same
  items, seeds, cap and concurrency (`chain.sh reference`; `analysis/reference.py`, `analysis/REFERENCE.json`).
  It is a different checkpoint from the three probe arms, not a setting of the same one: routed and shared
  experts in a K4 trellis format with E4M3 rounding; attention output, `q_b_proj` and the dense MLP at K4;
  attention input projections MXFP8; embedding and head FP8. Any difference from a probe arm is a
  whole-checkpoint difference and is not attributable to one component.
- A decomposition of the two-pass differences: the paired arm differences carry no measurable item-level
  variance, so their intervals are set by request-to-request sampling and narrow with more passes; the per-arm
  means carry item-level variance (28 to 67% of the total) that more passes do not remove.

## A2. Extension: two further single-message passes per arm

- Passes added: `single` rep 2 and `single` rep 3, for `anchor`, `hqa`, `compact` and `exlr8-k4`. Run tag `m0`.
- The total is fixed at four single-message passes per arm before the first request of rep 2. The stopping
  point does not depend on what the added passes show.
- Same 60 items at the same four lengths (240 requests per pass), reply cap 32,768, concurrency 8, thinking on,
  temperature 1.0, top_p 0.95. Seeds: the repeat index moves the whole seed block by 1,000,000
  (`probelib.seed_for`), so rep 2 and rep 3 use seed blocks no earlier pass used.
- Order: by pass across the arms (`anchor`, `hqa`, `compact`, `exlr8-k4`), one launch per arm per pass.
- No 8-turn pass is added, and none is run on `exlr8-k4`. No items are added.

## A3. Reading

- The comparison rule is the frozen one, applied to four passes: paired difference b - a, the item as the unit,
  repeats averaged within the item, 95% interval from 10,000 item resamples (seed 5). Request score:
  correct / fields if the reply finished with `stop`, otherwise 0.
- The two-pass tables stay as the result of the frozen protocol. The four-pass tables are reported beside them
  and labelled as an extension decided after the two-pass results were read. An interval that excludes 0 only
  at four passes is reported as that, with the two-pass interval next to it.
- Expected effect, stated before the data: half-widths of paired differences fall by about 0.71; half-widths of
  per-arm means fall by 10 to 20%.
- Every table is by length and by family as well as pooled, as PROTOCOL.md section 13 requires. Comparisons
  with `exlr8-k4` carry the whole-checkpoint statement wherever they appear.

## A4. Scoring capture on `exlr8-k4` (exploratory)

One teacher-forced capture in the assistant frame (`a0`), prefill and decode paths, on the texts of
PROTOCOL.md section 11a, read beside the `a0` captures of the probe arms. Exploratory, one capture; same
whole-checkpoint statement. `anchor` is itself a quantized checkpoint, so distance to `anchor` is distance to
another quantization and not to the unquantized model.
