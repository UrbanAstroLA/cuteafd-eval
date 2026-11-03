# G0 result (2026-11-02, CPU only)

| Check | Result | Receipt |
|---|---|---|
| BF16 core download (316 tensors, 14.56 GiB, ranged from zai-org/GLM-5.3-Flash-BF16 @ f9fed3bb) | all 316 within 6-bit error of K4-Core-K6's own decoded tensors: relative error 0.0190-0.0246 (median 0.0197), none above 0.05; a misplaced range would read ~1.4 | `g0/core-check.json`, `g0/core-check.log` |
| Loader swap switch (`g0/exl3_core_dequant.py`) | 12 owners, one per group: 6 named groups load the BF16 file bit for bit, 6 others equal the route-b rebuild bit for bit; unknown group and missing file raise. All 316 core names map to a group (34/34/34/34 KDA q/k/v/o, 11 each MLA q_a/kv_a/q_b/o, 84+42 shared, 6+3 dense, 1 head) | `g0/swap-test.json` |
| Capture plugin 0.3 (reduced dumps: top-64, selected ids, chosen token) | full CPU suite passes against the image's own `compute_prompt_logprobs`, including the new reduced-dump test (512 rows exact; 75 KB vs 4 MB) | `capture/tests/test_capture_cpu.out` |
| Trace set | 84 traces from the looping probes (60 finished, 24 not finished; docs 79, 13, 127, 88, 121; doc 121 has no non-finished sample), 5.32M tokens per arm; re-tokenized reasoning / logged tokens median 0.99 | `traces/index.json`, `traces/registry/tr/` |
| Launch wrapper (`start-v092x-swap-capture.sh`) | dry run renders the five extra mounts and the swap env; nothing started | dry-run output in session |

Not yet written: the stop-hazard scorer (reads the reduced dumps), and the G2 chain. Screen measures use reduced (top-64)
dumps on P-A and P-B too, so KL in the screen is a top-64 measure (as Block Q's top-20 measures), not full vocabulary.
