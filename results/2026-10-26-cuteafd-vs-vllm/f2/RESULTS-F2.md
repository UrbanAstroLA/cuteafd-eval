# F2 results: vLLM v0.9.2 prefix-cache reuse on identical repeated prompts (2026-10-27)

Declared in `../FOLLOWUPS.md`. Normal served v0.9.2 launch (`--enable-prefix-caching --mamba-cache-mode align`),
one stream, `/v1/completions` with exact-length token prompts from a public-domain PG-19 book, each sent 3 times.

| Prompt tokens | Cached tokens, reps 1-3 | TTFT reps 1-3 (s) |
|---|---|---|
| 1,024 | 0, 0, 0 | 0.240, 0.240, 0.240 |
| 4,352 | 0, 0, 0 | 1.125, 1.128, 1.124 |
| 8,192 | 0, 0, 0 | 2.089, 2.086, 2.088 |
| 8,704 | 0, 0, 0 | 2.272, 2.271, 2.270 |
| 17,408 | 4,352, 8,704, 8,704 | 3.457, 2.313, 2.309 |

`/metrics` prefix-cache hit counters agree with the usage field. The server log shows the MLA cache groups at
`block_size 4352` (hybrid KDA state alignment). Observed: reuse in whole 4,352-token blocks, and not the last two
blocks of a prompt; a repeated prompt below about 13K tokens gets no reuse. The v0.9.0 opt-in boundary prefix lookup
(`GLM53_DFLASH_BOUNDARY_LOOKUP`, default 0) was not tested. For comparison, CuteAFD restored a repeated 8K prompt in
0.017 s (Block T cached cell).
