#!/usr/bin/env bash
# Build the MODEL_DIR_OVERRIDE directory for K4-Core-K6 on "vLLM fork v0.9.2-experimental".
#
# Why: the v0.9.0 launcher (start.sh:295) insists on quantization_config.json, and this checkpoint ships
# quantize_config.json only. The launcher stays unmodified; instead MODEL_DIR_OVERRIDE mounts this
# self-contained directory at /model. It holds HARDLINKS to the HF snapshot's blobs (same <data> filesystem,
# zero extra bytes; symlinks would dangle inside the container), plus quantization_config.json as a second
# hardlink to the quantize_config.json blob (identical bytes: Exl3Config refuses if the two files differ).
#
# The hardlinks keep the blobs alive even if the HF cache is pruned; delete this directory to release them.
# Idempotent: re-running verifies the existing links and changes nothing.
#   ./local-make-overlay.sh            (no sudo; touches only <hf-home>/derived/)
umask 022
REV=5d3fffe1df9c4a109bbbdafb60dc19df9fac019d
SNAP=<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K4-Core-K6/snapshots/${REV}
OUT=<hf-home>/derived/GLM-5.3-Flash-EXL3-K4-Core-K6@5d3fffe1-vllm-overlay

if [[ ! -f "${SNAP}/quantize_config.json" || ! -f "${SNAP}/model.safetensors.index.json" ]]; then
  echo "snapshot incomplete: ${SNAP}" >&2; exit 1
fi
mkdir -p "${OUT}" || exit 1
fail=0
link() {  # link <blob> <name>
  local src="$1" dst="${OUT}/$2"
  if [[ -e "${dst}" ]]; then
    [[ "$(stat -c %i "${dst}")" == "$(stat -c %i "${src}")" ]] || { echo "differs: ${dst}" >&2; fail=1; }
  else
    ln "${src}" "${dst}" || fail=1
  fi
}
n=0
for f in "${SNAP}"/*; do
  [[ -f "${f}" ]] || continue            # quantization-errors/ (evidence only) is not needed for serving
  link "$(readlink -f "${f}")" "$(basename "${f}")"; n=$((n+1))
done
link "$(readlink -f "${SNAP}/quantize_config.json")" quantization_config.json
cat > "${OUT}/LOCAL-OVERLAY.txt" <<EOF
Hardlink overlay of wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6@${REV} for MODEL_DIR_OVERRIDE
(vLLM fork v0.9.2-experimental, local loader patch local-exl3-core-dequant). quantization_config.json is a
second link to the quantize_config.json blob. Made by <vllm-x-stack>/local-make-overlay.sh.
EOF
if (( fail )); then echo "overlay NOT consistent: ${OUT}" >&2; exit 1; fi
echo "overlay ok: ${OUT} (${n} snapshot files + quantization_config.json, hardlinks)"
