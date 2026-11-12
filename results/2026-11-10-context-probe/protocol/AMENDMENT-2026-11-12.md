# Amendment 2 to PROTOCOL.md (2026-11-12)

Written after the four-pass results of amendment 1 were read and published, and before the first request of the
passes it adds. PROTOCOL.md and amendment 1 are unchanged; the items, the drivers and the request settings are the
frozen ones (the driver refuses a measured pass if any of them has changed). `chain.sh` gains one arm definition
(sha256 before: 70cbaa9c…; the stage script is `amend2.sh`).

## B1. What had been read when this was written

- Everything in RESULTS.md sections 1 to 13: four single-message passes of `anchor`, `hqa`, `compact` and
  `exlr8-k4` (960 requests each), and their distance from the BF16 model to 14.4K.
- A post hoc breakdown of how those 3,840 replies ended (`analysis/make_endings.py`, sha256 f570a28d…;
  `analysis/endings.py`; `analysis/ENDINGS.json`), computed on 2026-11-12 and not yet written up: 44 replies did
  not finish, all inside the reasoning; `compact`'s lower score at 127K is concentrated in `join` replies that
  ran to the reply cap (10 of 80 against 4, 2 and 1).

## B2. A fifth configuration: `k325-fp8`

- Checkpoint: `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-Core-FP8`, revision d31ebc92: EXL3 routed experts at
  K3.25 with the official FP8 attention, dense and shared-expert blocks bundled in the same checkpoint. It is the
  checkpoint of the engine's own starting config for this model on two RTX cards
  (`examples/configs/glm53-flash-exl3-max.config`).
- Launch: `configs/glm53-flash-exl3-k3.25-core-fp8-2rtx.config`, engine v5.0.0 image by digest, defaults otherwise;
  the same local settings as the other arms (local experts, no Sparks, DFlash2 drafter, vision off).
- It differs from the three probe arms in two things at once: the routed experts (K3.25 against K4) and everything
  outside them (the official FP8 blocks against K6 or BF16). Like `exlr8-k4`, any difference from another arm is
  a whole-checkpoint difference and is not attributable to one component.
- Why it is added: it is the smallest configuration in this set and the one the engine ships as its default, so
  it shows where the default sits on the same tasks. In section 12 its distance from BF16 is a row from an earlier
  engine release; this amendment measures it on v5.0.0 beside the others.

## B3. Passes

- Four single-message passes, `single` rep 0 to rep 3, run tag `m0`: the same 60 items at the same four lengths
  (240 requests per pass), reply cap 32,768, concurrency 8, thinking on, temperature 1.0, top_p 0.95, and the same
  seed for each (item, length, repeat) as the other arms used.
- The total is fixed at four passes before the first request. One launch per pass.
- Not interleaved: the other arms' passes ran on 2026-11-10 to 2026-11-12, by pass across the arms; these four run
  alone afterwards on the same engine image, drivers and items. A session effect cannot be excluded by design; the
  engine image digest and the prompt token counts are checked against the earlier passes.
- No 8-turn pass.

## B4. Reading

- The frozen rule, as in amendment 1: paired difference b - a, the item as the unit, repeats averaged within the
  item, 95% interval from 10,000 item resamples (seed 5). Request score: correct / fields if the reply finished
  with `stop`, otherwise 0. Tables by length and by family as well as pooled.
- `k325-fp8` is read against each of the four existing arms; every such comparison carries the whole-checkpoint
  statement. The existing four-arm tables are not recomputed differently; the new arm is added to them.
- The ending breakdown is applied to `k325-fp8` with the definitions of `analysis/make_endings.py` as they stand
  (step line, copy run of 20 or more consecutive step lines, copy share of 0.5 or more for "copying"). For the
  first four arms that breakdown was post hoc; for this arm its definitions are fixed before the data.
- Stated before the data: no direction is predicted for task score. The four existing arms are level within about
  one point over all lengths while K3.25 sat 0.012 to 0.018 farther from BF16 on the earlier release, so either a
  level result or a lower one is plausible. For `join` at 127K the other arms left 4, 2, 10 and 1 of 80 replies
  unfinished.

## B5. Distance from BF16 for `k325-fp8`

The BF16-reference stage of `bf16ref/ADDENDUM-BF16REF.md` is run for this arm alone after its passes: the same
plans, dataset revision, scorers and two launches (`bf16ref/bf16ref.sh` unchanged, its arm list replaced by
`amend2.sh`). Prefill path, no sampling, to 14.4K. If the engine's fidelity CLI does not complete for this arm,
the stage's fallback capture is used, as its addendum describes.
