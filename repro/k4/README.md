# K4 launch files

The exact launch settings of the K4 measurement (`results/2026-10-27-k4-vllm-cuteafd/`). Only the K4 files are here;
the K3.25 configs are in `../cuteafd/configs/`.

| File | What it is |
|---|---|
| `vllm/env.sh` | vLLM fork v0.9.2: the recipe sourced before the v0.9.0 repository's start script (`MODEL_PROFILE=k4`, `GPU_MEMORY_UTILIZATION=0.95`, the image digest) |
| `cuteafd/glm53-flash-exl3-k4-2rtx.config` | CuteAFD v3.0.1 serving launch (Block T, Block L, startup): engine defaults plus `MAX_CONTEXT_TOKENS=262144`, the listen address, request logging off and `MAX_OUTPUT_TOKENS=393216` |
| `cuteafd/glm53-flash-exl3-k4-2rtx-score.config` | the Block Q scoring launch: the serving settings plus `ENABLE_BENCH=on`, an API key file, `FULL_PREFILL_LOGITS=on` and `PREFIX_CACHE_ENTRIES=0` |
| `cuteafd/glm53-flash-exl3-k4-2rtx-f1c.config`, `cuteafd/glm53-flash-exl3-k4-2rtx-score-f1c.config` | follow-up F1-K4: the serving and scoring launches with `GLM5_FLASH_FP8_PREFILL=off` (W8A16 prefill) |

Placeholders (`<cuteafd>/`, `<secrets>/` and so on) stand for local paths. The CuteAFD configs are used with the
launcher of tpurtell/cuteafd v3.0.1 and the infiniband guard in `../cuteafd/patches/`:
`./run.sh --config <file> [--dry-run]`. The checkpoint is brandonmusic's
[`brandonmusic/GLM-5.3-Flash-tr3-4bpw`](https://huggingface.co/brandonmusic/GLM-5.3-Flash-tr3-4bpw) @ `a5fee929`
(attribution: `../../NOTICE.md`).
