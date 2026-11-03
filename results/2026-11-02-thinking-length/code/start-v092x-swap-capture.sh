#!/usr/bin/env bash
# Thinking-length experiment (2026-11-02): v0.9.2-experimental capture launch for the BF16 core-swap arms.
# Derived from <k4k6-discovery>/vllm-patch/start-v092x-capture.sh (logic unchanged), plus:
#   ARM=k6swap  K4-Core-K6, switch on, and the core groups in SWAP_SET (optionally SWAP_LAYERS a-b) loaded from the
#               original BF16 core file instead of being rebuilt (LOCAL_EXL3_CORE_BF16_*; g0/exl3_core_dequant.py)
#   mounts      g0/exl3_core_dequant.py -> the image's installed module (ro; identical to the image's except the swap
#               switch, which does nothing when unset), bf16-core/ -> /swap (ro); plugin 0.3 (reduced dumps) and the
#               trace registry from this run directory; VLLM_SERVER_DEV_MODE=1 on every arm so the capture driver can
#               POST /reset_prefix_cache before each trace (traces of one question share their prompt prefix).
#               The server stays on 127.0.0.1:8001 (loopback), so the dev routes are not reachable from outside.
# Every ARM mounts the same module, so k6 here equals k6 in the earlier wrapper (switch unset).
#
# Original header follows.
## Start "vLLM fork v0.9.2-experimental" (local loader patch local-exl3-core-dequant) with the
## glm53_capture plugin armed. Copy of <run>/stage0/capture-vllm/start-v092-capture.sh
## (plugin, registry and the start.sh patching unchanged and taken from there), parameterised by ARM:
##   ARM=k6      K4-Core-K6, switch on (LOCAL_EXL3_DEQUANT_NONEXPERT=bf16)
##   ARM=k6dith  K4-Core-K6, switch on + noise A/B arm (LOCAL_EXL3_DEQUANT_DITHER_SEED=${DITHER_SEED:-1})
##   ARM=k4      K4 control, switch off, same image
## Differences from the 10-26 wrapper: recipe env and image per ARM (image pinned by local image ID), the
## experimental stack's local-env.sh, and its DEBUG_ENV entries (JIT caches, malloc_trim stopgap) kept ahead
## of the plugin variables (they do not change numerics; the 10-26 wrapper dropped them).
##
## --- original header ---
##
## The served configuration stays as the recipe has it: DFlash2 K3 speculation,
## prefix caching (+ mamba align), max-num-seqs 16, cudagraph ceiling 64, FP8 MLA
## KV, 0.95 memory, container glm53-flash-exl3-b12x-vllm, 127.0.0.1:8001.
##
## What differs from the normal start (source recipe env.sh; ./local-start.sh):
##   mounts  <plugin dir>   -> /kld-plugin   (ro)
##           <registry dir> -> /kld-registry (ro)
##           <OUT_DIR>      -> /kld-out      (rw)
##   env     VLLM_PLUGINS   image default + ",glm53_capture"
##           PYTHONPATH     "/kld-plugin:" + image default (/opt/b12x:/usr/local/lib/python3.12/dist-packages)
##           GLM53_CAP_ENABLE=1 GLM53_CAP_REGISTRY=/kld-registry GLM53_CAP_OUT=/kld-out/staging
## Nothing else.  The stack's start.sh is not modified: a temporary copy gets the
## three mount lines after its cache mount and its SCRIPT_DIR pointed back at
## the stack; env goes through start.sh's own DEBUG_ENV hook.
##
## IMAGE is exported explicitly.  The stack's local-env.sh defaults IMAGE to
## the v0.9.0 digest (f36dfb87); without the export a run would silently measure
## v0.9.0.  The script refuses to start unless IMAGE is the v0.9.2 digest after
## every file has been sourced.
##
## Usage:
##   OUT_DIR=<run>/vllm-v092-dumps ./start-v092-capture.sh
##   DRY_RUN=1 ./start-v092-capture.sh   # render the full docker run with a stub; start nothing
##
## The normal server must be stopped first (start.sh refuses if the container runs):
##   <vllm-stack>/stop.sh
set -uo pipefail

