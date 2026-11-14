# Checkpoints: what each one is

:::answer
The checkpoints differ most in their **routed experts**, which hold nearly all of the weights, and that is where most
of the distance from BF16 comes from ([precision](precision.html#sources), *established*). Between the two 4-bit
checkpoints, **neither is closer to BF16 on both reference sets** (*open*). **EXLR8 K4** was not detected to differ
from the K4-Core-K6 configurations on tasks (*supported*). The producers calibrated on different
text; the teacher panel comes from one producer's evidence set and can favour that checkpoint.
:::

## The checkpoints {#list}

The names, producers and builds are defined on the [terms page](terms.html#checkpoints). As stored:

{{table v5_bits}}

Sizes count the files as stored, not the form the engine runs: under the engine's defaults, part of what k325-fp8
stores at BF16 runs at FP8.

{{cite CP-bits-per-weight CP-bits-outside-experts CP-k325-as-run}}

## What they were calibrated on {#calibration}

{{table calibration_mix}}

{{cite V4-calibration-mix K4-pa-provenance CP-panel-tilt}}

## K4 against K4-Core-K6 {#k4-vs-k6}

{{synthesis S-ckpt-k6-k4}}

## EXLR8 K4 {#exlr8}

{{synthesis S-ckpt-exlr8}}

## How often each differs from BF16 {#how-often}

{{cite V4-per1000-top-token V4-per1000-confident V4-per1000-pb}}

## Not measured {#limits}

- Task accuracy of K4 against K4-Core-K6, except tool calling ([tools](tools.html)).
- Checkpoints of other producers at the same budget, other than EXLR8 K4.

## Changes {#changes}

- **2026-11-13** Rebuilt on findings. Corrected: the v5 study said the teacher panel can favour the probe arms'
  experts; it can favour brandonmusic's K4 ([corrections](audit.html#c03)).
