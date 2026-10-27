#!/usr/bin/env bash
# Stage 0 prompt build: CPU only, no network, no GPU, no sudo.
# Usage: run_build.sh SCRATCH_DIR
#   1. copies vllm/**/*.py out of the vLLM v0.9.2 image (a --network none container running tar);
#   2. runs build_prompts.py in the CuteAFD image (python 3.12, tokenizers 0.22.2, pyarrow, jinja2) with
#      the datasets, sources and tokenizer mounted read-only and stage0/prompts writable.
# No `set -e`: each step's exit code is checked explicitly.
VLLM_IMAGE=sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2
CPU_IMAGE=sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a
HERE=$(cd "$(dirname "$0")" && pwd)
PROMPTS=$(dirname "$HERE")
SCR=${1:?usage: run_build.sh SCRATCH_DIR}
mkdir -p "$SCR/vllm_src"
docker run --rm --network none --entrypoint sh "$VLLM_IMAGE" -c \
  'cd /usr/local/lib/python3.12/dist-packages && find vllm -name "*.py" -type f | LC_ALL=C sort | tar -cf - -T -' \
  | tar -xf - -C "$SCR/vllm_src"
rc=("${PIPESTATUS[@]}")
if [ "${rc[0]}" -ne 0 ] || [ "${rc[1]}" -ne 0 ]; then echo "source copy failed: ${rc[*]}" >&2; exit 1; fi
docker run --rm --network none --user "$(id -u):$(id -g)" -e CUDA_VISIBLE_DEVICES= --entrypoint python3 \
  -v <datasets>/2026-10-26-engine-compare:/ds:ro \
  -v "$SCR/vllm_src":/vsrc:ro \
  -v <hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K3.25-v1:/repo:ro \
  -v "$PROMPTS":/out \
  "$CPU_IMAGE" /out/build/build_prompts.py
rc=$?
if [ $rc -ne 0 ]; then echo "build failed: $rc" >&2; exit $rc; fi
echo "build ok"
