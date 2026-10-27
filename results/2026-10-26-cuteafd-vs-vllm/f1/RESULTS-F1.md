# F1 results: CuteAFD FP8 switches vs precision and speed (2026-10-27)

Follow-up, outside the frozen protocol; design and reading rule in `../FOLLOWUPS.md` (declared before running,
speed added by amendment A1 before any F1 request). tpurtell's panel P-B, generated rows, prefill-shaped scoring,
his CLI. vLLM reference = mean of the two first-launch vLLM runs (audit correction I1). After F3, against the mean of all three
vLLM runs (two launches): 8-16K C1 +0.0054 [+0.0034, +0.0074], F1c +0.0022 [+0.0005, +0.0041], F1d +0.0016
[−0.0005, +0.0033] (`../q/score/final/pb/pb-vs-vllm-mean3.json`); the reading below is unchanged. Paired 95% window bootstrap.
CuteAFD is bit-deterministic, so one run per arm. Speed: Block T driver subset (1K/8K input, 1 and 8 streams, code
and prose, 2 replicates), each arm ÷ F1-base (C1's scoring launch unchanged).

## 8-16K bucket (long code reading), where CuteAFD differed from vLLM

| Arm | Change | KL | vs C1 | vs vLLM mean | Top-1 vs vLLM | Decode speed | TTFT |
|---|---|---|---|---|---|---|---|
| C1 | as shipped | 0.0557 | — | +0.0050 [+0.0031, +0.0071] | −0.87 pts | 1.00 | 1.00 |
| F1a | KDA projections BF16 (also drops KDA output sharding) | 0.0535 | −0.0022 [−0.0047, +0.0005] | +0.0028 [+0.0007, +0.0052] | +0.06 | 0.92 | 0.98-1.00 |
| F1b | output head BF16 | 0.0555 | −0.0003 [−0.0004, −0.0001] | +0.0048 [+0.0028, +0.0069] | −0.79 | 0.94 | 1.00 |
| F1c | prefill GEMMs W8A16 (not W8A8) | 0.0525 | **−0.0032 [−0.0049, −0.0013]** | +0.0019 [+0.0000, +0.0039] | −0.51 | 0.99 | **1.04** |
| F1d | all three | 0.0519 | **−0.0038 [−0.0063, −0.0013]** | **+0.0013 [−0.0008, +0.0031]** | −0.14 | 0.96 (0.86-1.05) | 1.02-1.04 |

All generated rows: C1 +0.0030 [+0.0013, +0.0048] vs vLLM; F1c +0.0014 [+0.0003, +0.0026]; F1d +0.0007
[−0.0006, +0.0019]. Below 8K no arm differs clearly from C1.

## Reading (rule declared in FOLLOWUPS.md)

- **W8A8 prefill (F1c) accounts for most of the 8-16K difference** in this prefill-shaped measurement: it moves KL
  by −0.0032, more than half the C1−vLLM difference, at about 4% longer time to first token and no decode cost.
- **The FP8 head (F1b) does not**: −0.0003, at about 6% decode cost.
- **KDA FP8 (F1a)** moves top-1 most (+0.93 pts vs C1 at 8-16K) but its KL change is not resolved, at about 8% decode
  cost; it also changes KDA output sharding, so it is not a single-factor test.
- **All three (F1d)** leave no resolved difference from vLLM (KL +0.0013 [−0.0008, +0.0031], top-1 −0.14 pts), at
  about 4% median decode cost (worst cell −14.5%) and 2-4% longer time to first token.
- Scope: W8A8 prefill matters to prefill-shaped scoring and to prompt processing; tokens generated during decode use
  the decode path, which this measurement does not score. Precision of generated text under decode was not measured.
  The MLA, shared and dense projections stay FP8 in every arm (no BF16 option).

Files: `pb-F1-*-prefill.json` (his CLI), `speed-F1-*.json`, `F1-RESULTS.json`, `f1_analysis.py`.
