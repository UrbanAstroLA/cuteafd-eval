# K4f: high concurrency on K4, vLLM fork and CuteAFD (declared 2026-10-29, before any K4f request)

Follow-up outside the frozen K4 protocol (FROZEN.json generation 1 and GRID.json unchanged). The
frozen grid stopped at 4 streams (1 at 128K) because the grid was common to all of the protocol's arms (see the method page); the vLLM fork
and CuteAFD both admit more. K3.25 showed their scheduling differences at 4-16 streams.

**Cells** (the cells the frozen grid dropped that both engines admit; `K4f-cells.json`): 1K and 8K at 8 and 16 streams, 32K at 8, 128K at 2; 1,024 output tokens; the Block T prompt set, seeds and
nonce salt as in the protocol (block_t3.py `--subset side` with these cells). 32K x 16 is excluded (CuteAFD's
K4 pool of 447,488 tokens does not hold 16 x 33,792).
**Arms, one serving launch each:** vLLM fork (K4 recipe), CuteAFD as shipped, CuteAFD W8A16 prefill + amax (the K4
setting that serves on 2x RTX). After each of the first two arms' side cells, the Block T drift subset (64 requests)
checks the machine state against 2026-10-27.
**Reported:** per cell and content, decode tok/s per stream, aggregate tok/s and time to first token for each arm;
CuteAFD ÷ vLLM and W8A16+amax ÷ as shipped ratios; the ±8% band; never merged into the frozen three-engine tables.
**Guardrail.** ~3 GPU-hours expected; stop at 5. vLLM K3.25 serving restored at the end on every exit path.
