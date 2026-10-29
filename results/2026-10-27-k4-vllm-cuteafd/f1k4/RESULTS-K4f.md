# K4f results: high concurrency on K4, vLLM fork and CuteAFD (2026-10-29)

Design `FOLLOWUPS-K4f.md` (declared before any request). The cells the frozen grid dropped that both engines admit,
on the protocol's Block T prompts, seeds and nonce salt; one serving launch per arm; no request errors. Prompt-token
counts identical except the 128K code prompts on CuteAFD (literal `<think>` text, as in the protocol).

**Machine state.** Drift subsets after the vLLM and CuteAFD side cells matched 2026-10-27: decode 0.95-1.03x on both
engines; time to first token within 2% except one vLLM cell (1.12x).

Medians over content types and replicates; 1,024 output tokens per request; per-stream decode = tokens per second of one
request; aggregate = all tokens finished per second.

| Cell (input × streams) | Decode per stream, tok/s (vLLM / CuteAFD / W8A16+amax) | Aggregate, tok/s | CuteAFD ÷ vLLM, aggregate | First token, s | CuteAFD ÷ vLLM, first token |
|---|---|---|---|---|---|
| 1K × 8 | 52 / 58 / 58 | 370 / 370 / 369 | 1.00 | 1.52 / 2.84 / 2.95 | 1.87 |
| 1K × 16 | 33 / 36 / 36 | 322 / 465 / 459 | 1.44 | 2.49 / 4.44 / 4.62 | 1.78 |
| 8K × 8 | 41 / 45 / 44 | 224 / 235 / 230 | 1.05 | 9.91 / 9.96 / 10.37 | 1.01 |
| 8K × 16 | 24 / 26 / 26 | 195 / 267 / 262 | 1.37 | 18.3 / 19.2 / 20.0 | 1.05 |
| 32K × 8 | 23 / 42 / 43 | 93 / 101 / 98 | 1.09 | 41.0 / 54.4 / 56.6 | 1.33 |
| 128K × 2 | 66 / 104 / 112 | 25 / 29 / 28 | 1.15 | 58.2 / 59.7 / 62.2 | 1.03 |

Reading (±8% band):
- **Throughput under load:** level at 1K × 8 and 8K × 8; CuteAFD ahead at 16 streams (1.37-1.44x), at 32K × 8 (1.09x)
  and 128K × 2 (1.15x). On K3.25, 1K × 8 favoured the vLLM fork by 7-15%; on K4 it is level.
- **First token under load:** the vLLM fork answers short prompts sooner with many requests in flight (1K: 1.8-1.9x
  sooner); level at 8K and 128K × 2; the vLLM fork sooner at 32K × 8 (1.33x). Mechanism as on K3.25: the vLLM fork
  interleaves chunked prefill with decode; CuteAFD's prefill is faster per request but queued requests wait.
- **W8A16 + amax** matches CuteAFD as shipped at high concurrency: aggregate 0.97-1.00x, first token +4% in every cell.
- 32K × 16 not run: CuteAFD's K4 KV pool (447,488 tokens) does not hold 16 × 33,792.

Files: `t/V-side.json`, `t/C-side.json`, `t/C-w16amax-side.json`, `t/{V,C}-f-drift.json`, `K4f-cells.json`.
