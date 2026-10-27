> **CHECK.** Deterministic checks of the checkpoint bytes and a source reading, CPU only. Not a comparison of results.

# CuteAFD setup checks (2026-10-26)

**Expert bytes (`bytecheck/`).** The Core-FP8 checkpoint `d31ebc92` is K3.25-v1 `0490d2f7` with 179 projection tensors
replaced by the official FP8 weights. Hashing every tensor of the local K3.25-v1 snapshot against Core-FP8's published
stitch provenance: 150,047 of 150,047 base tensors byte-identical
(140.9 GB), 0 mismatches, 0 missing,
358 tensors from the FP8 source (the 179 weights and their block scales). The provenance file itself is part of the checkpoint repository and is
not copied here.

**FP8 projections (`fp8check/`).** For the 179 replaced tensors: the official FP8, dequantized, differs from
K3.25-v1's BF16 by 0.16% (relative Frobenius norm). Quantizing the BF16 tensors to E4M3 with
amax/448 scales over 128×128 blocks reproduces 99.99998% of the official codes, with
scales within one FP32 ulp (only 37.2% bit-equal).

**Source audit ([`source-audit/audit-vllm-items.md`](source-audit/audit-vllm-items.md)).** CuteAFD v3.0.1's counterparts of the vLLM-engine issues D1-D7 and E1 found in earlier
evaluation, read in source only: D1, D3, D4 and D7 handled correctly; D2, D5 and D6 not applicable to its design; for E1,
the batch-size mechanism does not apply, and route-dependent logits were measured afterwards
(`results/2026-10-26-e1-router-route/`). It also records that `swiglu_limit` is a compiled constant, not read from
`config.json`.
