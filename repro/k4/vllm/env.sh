# Recipe: glm53-flash-exl3-k4@tpurtell+v0.9.2  (draft-untested until captured; K4 measurement, 2026-10-27)
# tpurtell v0.9.2 release image (same digest as the K3.25 recipe) serving brandonmusic GLM-5.3-Flash tr3-4bpw ("K4",
# a5fee929) via the v0.9.0 launcher's MODEL_PROFILE=k4. Same settings as the K3.25 v0.9.2 recipe; the stack's
# local-env.sh overlay (JIT caches on <data>, malloc_trim stopgap) applies unchanged.
#   source <k4-recipe>/env.sh && cd <vllm-stack> && ./local-start.sh
export MODEL_PROFILE=k4
export GPU_MEMORY_UTILIZATION=0.95
export IMAGE=sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2
