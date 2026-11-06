> **EXPLORATORY.** A replication on new questions with a reading rule frozen before the first launch; one machine.

# New GPQA questions (2026-11-06)

The q_b + output-projection result of [`results/2026-11-05-attn-position`](../2026-11-05-attn-position/) rests on 11
questions, the unit its interval is computed over. This run adds 30 GPQA Diamond questions drawn at random (seed
20261106) from those not used before: K4-Core-K6 on the vLLM fork writes 3 replies per question (seeds recorded), the
finished replies become fixed traces, and every arm scores them. Site page: [Thinking length](../../docs/thinking.html).

- `NQ-RESULT.md`: the result as read. `SUMMARY.json`: the numbers. `protocol/`: protocol and `FROZEN.json`.
- `questions.json` (document ids), `analysis/traces-nq.json` (one entry per trace: question, seed, lengths; no token ids),
  `analysis/NQ.json` (readings, per-question deltas, per-reply length, finish and correctness).
- `code/`: question draw and chain; generation used
  [`results/2026-11-02-thinking-length`](../2026-11-02-thinking-length/)'s generator and trace builder, unchanged.

Not published: GPQA question text and the traces' token ids (dataset terms), reply texts, capture and probe dumps.
