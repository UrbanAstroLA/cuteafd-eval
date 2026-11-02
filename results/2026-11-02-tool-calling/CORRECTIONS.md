# Corrections to frozen text (kept outside PROTOCOL.md so its frozen hash stays valid)

- Amendment 1 says "11:58" and "10 minutes of the first repeat". From the logs: the first repeat on V-K3.25 started
  11:48:19 and the chain was stopped at about 11:49; the amended chain was frozen and started 11:49:33. The text was
  written from memory before the logs were checked.
- Discovery table: "K4-Core-K6's differs (2614a3c8, to check)": checked before the freeze; its template keeps earlier
  reasoning by default like the zai template (`clear_thinking` defaults false), and gate R renders it byte-identical
  with the kwarg. "Results go to ... `2026-11-xx-tool-soak`": published as `results/2026-11-02-tool-calling` (the soak
  was not run). "Gate: per-request usage.prompt_tokens ... on the first request of each scenario": the gate as run is
  the one defined under Block TC (three fixed conversations per arm).
