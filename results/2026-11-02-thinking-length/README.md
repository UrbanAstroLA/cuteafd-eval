# Thinking length and the 6-bit core of K4-Core-K6 (2026-11-02/03)

Does storing the core of K4-Core-K6 (attention, dense and shared-expert projections, output head: 316 tensors) in 6 bits
instead of BF16 make the model think longer? Every arm runs the same engine and loader; only the core tensors differ.
Site page: [Thinking length](../../docs/thinking.html).

**Engine.** tpurtell's vLLM fork v0.9.2 release image plus a **local loader modification** (not a tpurtell release):
it rebuilds the 6-bit EXL3 core to BF16 at load so the fork can serve this checkpoint, and, for the swap arms, loads
the original BF16 tensors of chosen groups instead. Code, build and checks: [`repro/vllm-k6-loader`](../../repro/vllm-k6-loader/).

- `SUMMARY.json`: every number on the page, with its source file.
- `G0-RESULT.md`, `G2-RESULT.md`, `G4-RESULT.md`, `LOOP-CHECKS.md`: the results as read, with their corrections.
- `protocol/`: the frozen plan (excerpt), Amendment 1, the G4 protocol and the three freeze manifests.
- `analysis/`: per-trace G2 scores (`G2-SCORES.json` frozen chain, `G2-SCORES-A1.json` with the second 6-bit launch),
  the G4 reading, the post-hoc contrasts and loop checks, `samples.csv` (one row per G1b and G4 sample: seed, finish,
  class, tokens, detector check; no text), and the scripts that compute them.
- `code/`: the chains, launch wrapper, generator, trace builder and capture plugin 0.3 as run. `g0/`: the BF16-core
  check and the loader swap test.

Not published: reasoning texts and GPQA question text (model output; dataset terms), the capture dumps (top-64
log-probabilities of model output, 0.9 GB) and the BF16 core file (14.56 GiB, a ranged copy of the BF16 source).
