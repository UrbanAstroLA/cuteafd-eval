# Speed

:::answer
**CuteAFD v4.0.0 is faster than the vLLM fork or level with it in every cell measured** on K3.25 and K4
(*established* for this machine). v3.0.1 was slower at short prompts with many streams and in first-token time at
1K and with many long prompts. **K4-Core-K6 runs slower than K4** on CuteAFD (*indicated*).
:::

## Engine against engine {#engines}

{{synthesis S-speed-engines}}

## The 6-bit core {#core}

{{synthesis S-speed-k6}}

## Per-cell results {#cells}

{{cite V4-speed-k325-ratios V4-speed-k4-ratios V4-speed-k6-ratios V3-t-decode-single V3-t-decode-longctx V3-t-ttft K4-t-decode K4-t-ttft}}

## Every cell {#tables}

The full grids, rendered from each run's published files. Ratios are read against each run's noise band.

:::more CuteAFD v4.0.0 against the vLLM fork, K3.25 {#tables-v4-k325}
{{table speed_cells results/2026-10-30-cuteafd-v4/t/k325/T-COMPARE.json}}
:::

:::more CuteAFD v4.0.0 against the vLLM fork, K4 and K4-Core-K6 {#tables-v4-k4}
{{table speed_cells results/2026-10-30-cuteafd-v4/t/k4/T-COMPARE.json}}
:::

:::more CuteAFD v3.0.1 against the vLLM fork, K4 {#tables-v3-k4}
{{table speed_cells results/2026-10-27-k4-vllm-cuteafd/t/t-compare.json}}
:::

:::more CuteAFD v3.0.1 against the vLLM fork, K3.25 {#tables-v3-k325}
{{include results/2026-10-26-cuteafd-vs-vllm/t/T-SUMMARY.md noid}}
:::

## Caveats {#caveats}

Speeds are per stream or aggregate under the grid's own load, with thinking on; code and JSON cells mostly measure
reasoning text. Noise bands come from each run's drift repeats, and the engines' speculative drafting differs.

{{cite V3-m2-labels V3-m2-draft V3-drift K4-t-drift V3-telemetry}}

## Changes {#changes}

- **2026-11-13** Rebuilt on findings. Corrected: the v4 summary's ±8% band was 8.85% on K3.25
  ([corrections](audit.html#c24)); the v3.0.1 single-stream speedup range ([corrections](audit.html#c14)).
