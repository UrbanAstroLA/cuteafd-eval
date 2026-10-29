> **EXPLORATORY.** A feasibility pilot with one request per prompt and engine, not part of a frozen protocol. It shows whether each engine accepts and answers very long prompts; it is not a quality result and is never placed in a table with measured results.

# Needles at 256K, 512K and 1M tokens on both engines (K3.25, 2026-10-27)

Both engines with the K3.25 checkpoint and their serving settings (vLLM fork v0.9.2, CuteAFD v3.0.1), thinking on,
temperature 1.0, top_p 0.95, `max_tokens` 16,384, one request at a time on an otherwise idle server, the same seed per
prompt on both engines. Prompts follow tpurtell's two needle designs from his vLLM fork (`scripts/test-long-context.py`:
one secret code near the start; `scripts/test-multi-needle-vllm.py`: six KEY=VALUE records at 5%, 25%, 50%, 75%, 95% and
99% of the prompt), built with the K3.25 tokenizer at exactly 262,144, 524,288 and 1,000,000 content tokens, each with
its own nonce in the first line. A cell completes if the reply finishes on its own within the cap; "found" means the
code appears in the reply after the reasoning, "6/6 in order" that all six records are returned in document order.

| Prompt | Prompt tokens | First token, vLLM fork | First token, CuteAFD | Reply tokens, vLLM fork | Reply tokens, CuteAFD | Finish (vLLM / CuteAFD) | Result (vLLM / CuteAFD) |
|---|---|---|---|---|---|---|---|
| single-256k | 262,156 | 62.5 s | 58.0 s | 77 | 74 | stop / stop | found / found |
| six-256k | 262,156 | 63.2 s | 58.5 s | 194 | 212 | stop / stop | 6/6 in order / 6/6 in order |
| single-512k | 524,300 | 132.2 s | 123.2 s | 69 | 135 | stop / stop | found / found |
| six-512k | 524,300 | 129.8 s | 122.5 s | 218 | 365 | stop / stop | 6/6 in order / 6/6 in order |
| single-1m | 1,000,012 | 270.5 s | 255.4 s | 79 | 108 | stop / stop | found / found |
| six-1m | 1,000,012 | 269.7 s | 254.2 s | 220 | 227 | stop / stop | 6/6 in order / 6/6 in order |

Started 2026-10-27T13:03:15-0700 (vLLM fork) and 2026-10-27T13:20:18-0700 (CuteAFD). Files: `V1-pilot.json`, `C1-pilot.json` (per request: seed, usage, timings,
finish reason, character counts, the check result; the reply text is not published), `prompts-index.json` (each
prompt's id, nonce, seed, expected answer, needle placements and sha256). The prompt texts and the script that built them
are not published; the hashes identify each prompt.
