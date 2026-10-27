> **EXPLORATORY.** A one-GPU microtest of one CuteAFD kernel, not part of the frozen protocol; approximate router inputs. Not compared with any measured result.

# CuteAFD router logits across the 160/161-row route switch (2026-10-26)

Why it was run: a source audit of CuteAFD could not determine from source whether the router logits are bit-identical across the switch between its skinny GEMV route (up to 160 rows) and its TMA tensor-core route (above). Files: `e1_router_route.py` (the test), `e1-router-route.json` (all cells), `e1-router-route.log`.

## Method and result

`e1_router_route.py`, one GPU, in the CuteAFD image. Same kernel class the served router program builds
(`RoutedBf16Projection(288, 4096, FP32 out)`), JIT-compiled from the image's source, not the served AOT
binary. Real router weights and correction biases of layers 3, 12, 24, 36, 44. Approximate router inputs
(normalized embedding rows, and random rows, times the post-attention norm weight); the real input
(the mHC-collapsed residual) was not reproduced. 64,000 rows per comparison.

| Comparison | Logits bit-identical | Max abs logit difference | Top-8 set changed |
|---|---|---|---|
| Skinny route at 160 rows vs TMA route at 161 rows | 0.35-0.37% of logits | 1.7e-5 to 8.2e-5 | 2 of 64,000 rows |
| Skinny at 160 vs skinny at 100 rows | 100% | 0 | 0 |
| TMA at 161 vs TMA at 512 rows | 100% | 0 | 0 |
| Skinny vs FP64 reference | | max error 1.0-1.6e-7 of the largest logit | 0 rows |
| TMA vs FP64 reference | | max error 5.3-6.8e-6 of the largest logit | 2 rows |

Where the top-8 set agreed, routing weights differed by at most 8.0e-7. Both routes accumulate in FP32;
the TMA route's error is larger but within an FP32 dot product's rounding.

Reading: logits are **not** bit-identical across the switch; within each route they do not depend on the
row count. Expert selection changed in 2 of 64,000 rows, both when the TMA route moved a near-tie away from
the FP64 choice. Exposure: launches above 160 rows are prefill chunks; decode steps stay on the skinny route.
This is numerical variation between routes, the same kind as observed on the vLLM engine (its E1).