HERE=<tl-run>/capture   # plugin 0.3
RUN=<tl-run>
MODFILE=${RUN}/g0/exl3_core_dequant.py
MODTARGET=/usr/local/lib/python3.12/dist-packages/vllm/model_executor/layers/quantization/exl3_core_dequant.py
SWAPDIR=${RUN}/bf16-core
TMPDIR_HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STACK=<vllm-stack>                              # start.sh (unmodified upstream launcher)
XSTACK=<vllm-x-stack>                # local-env.sh for the experimental image
PIN_IMAGE=local/glm53-flash:v0.9.2-experimental
PIN_IMAGE_ID="${PIN_IMAGE_ID:?set PIN_IMAGE_ID to the image ID recorded in VALIDATION.md}"
case "${ARM:-}" in
  k6)     RECIPE_ENV="<recipes>/glm53-flash-exl3-k4-core-k6@tpurtell+v0.9.2-experimental/env.sh"; WANT_PROFILE=custom
          ARM_ENV="LOCAL_EXL3_DEQUANT_NONEXPERT=bf16" ;;
  k6dith) RECIPE_ENV="<recipes>/glm53-flash-exl3-k4-core-k6@tpurtell+v0.9.2-experimental/env.sh"; WANT_PROFILE=custom
          ARM_ENV="LOCAL_EXL3_DEQUANT_NONEXPERT=bf16 LOCAL_EXL3_DEQUANT_DITHER_SEED=${DITHER_SEED:-1}" ;;
  k4)     RECIPE_ENV="<recipes>/glm53-flash-exl3-k4@tpurtell+v0.9.2-experimental/env.sh"; WANT_PROFILE=k4
          ARM_ENV="" ;;
  k6swap) [[ -n "${SWAP_SET:-}" ]] || { echo "start-v092x-swap: ARM=k6swap needs SWAP_SET" >&2; exit 2; }
          RECIPE_ENV="<recipes>/glm53-flash-exl3-k4-core-k6@tpurtell+v0.9.2-experimental/env.sh"; WANT_PROFILE=custom
          ARM_ENV="LOCAL_EXL3_DEQUANT_NONEXPERT=bf16 LOCAL_EXL3_CORE_BF16_FILE=/swap/core.safetensors LOCAL_EXL3_CORE_BF16_SET=${SWAP_SET}${SWAP_LAYERS:+ LOCAL_EXL3_CORE_BF16_LAYERS=${SWAP_LAYERS}}" ;;
  *) echo "start-v092x-swap: ARM must be k6, k6swap, k6dith or k4" >&2; exit 2 ;;
esac
PIN_START_SH=e1196cbcd6b4744cb41fdebf3d12d8586dbea464e702af5de47617837efe0e5e
PLUGIN_DIR="${HERE}/plugin"
REGISTRY_DIR="${REGISTRY_DIR:-${RUN}/traces/reg}"
OUT_DIR="${OUT_DIR:?set OUT_DIR}"
IMAGE_PYTHONPATH=/opt/b12x:/usr/local/lib/python3.12/dist-packages
IMAGE_VLLM_PLUGINS=lora_filesystem_resolver,lora_hf_hub_resolver

die() { echo "start-v092x-capture: $*" >&2; exit 1; }

# Overrides that would change the served engine are refused, not passed through.
# (IMAGE, MODEL_PROFILE and GPU_MEMORY_UTILIZATION are set unconditionally by
# the recipe env below and checked afterwards, so a shell that sourced it is fine.)
for v in SPECULATIVE_METHOD DFLASH_TOKENS ENABLE_PREFIX_CACHING MAX_NUM_SEQS \
         MAX_NUM_BATCHED_TOKENS MAX_CUDAGRAPH_CAPTURE_SIZE KV_CACHE_PROFILE KV_CACHE_DTYPE \
         MAX_MODEL_LEN MODEL_ID MODEL_REVISION MODEL_DIR_OVERRIDE \
         CONTAINER_NAME PORT DEBUG_ENV EXTRA_SERVE_ARGS IMAGE LOCAL_EXL3_DEQUANT_NONEXPERT \
         LOCAL_EXL3_DEQUANT_DITHER_SEED LOCAL_EXL3_DEQUANT_DEVICE LOCAL_EXL3_CORE_BF16_FILE \
         LOCAL_EXL3_CORE_BF16_SET LOCAL_EXL3_CORE_BF16_LAYERS; do
  [[ -v "$v" ]] && die "$v is set in the calling environment; unset it (the recipe decides it)"
