# Third-party material and attribution

Code in this repository is Apache-2.0 (`LICENSE`); results and documentation are CC BY 4.0 (`LICENSE-DATA.md`).
The material below keeps its own licence.

## Engines (referenced, not redistributed)

- **CuteAFD** by tpurtell, https://github.com/tpurtell/cuteafd, MIT licence. Evaluated at v3.0.1 (`9098781f`), image
  `ghcr.io/tpurtell/cuteafd-coordinator:v3.0.1@sha256:392db7c0…`. `repro/cuteafd/patches/0001-coordinator-infiniband-guard.patch`
  is a change to its launcher `scripts/launch/run-family.sh`, which is "Copyright (c) 2026 T.J. Purtell" under the MIT
  licence (https://github.com/tpurtell/cuteafd/blob/main/LICENSE). The configs in
  `repro/cuteafd/configs/` follow his 2-RTX v3 release card.
- **tpurtell/glm-5.3-flash-ext3-2x-rtx** (tpurtell's vLLM-based engine), https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx,
  built on vLLM (Apache-2.0). Evaluated at v0.9.2. The capture plugin in `repro/stage0/capture-vllm/` hooks a method of
  that image's vLLM; it contains no vLLM code.

## Reference sets and checkpoints (referenced, not redistributed)

- **cuteafd-fidelity** by tpurtell, Hugging Face dataset `wrldsuksgo2mars/cuteafd-fidelity` @ `a7e7d1b4`, config
  `glm5_flash-v2_20261005_bf16root`, MIT licence. Panel P-B. `repro/stage0/scorers/score_pb.py` ports his scoring rule
  (the CuteAFD source `reference.rs`, Copyright (c) 2026 T.J. Purtell, MIT licence) to Python; it was validated against
  his own CLI with zero difference. `results/2026-10-26-cuteafd-vs-vllm/q/rows/pb-rows.csv` holds the per-position scores
  computed against this panel, with the panel's reference NLL of each next token; released under CC BY 4.0 with this
  attribution.
- **GLM-5.3-Flash BF16 teacher logits** from Brandon M. Music (brandonmusic): 25 windows of 2,048 tokens, full-vocabulary
  logits of `zai-org/GLM-5.3-Flash-BF16` @ `a6c167b6`, publicly available in the Hugging Face dataset
  `brandonmusic/GLM-5.3-Flash-ShapleyMCG-K4-Evidence` @ `32afb8875f830528d5545c20a51846b56c537f44` (no licence stated).
  Panel P-A. They were first scored from `brandonmusic/GLM-5.3-Flash-BF16-Teacher-Logits` @ `95f4fdd9`, no longer
  public; all 25 teacher files, token arrays and the mask are byte-identical in the Evidence repository.
  `results/2026-10-26-cuteafd-vs-vllm/q/rows/pa-rows.csv` holds per-position scores computed against it (no logits, no
  token ids): our KL, NLL and top-1 columns under CC BY 4.0; `teacher_nll` and `teacher_confident` are derived from
  his teacher logits and credited to him. Provenance and hashes: `results/2026-10-26-cuteafd-vs-vllm/q/pa/PROVENANCE.json`.
- **Checkpoints**: `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-v1`, `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-Core-FP8`
  (tpurtell), `incoai/GLM-5.3-Flash-DFlash2`, `zai-org/GLM-5.3-Flash`. Their licences are on their model cards.
- Hugh Madden's `klgate.py` was used as an independent cross-check of the P-A scorer; it is not included.

## Prompt sources

Revisions and file hashes: `protocol/SOURCES.json`. Selection rules and seeds: `repro/stage0/prompts/RULES.json`.

| Source | Licence | Used for | In this repository |
|---|---|---|---|
| LongBench-Write (THUDM/LongWriter, `evaluation/longbench_write_en.jsonl` @ `447539b3`) | Apache-2.0 | Block L and T prose tasks | the 4 Block L prose prompts, verbatim, in `repro/stage0/prompts/L/prose/`; Block T items rebuilt by the build script |
| MATH-500 (HuggingFaceH4/MATH-500 @ `6e4ed1a2`), derived from MATH (Hendrycks et al.) | MIT (MATH) | Block L and T reasoning tasks, with their reference answers | the 4 Block L reasoning prompts, verbatim, in `repro/stage0/prompts/L/reasoning/` |
| PG-19 (DeepMind, test split @ `4d28bd77`) | Apache-2.0 (dataset); the books are in the public domain | Q2 prose windows, Block T prose and reasoning contexts | not included; rebuilt from the source by the build script |
| HumanEval+ and MBPP+ (evalplus) | Apache-2.0 | Block T code tasks | not included; rebuilt |
| vLLM source files from the v0.9.2 image (`SPDX-License-Identifier: Apache-2.0` files only) | Apache-2.0 | Q2 code windows, Block T code and JSON contexts | not included; rebuilt (each file keeps its own licence header) |

Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0. MIT licence of MATH:
https://github.com/hendrycks/math/blob/main/LICENSE.

The authored material (the JSON task, the four multi-file code specifications with their hidden tests and reference
implementations, the prompt wrappers) was written for this evaluation and is under CC BY 4.0 (text) and Apache-2.0 (code).
