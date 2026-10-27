#!/usr/bin/env bash
# Start the served vLLM v0.9.2 configuration with the glm53_capture plugin armed.
#
# The served configuration stays as the recipe has it: DFlash2 K3 speculation,
# prefix caching (+ mamba align), max-num-seqs 16, cudagraph ceiling 64, FP8 MLA
# KV, 0.95 memory, container glm53-flash-exl3-b12x-vllm, 127.0.0.1:8001.
#
# What differs from the normal start (source recipe env.sh; ./local-start.sh):
#   mounts  <plugin dir>   -> /kld-plugin   (ro)
#           <registry dir> -> /kld-registry (ro)
#           <OUT_DIR>      -> /kld-out      (rw)
#   env     VLLM_PLUGINS   image default + ",glm53_capture"
#           PYTHONPATH     "/kld-plugin:" + image default (/opt/b12x:/usr/local/lib/python3.12/dist-packages)
#           GLM53_CAP_ENABLE=1 GLM53_CAP_REGISTRY=/kld-registry GLM53_CAP_OUT=/kld-out/staging
# Nothing else.  The stack's start.sh is not modified: a temporary copy gets the
# three mount lines after its cache mount and its SCRIPT_DIR pointed back at
# the stack; env goes through start.sh's own DEBUG_ENV hook.
#
# IMAGE is exported explicitly.  The stack's local-env.sh defaults IMAGE to
# the v0.9.0 digest (f36dfb87); without the export a run would silently measure
# v0.9.0.  The script refuses to start unless IMAGE is the v0.9.2 digest after
# every file has been sourced.
#
# Usage:
#   OUT_DIR=<run>/vllm-v092-dumps ./start-v092-capture.sh
#   DRY_RUN=1 ./start-v092-capture.sh   # render the full docker run with a stub; start nothing
#
# The normal server must be stopped first (start.sh refuses if the container runs):
#   <vllm-stack>/stop.sh
set -uo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STACK=<vllm-stack>
RECIPE_ENV="<recipes>/glm53-flash-exl3-k3.25@tpurtell+v0.9.2/env.sh"
PIN_IMAGE=sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2
PIN_START_SH=e1196cbcd6b4744cb41fdebf3d12d8586dbea464e702af5de47617837efe0e5e
PLUGIN_DIR="${HERE}/plugin"
REGISTRY_DIR="${REGISTRY_DIR:-${HERE}/registry}"
OUT_DIR="${OUT_DIR:-<run>/vllm-v092-dumps}"
IMAGE_PYTHONPATH=/opt/b12x:/usr/local/lib/python3.12/dist-packages
IMAGE_VLLM_PLUGINS=lora_filesystem_resolver,lora_hf_hub_resolver

die() { echo "start-v092-capture: $*" >&2; exit 1; }

# Overrides that would change the served engine are refused, not passed through.
# (IMAGE, MODEL_PROFILE and GPU_MEMORY_UTILIZATION are set unconditionally by
# the recipe env below and checked afterwards, so a shell that sourced it is fine.)
for v in SPECULATIVE_METHOD DFLASH_TOKENS ENABLE_PREFIX_CACHING MAX_NUM_SEQS \
         MAX_NUM_BATCHED_TOKENS MAX_CUDAGRAPH_CAPTURE_SIZE KV_CACHE_PROFILE KV_CACHE_DTYPE \
         MAX_MODEL_LEN MODEL_ID MODEL_REVISION MODEL_DIR_OVERRIDE \
         CONTAINER_NAME PORT DEBUG_ENV EXTRA_SERVE_ARGS; do
  [[ -v "$v" ]] && die "$v is set in the calling environment; unset it (the recipe decides it)"
done

for p in "${STACK}/start.sh" "${STACK}/local-env.sh" "${RECIPE_ENV}" \
         "${PLUGIN_DIR}/glm53_capture_plugin/__init__.py" \
         "${PLUGIN_DIR}/glm53_capture-0.2.dist-info/entry_points.txt" "${REGISTRY_DIR}"; do
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
# shellcheck disable=SC1091
source "${STACK}/local-env.sh" || die "cannot source local-env.sh"
[[ "${IMAGE}" == "${PIN_IMAGE}" ]] || die "IMAGE changed to ${IMAGE} after local-env.sh"
[[ "${PORT}" == "127.0.0.1:8001" ]] || die "PORT=${PORT}, expected 127.0.0.1:8001"
[[ "${MODEL_PROFILE}" == k325 && "${GPU_MEMORY_UTILIZATION}" == 0.95 ]] \
  || die "recipe env gave MODEL_PROFILE=${MODEL_PROFILE} GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION}"
docker image inspect "${IMAGE}" >/dev/null 2>&1 || die "image ${IMAGE} not present locally (no pull from here)"

export DEBUG_ENV="VLLM_PLUGINS=${IMAGE_VLLM_PLUGINS},glm53_capture PYTHONPATH=/kld-plugin:${IMAGE_PYTHONPATH} GLM53_CAP_ENABLE=1 GLM53_CAP_REGISTRY=/kld-registry GLM53_CAP_OUT=/kld-out/staging"

# --- patched copy of start.sh -------------------------------------------------
PATCHED="$(mktemp --suffix=.sh "${HERE}/.start-capture.XXXXXX")" || die "mktemp failed"
trap 'rm -f "${PATCHED}"' EXIT
ANCHOR='  --volume "${CACHE_DIR}:/root/.cache" \'
SDLINE='SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"'
grep -qxF -- "${ANCHOR}" "${STACK}/start.sh" || die "cache-mount anchor not found in start.sh"
grep -qxF -- "${SDLINE}" "${STACK}/start.sh" || die "SCRIPT_DIR line not found in start.sh"
awk -v stack="${STACK}" -v plugin="${PLUGIN_DIR}" -v reg="${REGISTRY_DIR}" -v out="${OUT_DIR}" \
    -v anchor="${ANCHOR}" -v sdline="${SDLINE}" '
  $0 == sdline { printf "SCRIPT_DIR=\"%s\"\n", stack; next }
  { print }
  $0 == anchor {
    printf "  --volume \"%s:/kld-plugin:ro\" \\\n", plugin
    printf "  --volume \"%s:/kld-registry:ro\" \\\n", reg
    printf "  --volume \"%s:/kld-out\" \\\n", out
  }' "${STACK}/start.sh" > "${PATCHED}" || die "awk failed"
chmod +x "${PATCHED}"
# exactly one changed line and three added lines, nothing else
nd="$(diff "${STACK}/start.sh" "${PATCHED}" | grep -c '^[<>]')"
[[ "${nd}" == 5 ]] || { diff "${STACK}/start.sh" "${PATCHED}"; die "unexpected patch size (${nd} diff lines)"; }

echo "=== v0.9.2 capture launch ==="
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
  STUB="$(mktemp -d "${HERE}/.stub.XXXXXX")" || die "mktemp failed"
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
