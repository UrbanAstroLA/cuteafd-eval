# K4e results: CuteAFD W8A16 prefill + amax under the full serving tests (2026-10-28)

Design `FOLLOWUPS-K4e.md` (declared before any request). Same prompts, seeds and grid as the frozen K4 protocol's Block T and Block L runs; one CuteAFD serving launch with `GLM5_FLASH_FP8_PREFILL=off` + `FP8_SCALES=amax`, bracketed by as-shipped
drift subsets. No request errors.

**Machine state.** The two as-shipped drift subsets matched the protocol's Block T drift run (2026-10-27): decode 0.95-1.03x per cell and
content, time to first token within 1.5%; inside the ±8% band, so comparisons against those runs are read.

**Block T (full grid, per cell, medians over content types):**

| Cell (input × streams) | Decode: ÷ as shipped / ÷ vLLM | Aggregate: ÷ as shipped / ÷ vLLM | First token: ÷ as shipped / ÷ vLLM (s) |
|---|---|---|---|
| 1K × 1 | 1.05 / 1.22 | 1.04 / 1.18 | 1.04 / 1.62 (0.43) |
| 1K × 4 | 1.03 / 1.21 | 0.98 / 1.07 | 1.04 / 1.43 (1.30) |
| 8K × 1 | 0.96 / 1.21 | 0.96 / 1.19 | 1.04 / 0.87 (1.91) |
| 8K × 4 | 0.99 / 1.13 | 0.97 / 1.10 | 1.04 / 0.97 (5.52) |
| 32K × 1 | 1.07 / 1.20 | 1.01 / 1.19 | 1.04 / 0.85 (7.68) |
| 32K × 4 | 1.02 / 1.54 | 0.98 / 1.10 | 1.04 / 1.19 (28.67) |
| 128K × 1 | 1.01 / 1.13 | 0.97 / 1.15 | 1.04 / 0.86 (31.19) |

Against CuteAFD as shipped: decode and aggregate level in every cell (inside ±8%); time to first token +4% in every
cell. Against the vLLM fork the as-shipped pattern holds (decode 1.13-1.54x; first token later at 1K and at 32K × 4,
sooner at 8K-128K one stream).

**Block L (descriptive, small n; same seeds as the protocol's Block L):**

| Stage, content | vLLM fork | CuteAFD as shipped | CuteAFD W8A16 + amax |
|---|---|---|---|
| 128K cap, code: all tests pass | 8/8 | 8/8 | 8/8 |
| 128K cap, JSON valid | 5/8 | 3/8 | 6/8 |
| 128K cap, reasoning correct | 8/8 | 8/8 | 8/8 |
| 32K cap, code finished and passing | 0/8 | 5/8 | 2/8 |
| 32K cap, JSON valid | 2/8 | 2/8 | 3/8 |
| median code reply at 128K cap (tokens) | 51,343 | 39,377 | 37,537 |
| median decode, 128K-cap code (tok/s) | 105 | 124 | 123 |
| terminal loops (U5 rule: exact period) | 0 | 0 | 0 |

Every repetition the frozen analyzer flagged is classified "copy from reasoning" (vLLM 9, as shipped 10, W8A16 +
amax 7), as in the protocol's Block L.

Reading: W8A16 + amax serves on 2x RTX with K4 at the as-shipped throughput and +4% time to first token, and its
long-output results match or exceed as shipped on these small samples (JSON 6/8 vs 3/8; code at the 32K cap 2/8 vs
5/8: n = 8 per cell, not separated from sampling).

Files: `t/C-w16amax-r1.json`, `t/C-e-base{1,2}.json`, `l/C-w16amax-r1-*.json`, `l/L-analysis-e.json`,
`l/LOOP-RULES-e.json`.
