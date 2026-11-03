# Recipe: glm53-flash-exl3-k4-core-k6@tpurtell+v0.9.2-experimental  (draft-untested until captured)
# wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6 @5d3fffe1 on "vLLM fork v0.9.2-experimental": tpurtell's v0.9.2
# release image + local loader patch local-exl3-core-dequant (not tpurtell's engine as shipped; his fork
# cannot load this checkpoint). The switch rebuilds the 324 non-expert EXL3 matrices (K6 core and head, K4 MTP core)
# to BF16 at load; the K4 routed experts stay on the fork's b12x path. Model dir: hardlink overlay with
# quantization_config.json (made by <vllm-x-stack>/local-make-overlay.sh).
#   source "<recipes>/glm53-flash-exl3-k4-core-k6@tpurtell+v0.9.2-experimental/env.sh" && <vllm-x-stack>/local-start.sh
export MODEL_PROFILE=custom
export MODEL_ID=wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6
export MODEL_REVISION=5d3fffe1df9c4a109bbbdafb60dc19df9fac019d
export MODEL_DIR_OVERRIDE=<hf-home>/derived/GLM-5.3-Flash-EXL3-K4-Core-K6@5d3fffe1-vllm-overlay
export GPU_MEMORY_UTILIZATION=0.95
export IMAGE=local/glm53-flash:v0.9.2-experimental
# The switch. The stack's local-env.sh appends its own DEBUG_ENV entries after this one.
export DEBUG_ENV="${DEBUG_ENV:-} LOCAL_EXL3_DEQUANT_NONEXPERT=bf16"
