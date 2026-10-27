# vLLM v0.9.2 startup with JIT caches persisted (2026-10-27)

Measurement of startup time from the server logs, outside the frozen protocol. On this setup the stack's environment
overlay points `TILELANG_CACHE_DIR`, `TRITON_CACHE_DIR`, `TORCHINDUCTOR_CACHE_DIR` and `CUDA_CACHE_PATH` into the cache
directory the container already keeps between starts; nothing else changed. Times run from container start to the
"startup warmup complete" line.

| Run | Ready |
|---|---|
| vLLM v0.9.2, JIT caches not persisted | 697 s |
| vLLM v0.9.2, JIT caches persisted (warm) | 382 s |
| CuteAFD v3.0.1 | 89 s |

The first start after the change fills the caches and takes 714 s; later starts are
warm. Phase detail: `RESULTS.md` and `startup.json`. Receipts: `RESULTS.txt`, `measure.sh` and the server logs
(`run*-docker.log`, each cut at its "container is ready" line; later lines are unrelated serving traffic).
