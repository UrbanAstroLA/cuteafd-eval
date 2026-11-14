# Tool calling

:::answer
**All five arms score within a few points of each other** on a multi-turn tool-calling benchmark, and the engines
differ on a handful of scenarios (*supported*). **CuteAFD's results repeat exactly across seeds**; the vLLM fork's
change on a few scenarios.
:::

{{synthesis S-tools}}

## Details {#details}

{{cite TC-status-counts TC-turn-time TC-gate-r2}}

## Not measured {#limits}

- Other tool-calling benchmarks, or thinking off.
- K4-Core-K6 on the vLLM fork.

## Changes {#changes}

- **2026-11-13** Rebuilt on findings. Corrected: on K3.25 the engines ran different checkpoint variants
  ([corrections](audit.html#c42)).
