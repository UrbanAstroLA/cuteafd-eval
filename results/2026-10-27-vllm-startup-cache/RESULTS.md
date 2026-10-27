# vLLM v0.9.2 startup with JIT caches persisted (2026-10-27)

Change: the stack's env overlay (`local-env.sh`) points `TILELANG_CACHE_DIR`, `TRITON_CACHE_DIR`,
`TORCHINDUCTOR_CACHE_DIR` and `CUDA_CACHE_PATH` into the already persisted `/root/.cache` mount (forwarded by
`start.sh`'s `DEBUG_ENV`). Nothing else changed. Times are from container start to "startup warmup complete".

| Phase | Not persisted | Persisted, warm |
|---|---|---|
| Process start + weight loading | 242 s (weights 135.7 s) | 254 s (weights 139.3 s) |
| TileLang JIT | 222 s (49 compiles) | 0 compiles |
| CUDA graph capture | 153 s | 43 s (58 s phase) |
| Warm-up (4 passes) | ~73 s | ~64 s |
| **Ready** | **697 s** | **382 s** (−45%) |

First start after the change: 714 s (it fills the caches). Persisted cache sizes: TileLang 11 MB, Triton 88 MB,
TorchInductor 6.1 MB, CUDA ComputeCache (root-owned, small). For comparison CuteAFD v3.0.1 is ready in 89 s.
The remaining vLLM time is mostly weight loading (~137 GB at about 1 GB/s, plus loader overhead).
Receipts: `run*-docker.log`, `RESULTS.txt`, `startup.json`, `measure.sh`.
