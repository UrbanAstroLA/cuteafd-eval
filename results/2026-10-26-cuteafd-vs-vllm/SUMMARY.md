# CuteAFD v3.0.1 and vLLM fork v0.9.2 on 2x RTX PRO 6000 Max-Q: evaluation summary (2026-10-26/27)

Both engines are tpurtell's. Model GLM-5.3-Flash EXL3 K3.25 (identical expert bytes; CuteAFD's Core-FP8 checkpoint
carries the official FP8 projections, vLLM's K3.25-v1 the BF16 ones). Frozen protocol `PROTOCOL-DRAFT.md` +
`FROZEN.json`; labelled follow-ups `FOLLOWUPS.md`; separate adversarial review `AUDIT-2026-10-27.md`.
Thinking on for every generation request (the stacks handle thinking off differently; see Observations).

## Precision (teacher-forced, prefill-shaped; `RESULTS-Q.md`, `f1/RESULTS-F1.md`)

| | vLLM (mean of 3 runs) | CuteAFD as shipped | CuteAFD − vLLM | Scored history, tokens (min / median / max) |
|---|---|---|---|---|
| Full-vocab KL, 25 x 2K panel | 0.0458 | 0.0476 | +0.0017 [+0.0006, +0.0028] | 1 / 1,024 / 2,047 |
| Panel P-B, generated rows, all | ~0.0451 | 0.0484 | +0.0033 [+0.0016, +0.0049]; top-1 −0.46 pts | 1,084 / 5,751.5 / 14,402 |
| P-B 0-8K | | | KL within ±0.0017, intervals include 0 | 1,084 / 2,194 / 5,781 |
| P-B 8-16K (long code reading) | | 0.0557 | **+0.0054 [+0.0034, +0.0074]; top-1 −0.81 pts** | 10,284 / 12,069 / 14,402 |
| NLL, human text 32K-128K (no teacher) | | | no difference beyond about ±0.005 nat (6 documents) | 28,672 / 63,487.5 / 131,071 |

Follow-up F1 (CuteAFD switches, 8-16K, vs vLLM mean of 3 runs): W8A16 prefill instead of W8A8 → +0.0022 [+0.0005,
+0.0041] at ~4% longer time to first token and no decode cost; BF16 head → no change at ~6% decode cost; all three
(KDA, head, prefill) → +0.0016 [−0.0005, +0.0033], top-1 −0.08 pts, at ~4% median decode cost. Most of the
difference sits in the W8A8 prefill GEMMs. Decode-shaped precision (the path generated tokens use) was not scored.
CuteAFD is bit-deterministic; vLLM's multi-chunk prefill is not run-to-run deterministic.

## Throughput (Block T, 1,008 requests per engine, 0 errors; `t/T-SUMMARY.md`, `t/CAVEATS.md`)

- Single-stream decode: CuteAFD 1.02-1.41x vLLM (largest on reasoning and code text); vLLM's single-stream decode is
  flat at ~145-150 tok/s from 1K to 128K input.
- End-to-end aggregate: level at 1K-8K, except 1K x 8 streams where CuteAFD is 0.87-0.93x vLLM in all four content
  types (consistent direction, within the per-cell spread); CuteAFD +6-17% at 32K-128K,
  mostly from faster long prefill (4,400-4,500 vs 3,700-3,900 tok/s).
- Time to first token: vLLM faster on 1K prompts (0.25 vs 0.41 s); CuteAFD faster on long prompts at 1 stream,
  slower under long-prompt concurrency (it schedules prefills ahead of decode).
- Repeated prompt: CuteAFD restores from its prefix cache in 0.017 s; vLLM reuses only whole 4,352-token blocks,
  not the last two (F2).
- Drift repeats (identical prompts, later run): medians within ±2% on both engines; per-cell spread ±7-13%.
- Both GPUs ran at the 300 W power cap (GPU 0 ~87 °C, 1,890 MHz median).

## Long output to 128K (Block L, 100 requests per engine, every gate passed; `l/L-analysis-both.json`)

At the 128K cap: code 7/8 full test pass on both (217 vs 212 of 218 tests); MATH-500 level 5 8/8 on both (ceiling);
prose 8/8 stopped on both; JSON valid 6/8 vLLM (both failures the 1,030-record task at the cap) vs 4/8 CuteAFD (field
pattern slips in otherwise complete outputs; n=2 per prompt). CuteAFD replies ran ~15-25% shorter (median prose 39K
vs 49K, code 38K vs 51K tokens); cause not separated from sampling. Decode at 8 streams faster on CuteAFD for
reasoning and JSON, about level on code and prose.

## Observations

- Thinking off: same chat template on both; CuteAFD renders an empty `<think></think>`, the vLLM stack ignores
  `enable_thinking:false` (reasoning arrives in content).
- vLLM prefix cache: 4,352-token block granularity in align mode; prompts below ~13K tokens get no reuse; the v0.9.0
  opt-in boundary lookup (`GLM53_DFLASH_BOUNDARY_LOOKUP`) is off by default (not tested).
- vLLM's multi-chunk prefill: rows beyond the first 2,045-token chunk are not bit-identical run to run.
- CuteAFD launcher: default output limit 4,096 (longer requests are clamped), unconditional `/dev/infiniband`, request logging on
  by default, `0.0.0.0` under host networking; `swiglu_limit` compiled in.
- CuteAFD router: logits differ slightly across its 160/161-row GEMM route switch (prefill only).
- vLLM draft acceptance 1.53 of 3 tokens per step (51%); CuteAFD exposes no acceptance counter.
- Literal `<think>` text in user content is tokenized as special tokens by the vLLM stack, as text by CuteAFD.

## Limits

Two prompt-set sizes are small (Block L n=2 per prompt; Q2 6 documents); teacher-anchored precision stops at 14.4K;
decode-shaped scoring not run; CuteAFD scoring cannot run under load; vLLM Block T ran before GPU telemetry began.
