# Local loader modification: K4-Core-K6 on tpurtell's vLLM fork v0.9.2

**Not a tpurtell release.** tpurtell's vLLM fork v0.9.2 does not load `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6`
(its core and head are stored as 6-bit EXL3; the fork expects them in BF16, as in K4). This modification, built
locally on top of the fork's v0.9.2 release image, rebuilds every non-expert EXL3 matrix (316 core and head matrices,
8 in the K4 MTP block) to a BF16 `.weight` while the weights stream in. The routed experts keep the fork's own EXL3
path, so the model is built and loaded exactly like K4. With the switch unset, every edited line is a no-op and the
image behaves as the release. Used by the [thinking-length investigation](../../results/2026-11-02-thinking-length/)
and its earlier precision check against K4.

| File | What |
|---|---|
| `exl3_core_dequant.py` | the new module (installed as `vllm/model_executor/layers/quantization/exl3_core_dequant.py`): config split, decoder, exact reconstruction, loader generator |
| `swap/exl3_core_dequant.py` | the same module plus the swap switch used by the thinking-length investigation (mounted over the installed one); identical behaviour when the swap variables are unset |
| `local-port-exl3-core-dequant.py` | installs the module and edits three files; each anchor must match exactly once or the build fails |
| `local-exl3-core-dequant.diff` | the resulting diff of the three edited files (17 lines added, 2 replaced) |
| `local-k6dequant.Dockerfile` | `FROM` the v0.9.2 release image by digest, port, marker check, `py_compile` |
| `local-make-overlay.sh` | model directory of hardlinks plus `quantization_config.json` (the launcher requires it; the checkpoint ships `quantize_config.json`) |
| `local-env.sh`, `local-start.sh`, `recipe-k4-core-k6-env.sh` | environment, then tpurtell's v0.9.0 `start.sh` unmodified |

**Switches.** `LOCAL_EXL3_DEQUANT_NONEXPERT=bf16` turns the rebuild on. Swap arms add
`LOCAL_EXL3_CORE_BF16_FILE=<safetensors of original BF16 core tensors>` and `LOCAL_EXL3_CORE_BF16_SET=<groups>` (`kda_q`,
`kda_k`, `kda_v`, `kda_o`, `mla_q_a`, `mla_kv_a`, `mla_q_b`, `mla_o`, `dense_gate_up`, `dense_down`, `shared_gate_up`,
`shared_down`, `lm_head` or `all`), optionally `LOCAL_EXL3_CORE_BF16_LAYERS=<a>-<b>`. Each swap launch logs how many
matrices it loaded from the file.

**Numerics.** W_eff = diag(suh) · H · W_inner · H · diag(svh) (block-diagonal Hadamard of order 128 on both sides),
W_inner the fp16 trellis decode ported from b12x's reference decoder; computed exactly in fp64 and rounded once, to
nearest-even, to BF16. The producer's own rebuild rounds at FP16 between stages: the two differ in 15.8% of elements
(median), 2.4% by more than one BF16 unit.

**Checks** (CPU unless marked):

| Check | Result |
|---|---|
| Decoder against b12x's numpy reference | bit-exact on 20 random K2-K6 payloads and 23 real matrices of every shape class |
| fp64 reconstruction | exact against rational arithmetic (12,288 elements); BF16 rounding correct on 8M values |
| 324 rebuilt matrices against K4's BF16 tensors (same BF16 source) | NMSE median 3.88e-4 (K6), 5.8-7.5e-3 (K4 MTP); quantization error over the producer's recorded error: median 1.000 (0.80-1.22) |
| BF16 rounding | median 0.7% of the quantization NMSE |
| Load on GPU | 316 matrices rebuilt on both ranks; loaded-weight hashes equal the CPU table; weight ledger per rank equal to K4's |
| Teacher panel (P-A, full vocabulary, two launches) | K4-Core-K6 0.0306 against K4 0.0246 on the same image (+0.0060 [+0.0021, +0.0099]); the two K4-Core-K6 launches bit-identical. CuteAFD v4.0.0, which runs the 6-bit core natively, measured 0.0297 on the same panel |
| Swap switch (thinking-length G0) | named groups load the BF16 file bit for bit, the others equal the rebuild bit for bit; an unknown group or missing file raises ([`g0/swap-test.json`](../../results/2026-11-02-thinking-length/g0/swap-test.json)) |
| BF16 core file (316 tensors, ranged from `zai-org/GLM-5.3-Flash-BF16` @ `f9fed3bb`) | every tensor within 6-bit error of the rebuilt one: relative error 0.019-0.025 ([`g0/core-check.json`](../../results/2026-11-02-thinking-length/g0/core-check.json)) |

Build (offline, from the release image already on disk):

```bash
docker build --pull=false --network none -f local-k6dequant.Dockerfile -t local/glm53-flash:v0.9.2-experimental .
```

Published copies carry this repository's naming (`LOCAL_` switch prefix, `local-` file and marker names); the copies
that ran differ only in that name. Licence: Apache-2.0, as the vLLM files it edits.
