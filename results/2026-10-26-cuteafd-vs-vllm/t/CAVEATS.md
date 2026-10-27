# Block T caveats (from the 2026-10-27 audit, AUDIT-2026-10-27.md)

- **Inputs are not byte-identical across engines.** The driver salts each request's nonce first line with the run label
  and a timestamp, so the two engines saw different 12-digit nonces (0 of 1,008 shared); prompt bodies are identical.
  The 128K code prompts tokenize 24 tokens longer on CuteAFD: the vLLM stack parses 12 literal `<think>`/`</think>`
  strings in the user text as special tokens, CuteAFD keeps them as text. Effect on throughput: small; on content: the
  model sees slightly different text in those cells.
- **"code" and "json" cells measure reasoning text.** With thinking on and 1,024 output tokens, every reply in those
  cells is still reasoning when it hits the cap, on both engines. Content labels describe the prompt, not the output.
- **Draft policies differ** (vLLM: DFlash2, 3 draft tokens fixed; CuteAFD: its own adaptive DFlash2 with an FP8
  drafter). Acceptance was not recorded for either engine in Block T.
- **Long-input concurrency cells.** Per-stream decode at 32K/128K with 4-16 streams mostly reflects scheduling:
  streams that decode without prefill interleaving run at the same speed on both engines (45.0 vs 45.6, 50.4 vs 49.7,
  95.4 vs 90.5, 72.6 vs 76.6 tok/s). At 32K/128K, 71-92% of batch wall time is before the last first token, so the
  +6-17% aggregate there mostly reflects CuteAFD's faster long prefill.
- **Noise.** A later re-run of CuteAFD (F1-base) shows about ±4-8% per cell; ratios within that range are not
  differences. No drift repeat was run inside Block T; one is declared in FOLLOWUPS.md.
- **Launch deltas** not in the protocol's list: vLLM GPU memory utilisation 0.95 (upstream 0.97; the desktop holds
  ~2 GB on GPU 1), launched with the v0.9.0 stack's start script and the v0.9.2 image.
