# Multi-turn tool calling: CuteAFD v4.0.0 and tpurtell's vLLM fork v0.9.2 (2026-11-02)

A functional check of multi-turn tool calling on both engines with
[tool-eval-bench](https://github.com/SeraphimSerapis/tool-eval-bench) (commit `cf54b4b`, all 88 scenarios including
Hard Mode). Two RTX PRO 6000 Max-Q, GPU only, no DGX Spark expert nodes; thinking on. Site page:
[Tool calling](../../docs/tools.html).

- `SUMMARY.json`: per arm and repeat, points of 176, pass / partial / fail, the harness's own scores (final score,
  rating, responsiveness, deployability, safety gate), category points, and every scenario's status per repeat.
- `rows.csv`: one row per arm, repeat and scenario: status and points. No transcripts, tool arguments or model output.
- `PROTOCOL.md`, `FROZEN.json`, `CORRECTIONS.md`: the frozen protocol, its amendment and a time correction.
- `gate/`: the equal-prompt checks (offline template render and live prompt-token counts per arm).