done

for p in "${STACK}/start.sh" "${XSTACK}/local-env.sh" "${RECIPE_ENV}" \
         "${PLUGIN_DIR}/glm53_capture_plugin/__init__.py" \
         "${PLUGIN_DIR}/glm53_capture-0.3.dist-info/entry_points.txt" "${REGISTRY_DIR}" \
         "${MODFILE}" "${SWAPDIR}/core.safetensors"; do
  [[ -e "$p" ]] || die "missing: $p"
done
have="$(sha256sum "${STACK}/start.sh" | cut -d' ' -f1)"
[[ "${have}" == "${PIN_START_SH}" ]] || die "start.sh sha256 ${have} != pinned ${PIN_START_SH}; re-check this wrapper"
ls "${REGISTRY_DIR}"/*/*.json >/dev/null 2>&1 || die "registry ${REGISTRY_DIR} has no entries (capture.py register)"

# --- environment: recipe, then explicit IMAGE, then the stack's pinned env ---
# shellcheck disable=SC1090
source "${RECIPE_ENV}" || die "cannot source ${RECIPE_ENV}"
[[ "${IMAGE:-}" == "${PIN_IMAGE}" ]] || die "recipe env set IMAGE=${IMAGE:-unset}, expected ${PIN_IMAGE}"
export IMAGE="${PIN_IMAGE}"
export DEBUG_ENV=""   # the recipe's switch entry is re-added explicitly from ARM_ENV below
# shellcheck disable=SC1091
source "${XSTACK}/local-env.sh" || die "cannot source local-env.sh"
[[ "${IMAGE}" == "${PIN_IMAGE}" ]] || die "IMAGE changed to ${IMAGE} after local-env.sh"
[[ "${PORT}" == "127.0.0.1:8001" ]] || die "PORT=${PORT}, expected 127.0.0.1:8001"
[[ "${MODEL_PROFILE}" == "${WANT_PROFILE}" && "${GPU_MEMORY_UTILIZATION}" == 0.95 ]] \
  || die "recipe env gave MODEL_PROFILE=${MODEL_PROFILE} GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION}"
have_id="$(docker image inspect --format '{{.Id}}' "${IMAGE}" 2>/dev/null)" || die "image ${IMAGE} not present locally (no pull from here)"
[[ "${have_id}" == "${PIN_IMAGE_ID}" ]] || die "image ${IMAGE} is ${have_id}, expected ${PIN_IMAGE_ID} (rebuilt?)"

export DEBUG_ENV="${DEBUG_ENV} ${ARM_ENV} VLLM_SERVER_DEV_MODE=1 VLLM_PLUGINS=${IMAGE_VLLM_PLUGINS},glm53_capture PYTHONPATH=/kld-plugin:${IMAGE_PYTHONPATH} GLM53_CAP_ENABLE=1 GLM53_CAP_REGISTRY=/kld-registry GLM53_CAP_OUT=/kld-out/staging"

# --- patched copy of start.sh -------------------------------------------------
PATCHED="$(mktemp --suffix=.sh "${TMPDIR_HERE}/.start-capture.XXXXXX")" || die "mktemp failed"
trap 'rm -f "${PATCHED}"' EXIT
ANCHOR='  --volume "${CACHE_DIR}:/root/.cache" \'
SDLINE='SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"'
grep -qxF -- "${ANCHOR}" "${STACK}/start.sh" || die "cache-mount anchor not found in start.sh"
grep -qxF -- "${SDLINE}" "${STACK}/start.sh" || die "SCRIPT_DIR line not found in start.sh"
awk -v stack="${STACK}" -v plugin="${PLUGIN_DIR}" -v reg="${REGISTRY_DIR}" -v out="${OUT_DIR}" \
    -v modfile="${MODFILE}" -v modtarget="${MODTARGET}" -v swapdir="${SWAPDIR}" \
    -v anchor="${ANCHOR}" -v sdline="${SDLINE}" '
  $0 == sdline { printf "SCRIPT_DIR=\"%s\"\n", stack; next }
  { print }
  $0 == anchor {
    printf "  --volume \"%s:/kld-plugin:ro\" \\\n", plugin
    printf "  --volume \"%s:/kld-registry:ro\" \\\n", reg
    printf "  --volume \"%s:/kld-out\" \\\n", out
    printf "  --volume \"%s:%s:ro\" \\\n", modfile, modtarget
    printf "  --volume \"%s:/swap:ro\" \\\n", swapdir
  }' "${STACK}/start.sh" > "${PATCHED}" || die "awk failed"
chmod +x "${PATCHED}"
# exactly one changed line and five added lines, nothing else
nd="$(diff "${STACK}/start.sh" "${PATCHED}" | grep -c '^[<>]')"
[[ "${nd}" == 7 ]] || { diff "${STACK}/start.sh" "${PATCHED}"; die "unexpected patch size (${nd} diff lines)"; }

echo "=== v0.9.2-experimental swap capture launch, ARM=${ARM} SWAP_SET=${SWAP_SET:-} SWAP_LAYERS=${SWAP_LAYERS:-} ==="
echo "module         : ${MODFILE} -> ${MODTARGET} (ro)"
echo "swap file      : ${SWAPDIR} -> /swap (ro)"
echo "image          : ${IMAGE}"
echo "recipe env     : ${RECIPE_ENV}"
echo "stack start.sh : ${STACK}/start.sh (sha256 ${have:0:12}, unmodified; temp copy ${PATCHED})"
echo "plugin         : ${PLUGIN_DIR} -> /kld-plugin (ro)"
echo "registry       : ${REGISTRY_DIR} -> /kld-registry (ro)"
echo "output         : ${OUT_DIR} -> /kld-out (rw); plugin writes /kld-out/staging"
echo "forwarded env  : ${DEBUG_ENV}"
echo "patch          :"
diff "${STACK}/start.sh" "${PATCHED}" | sed 's/^/    /'
echo

if [[ "${DRY_RUN:-0}" == 1 ]]; then
  # Render the exact docker run with a stub `docker`: image inspect goes to the
  # real docker (read-only); container inspect reports "absent"; run is printed.
  STUB="$(mktemp -d "${TMPDIR_HERE}/.stub.XXXXXX")" || die "mktemp failed"
  trap 'rm -f "${PATCHED}"; rm -rf "${STUB}"' EXIT
  REAL_DOCKER="$(command -v docker)"
  cat > "${STUB}/docker" <<EOF
#!/usr/bin/env bash
case "\$1 \$2" in
  "image inspect") exec "${REAL_DOCKER}" "\$@" ;;
esac
case "\$1" in
  inspect) exit 1 ;;
  run) printf 'DOCKER-RUN-ARG\t%s\n' "\$@"; exit 0 ;;
  pull) echo "stub: refusing pull" >&2; exit 1 ;;
  *) echo "stub: unexpected docker \$*" >&2; exit 1 ;;
esac
EOF
  chmod +x "${STUB}/docker"
  PATH="${STUB}:${PATH}" "${PATCHED}"
  rc=$?
  echo "DRY_RUN=1: rendered only (start.sh exit ${rc}); nothing started."
  exit "${rc}"
fi

mkdir -p "${OUT_DIR}/staging" || die "cannot create ${OUT_DIR}/staging"
for s in "${REGISTRY_DIR}"/*/; do mkdir -p "${OUT_DIR}/staging/$(basename "$s")"; done
"${PATCHED}"
rc=$?
[[ "${rc}" == 0 ]] || die "start.sh exited ${rc}"
echo "Started. Ready when 'docker logs glm53-flash-exl3-b12x-vllm' shows"
echo "  'glm53_capture: patched PromptLogprobsWorker.compute_prompt_logprobs' and"
echo "  'GLM release startup warmup complete; container is ready.'"
