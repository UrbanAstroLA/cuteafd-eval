# CuteAFD v4.0.0 against tpurtell's vLLM fork v0.9.2, and three checkpoints (2026-10-30/31)

Measurement under a protocol frozen before the first comparison request (see `RUN.json`). Two RTX PRO 6000 Max-Q
(300 W), GPU only: experts local, no DGX Spark expert nodes; thinking on. CuteAFD v4.1.0 (released after this run) was
read in source, not run: no change to this setup's GLM-5.3-Flash compute path was found. Pages: [Three checkpoints](../../docs/checkpoints.html) and
[CuteAFD v4.0.0](../../docs/v4.html) on the site.

- `SUMMARY.json`: every number on the two pages, with its source block.
- `t/<checkpoint>/T-COMPARE.json`: Block T speed comparison per checkpoint (CuteAFD / vLLM fork ratios, drift, band);
  K4-Core-K6 is arm K in `t/k4/`.
- `q/fullvocab/pa-pair-*.json`: full-vocabulary P-A pairs (window bootstrap).

K4-Core-K6 runs on CuteAFD only: vLLM fork v0.9.2 does not load it.
