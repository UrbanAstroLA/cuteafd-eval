#!/usr/bin/env python3
"""local loader patch (local-exl3-core-dequant) for tpurtell's vLLM fork v0.9.2.
Engine variant name: "vLLM fork v0.9.2-experimental" -- a local patch, not tpurtell's release.

Copies exl3_core_dequant.py into the vLLM package and edits three files with anchors that must each
match exactly once (a moved anchor fails the image build instead of patching the wrong place):

  model_executor/layers/quantization/exl3.py
    - Exl3Config.__init__: add dequant_storage = {}
    - maybe_update_config: before _configure_standard_fused_moe, move the non-expert EXL3 records
      into dequant_storage (switch on only), so the fused-MoE detection sees experts only, exactly
      as for the K4 checkpoint
    - _storage_entry: optional lookup table (default tensor_storage; stock calls unchanged)
  models/glm5next/nvidia/model.py   Glm5NextForCausalLM.load_weights: wrap the weight iterator
  models/glm5next/nvidia/mtp.py     Glm5NextMTP.load_weights: wrap the weight iterator (native MTP)

With LOCAL_EXL3_DEQUANT_NONEXPERT unset every edited line is a no-op (stock behaviour).
Usage: local-port-exl3-core-dequant.py <vllm package dir> <exl3_core_dequant.py>
"""
import pathlib
import shutil
import sys

MARK = "local-exl3-core-dequant"
root = pathlib.Path(sys.argv[1])
module_src = pathlib.Path(sys.argv[2])


def patch(rel, edits):
    path = root / rel
    text = path.read_text()
    if MARK in text:
        raise SystemExit(f"{path}: already patched")
    for old, new in edits:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{path}: anchor found {count} times, expected 1:\n{old}")
        text = text.replace(old, new)
    path.write_text(text)
    print("patched", path)


shutil.copyfile(module_src, root / "model_executor/layers/quantization/exl3_core_dequant.py")
print("installed", root / "model_executor/layers/quantization/exl3_core_dequant.py")

patch("model_executor/layers/quantization/exl3.py", [
    (
        "        self.standard_fused_moe = False\n\n    def get_name(self) -> str:\n",
        "        self.standard_fused_moe = False\n"
        "        # local-exl3-core-dequant: non-expert EXL3 records rebuilt to BF16 at load (local patch)\n"
        "        self.dequant_storage: dict[str, Any] = {}\n"
        "\n    def get_name(self) -> str:\n",
    ),
    (
        "        self._configure_standard_fused_moe(hf_config)\n"
        "        self._configure_base_quantization(hf_config)\n"
        "        self._validate_storage_metadata()\n",
        "        # local-exl3-core-dequant: no-op unless LOCAL_EXL3_DEQUANT_NONEXPERT=bf16\n"
        "        from .exl3_core_dequant import split_nonexpert_storage\n"
        "        split_nonexpert_storage(self)\n"
        "        self._configure_standard_fused_moe(hf_config)\n"
        "        self._configure_base_quantization(hf_config)\n"
        "        self._validate_storage_metadata()\n",
    ),
    (
        "    def _storage_entry(self, prefix: str) -> dict[str, Any] | None:\n",
        "    def _storage_entry(\n"
        "        self, prefix: str, storage: dict[str, Any] | None = None  # local-exl3-core-dequant\n"
        "    ) -> dict[str, Any] | None:\n",
    ),
    (
        "            entry = self.tensor_storage.get(candidate)\n",
        "            entry = (self.tensor_storage if storage is None else storage).get(candidate)\n",
    ),
])

WRAP = (
    "        from vllm.model_executor.layers.quantization import exl3_core_dequant  # local-exl3-core-dequant\n"
    "        if exl3_core_dequant.mode():  # local patch; unset = stock iterator\n"
    "            weights = exl3_core_dequant.dequant_weights(\n"
    "                weights, self.quant_config, self.config, spec={spec})\n"
)

patch("models/glm5next/nvidia/model.py", [
    (
        "    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:\n"
        "        loader = AutoWeightsLoader(\n"
        "            self,\n"
        "            skip_prefixes=([\"lm_head.\"] if self.config.tie_word_embeddings else None),\n"
        "        )\n",
        "    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:\n"
        + WRAP.format(spec="False") +
        "        loader = AutoWeightsLoader(\n"
        "            self,\n"
        "            skip_prefixes=([\"lm_head.\"] if self.config.tie_word_embeddings else None),\n"
        "        )\n",
    ),
])

patch("models/glm5next/nvidia/mtp.py", [
    (
        "    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:\n"
        "        stacked_params_mapping = [\n"
        "            (\"gate_up_proj\", \"gate_proj\", 0),\n",
        "    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:\n"
        + WRAP.format(spec="True") +
        "        stacked_params_mapping = [\n"
        "            (\"gate_up_proj\", \"gate_proj\", 0),\n",
    ),
])
