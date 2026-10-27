# CuteAFD launch files

| Path | What |
|---|---|
| `configs/glm53-flash-exl3-k3.25-core-fp8-2rtx.config` | Serving config (Blocks T and L): 2 RTX, routed experts on the GPUs, no Sparks, DFlash2, image pinned by digest |
| `configs/glm53-flash-exl3-k3.25-core-fp8-2rtx-score.config` | Block Q scoring launch for C1: adds the bench endpoint, API key file, full prefill logits, dump directory |
| `configs/glm53-flash-exl3-k3.25-v1-2rtx-score.config` | Block Q scoring launch for the C0 control (K3.25-v1, FP8 projections quantized at load) |
| `configs/glm53-flash-exl3-k3.25-core-fp8-2rtx-score-f1{a,b,c,d}.config` | Follow-up F1 arms: the scoring launch with one or all optional FP8 paths off |
| `patches/0001-coordinator-infiniband-guard.patch` | The launcher change used here: pass `/dev/infiniband` only when it exists |
| `receipts/dry-run-1.log`, `receipts/dry-run-score.log` | The launcher's resolved plans (`--dry-run`) for the serving and C1 scoring configs |

The configs are copies of the files used, with paths replaced by placeholders (`<cuteafd>`, `<run>`, `<secrets>`).
Their header comment describes them as following tpurtell's 2-RTX v3 release card; the attention placement and index
cache the launcher actually resolved on this machine are recorded in the dry-run plans.

Deltas from the release card, all in the configs: listen address `127.0.0.1:8001`; `USAGE=off` (no request/response
logging); `MAX_OUTPUT_TOKENS=393216` (the engine's ceiling; the launcher's default is 4,096); the Core-FP8 checkpoint with
`GLM5_FLASH_FP8_MODEL_ID=off` (it already carries the official FP8 projections); image pinned by digest.
