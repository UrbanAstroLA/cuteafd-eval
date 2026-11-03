# Source this before the v0.9.0 launcher for "vLLM fork v0.9.2-experimental" (local loader patch):
#   source <recipes>/<recipe>/env.sh && <vllm-x-stack>/local-start.sh
# The launcher is tpurtell's v0.9.0 start.sh, unmodified, in <vllm-stack> (this stack has
# no copy of it). Every local deviation of the v0.9.0 stack's local-env.sh is carried over below; the only
# new things are the image and, in the K4-Core-K6 recipe, the switch LOCAL_EXL3_DEQUANT_NONEXPERT=bf16.
#
# Image: tpurtell v0.9.2 release (sha256:ea0430aa...) + local-exl3-core-dequant, built locally from
# local-k6dequant.Dockerfile. Switch unset = stock v0.9.2 behaviour, so the K4 control runs the same image.
export IMAGE="${IMAGE:-local/glm53-flash:v0.9.2-experimental}"
# Same JIT/kernel cache as the v0.9.x recipes: the patch touches Python loader code only, no kernels.
export CACHE_DIR=<cache>/vllm-v090
export HF_HOME=<hf-home>
export PORT="${PORT:-127.0.0.1:8001}"   # network rule: publish on loopback only
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"   # upstream 0.97 cannot start beside the desktop on GPU 1
# JIT caches outside ~/.cache kept inside the persisted CACHE_DIR mount (/root/.cache in the container), and the
# malloc_trim stopgap for upstream issue #12 (PYTHONUSERBASE loads <cache>/vllm-v090/local-pyuser/.../
# usercustomize.py, which calls malloc_trim(0) in the workers every LOCAL_MALLOC_TRIM_S seconds). Same values
# as <vllm-stack>/local-env.sh (2026-10-27); start.sh forwards DEBUG_ENV entries as --env.
export DEBUG_ENV="${DEBUG_ENV:-} TILELANG_CACHE_DIR=/root/.cache/tilelang TRITON_CACHE_DIR=/root/.cache/triton TORCHINDUCTOR_CACHE_DIR=/root/.cache/torchinductor CUDA_CACHE_PATH=/root/.cache/nv/ComputeCache PYTHONUSERBASE=/root/.cache/local-pyuser LOCAL_MALLOC_TRIM_S=300"
