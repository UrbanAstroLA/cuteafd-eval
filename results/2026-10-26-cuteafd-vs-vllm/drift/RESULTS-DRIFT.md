# Drift results (2026-10-27)

Declared in `../FOLLOWUPS.md`. Same driver, seeds and nonce salt as each engine's own Block T run (prompt token
counts identical in 16/16 matched cells): inputs 1K and 32K, 1 and 8 streams, code and prose, replicates 0-1.
Ratio = later run / Block T run, per cell.

| Engine | Later run | Decode per-stream, median (range) | Aggregate, median (range) |
|---|---|---|---|
| CuteAFD | ~3 h after its Block T | 0.981 (0.958-1.065) | 0.990 (0.971-1.029) |
| vLLM | ~7.5 h after its Block T, fresh launch | 1.021 (0.931-1.126) | 1.013 (0.935-1.125) |

Reading: no systematic drift at the median; single cells vary by up to about ±13%, so Block T ratios within about
±10% are not differences. vLLM draft acceptance over this subset: 1.53 of 3 drafted tokens per verify step (51%).
GPU telemetry from 01:06 (first sample; the file name says 0050) (`../gpu-telemetry-from-0050.csv`): both GPUs at the 300 W power cap while busy;
GPU 0 median 1,890 MHz / 87 °C, GPU 1 2,100 MHz / 85 °C; throttle reason: software power cap.
