> **EXPLORATORY.** Follow-ups to the thinking-length investigation: criteria written before computing, one frozen vLLM arm; not a full protocol.

# Position analysis and the q_b + output-projection arm (2026-11-05)

Two follow-ups to the [thinking-length investigation](../2026-11-02-thinking-length/), both on its 93 fixed GPQA traces.
Site page: [Thinking length](../../docs/thinking.html).

- **Position (zero GPU).** From the existing dumps of both engines: does the divergence between arms, or the stop-decision
  difference, grow with position along the trace? Criteria written before computing: `NOTE.md`. Result:
  `analysis/POSITION.json`.
- **q_b + output projections together (vLLM fork).** The two groups that met G2's rule (MLA q_b, MLA output) plus the KDA
  output projection, 56 tensors loaded as native BF16, against K4-Core-K6, two launches each, interleaved. Frozen before the
  first launch (`protocol/FROZEN-QBO.json`). Result as read: `QBO-RESULT.md`; numbers `analysis/QBO.json`; the post hoc
  comparison with the whole-core swap `analysis/POSTHOC-QBO-ALL.json`. **Read with**
  [`results/2026-11-06-new-questions`](../2026-11-06-new-questions/): on 30 new questions the shift does not appear.
- **CuteAFD.** v4.0.0 refuses a partial native core (every layer's attention and FFN groups must be native together), so
  the attention-only arm planned for CuteAFD did not load (`NOTE.md`). The 6-bit arm, relaunched for it, scored the 10
  longest traces bit-identically to the stored dumps of two days earlier (`analysis/S2-IDENTITY-CHECK.json`).

`SUMMARY.json` holds every number used on the page. Not published: the capture dumps (top-64 log-probabilities of model
output on GPQA-derived traces).
