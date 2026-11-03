# "vLLM fork v0.9.2-experimental": tpurtell's v0.9.2 release image + local loader patch
# local-exl3-core-dequant (env-gated; unset LOCAL_EXL3_DEQUANT_NONEXPERT = stock behaviour). Not tpurtell's release.
# Rebuilds the non-expert EXL3 matrices of K4-Core-K6 to BF16 at load; experts stay on b12x. See exl3_core_dequant.py.
# Build (CPU only, nothing pulled; the base must already be on disk):
#   cd <vllm-x-stack> && \
#   nice docker build --pull=false --network none -f local-k6dequant.Dockerfile -t local/glm53-flash:v0.9.2-experimental .
FROM ghcr.io/tpurtell/glm-5.3-flash-exl3-4bpw-2x-rtx@sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2
COPY local-port-exl3-core-dequant.py exl3_core_dequant.py <tmp>/local/
RUN python3 <tmp>/local/local-port-exl3-core-dequant.py /usr/local/lib/python3.12/dist-packages/vllm <tmp>/local/exl3_core_dequant.py \
 && cd /usr/local/lib/python3.12/dist-packages/vllm \
 && grep -q "local-exl3-core-dequant" model_executor/layers/quantization/exl3.py \
 && grep -q "local-exl3-core-dequant" models/glm5next/nvidia/model.py \
 && grep -q "local-exl3-core-dequant" models/glm5next/nvidia/mtp.py \
 && python3 -m py_compile model_executor/layers/quantization/exl3.py model_executor/layers/quantization/exl3_core_dequant.py \
      models/glm5next/nvidia/model.py models/glm5next/nvidia/mtp.py \
 && rm -rf <tmp>/local
LABEL io.local.patch="local-exl3-core-dequant: env-gated BF16 rebuild of non-expert EXL3 matrices at load (local patch, not tpurtell's release)" \
      io.local.variant="vLLM fork v0.9.2-experimental" \
      io.local.switch="LOCAL_EXL3_DEQUANT_NONEXPERT=bf16 (unset = stock)" \
      io.local.base="ghcr.io/tpurtell/glm-5.3-flash-exl3-4bpw-2x-rtx@sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2"
