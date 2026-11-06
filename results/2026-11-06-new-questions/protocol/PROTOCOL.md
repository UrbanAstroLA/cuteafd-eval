# New GPQA questions: does the q_b + o_proj stop-decision shift hold beyond the 11 questions? (frozen 2026-11-06)

Exploratory; follows `results/2026-11-05-attn-position/QBO-RESULT.md` (+0.0118 [+0.0047, +0.0205] in log p(`</think>`)
at the close, qbo minus K4-Core-K6, 11 questions). The interval there is clustered by question; repeat launches only
measured engine noise (0.0018). The unit that limits it is the question, so this run adds questions.

## Traces
- Questions: 30 GPQA Diamond documents drawn by `select_questions.py` (Random(20261106)) from the 198 minus the 12
  already used (79, 13, 127, 88, 121, 90; 186, 12, 81, 120, 86, 74): `questions.json`.
- Generation: K4-Core-K6 on the vLLM fork, route b, no swap (on-policy for the baseline), the thinking-length run's
  `drivers/gen_traces.py` unchanged: lm-eval's GPQA rendering, temperature 1.0, top_p 0.95, thinking on, cap 327,680,
  3 samples per question, seed 60000 + 100 * doc + rep (recorded), 4 in flight, wall budget 3 h (requests running at the
  cut are kept as unfinished).
- Set nq: the thinking-length run's `traces/build_traces.py` unchanged (checked: it rebuilds the earlier on-policy set
  token-identically): every finished sample of <= 96K completion tokens (up to 3 per question), 1 not-finished per
  question (first 32K tokens), stored rows every 64th reasoning row + the last 512.

## Arms
- vLLM fork v0.9.2-experimental, route b, pinned image, the swap launch script unchanged: k6-a, qbo-a, all, k6-b, qbo-b
  (qbo = mla_q_b, mla_o, kda_o native BF16, 56 matrices; all = whole core BF16, 316). Loader counts checked at every launch.
- CuteAFD v4.0.0 (stage run only with `--with-cuteafd`): C-K6 (6-bit core) and C-K6x (BF16 core, FP8 at load), score
  configs, `probe_traces.py` unchanged. One launch each: CuteAFD scoring was bit-identical across launches and days.

## Reading (analyze_nq.py, written before the first launch)
Every difference is the BF16 side minus the 6-bit side; positive = more ready to stop where the trace stopped.
- **Primary**: lp_close, qbo minus k6 (launch means), finished traces of the new questions only, 95% bootstrap clustered
  by question (2000, seed 20261106).
  - **Replicated** if the interval excludes 0 on the positive side, the estimate exceeds the launch band (largest
    within-arm launch difference) and all four cross-launch pairings are positive.
  - **Opposite direction** if the interval excludes 0 on the negative side and exceeds the band.
  - Otherwise **not replicated at this size**; reported with whether +0.0118 lies inside the new interval.
- **Secondary** (stated now; was post hoc before): qbo minus all, all minus k6 (whole core BF16 is one launch);
  hazard and last-512 mean log p for each; all 41 questions pooled (the 93 earlier traces, scored by the qbo run's
  launches, plus nq); per-question deltas.
- **CuteAFD**: C-K6x minus C-K6 on nq (deterministic, so the rule is "the interval excludes 0"); pooled with the core-swap
  step 2 (11 questions); on the same traces, vLLM all minus k6 against CuteAFD C-K6x minus C-K6 (means, per-trace
  correlation; descriptive).

## Descriptive (tracked in every run, not part of any rule)
- Generation: thinking length (completion tokens) per sample and per question, finish classes (ok, loop, exhaust,
  unfinished at the cut), accuracy on finished replies (local-gpqa-score's frozen extractor), per-request tok/s.
- Scoring, every arm on every nq trace: trace NLL (mean chosen-token -log p over stored rows), top-1 agreement and top-64
  KL against k6-a.

## Scope
GPQA reasoning only (where free generation showed no length difference); the stop decision, not thinking length. Traces
are on-policy for K4-Core-K6 on vLLM, off-policy for every other arm and for CuteAFD. GPQA text stays unpublished
(document ids only).
