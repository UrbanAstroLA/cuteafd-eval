# Running it: what an operator needs to know

:::answer
**CuteAFD v4.0.0 holds a larger KV pool and starts in about a minute and a half**; the vLLM fork takes four to six
minutes with its JIT caches kept between starts (*established*). **CuteAFD repeats requests bit for bit**; the vLLM
fork varies beyond its first prefill chunk (*established*). **CuteAFD reuses repeated prompts**; the vLLM fork only
in whole large blocks (*supported*).
:::

## Capacity and startup {#capacity}

<span id="startup"></span>

{{synthesis S-run-capacity}}

{{cite SU-phases SU-populate K4-startup-time K4-b-fit}}

## Repeatability {#determinism}

{{synthesis S-run-determinism}}

## Prefix cache {#prefix-cache}

{{synthesis S-run-prefix}}

## Thinking off and control tokens {#thinking-off}

{{cite V3-think-off K4-smoke V3-i2-inputs}}

## Launcher defaults {#launcher}

{{cite V3-obs-launcher VC-fp8-path-context}}

## Launch files measured {#configs}

The files that ran, as published. Local paths in published copies are placeholders.

{{file repro/cuteafd/configs/glm53-flash-exl3-k3.25-core-fp8-2rtx.config}}

{{file repro/k4/cuteafd/glm53-flash-exl3-k4-2rtx.config}}

{{file repro/k4/vllm/env.sh}}

More configurations, including every follow-up arm: [repro/](https://github.com/UrbanAstroLA/cuteafd-eval/tree/main/repro)
and each run's `configs/` folder; v5 launches are in the [v5 record](v5.html).

## Changes {#changes}

- **2026-11-13** Rebuilt on findings; launch files are shown as published rather than retyped. Corrected: v3.0.1's
  K4 pool was measured with a desktop on one GPU ([corrections](audit.html#c29)).
