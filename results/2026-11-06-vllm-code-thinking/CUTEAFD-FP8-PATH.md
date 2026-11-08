# What changes with the core's format on CuteAFD v4.0.0 (source reading, no GPU; 2026-11-06)

Read in the tagged v4.0.0 source and in the server logs of the core-swap run (same daemon logic as the code study).
Paths are relative to the cuteafd repository. "Read" = seen in code or logs; "inferred" = not visible in this checkout.

Design context (added 2026-11-08): these settings are the launcher's defaults, with its stated reasons in the comment above
the GLM 5.3 Flash precision block (`scripts/launch/run-family.sh:2337-2351`): row128 KDA and an FP8 head on both layouts,
token-row KDA output ownership on the two-GPU head split because it avoids rounding half-K BF16 partials. The model
notes (`docs/models/glm5_flash.md:163-210`, "Default precision") give the speed trade and its teacher-forced checks (top-1,
KL); they and the `--kda-fp8` option text (`.../glm5_flash/mod.rs:189-197`, which also records the verify-vs-decode
rounding cost under speculation) describe BF16 KDA as the default on the two-GPU split. The documents differ; the
launcher's choice is what runs. This note maps what each setting changes.

## Server logs (read)
| Launch | KDA projections | Vocabulary head | Prefill FP8 activations |
|---|---|---|---|
| K4-Core-K6, native 6-bit core (C-K6) | `kda_fp8=Off` (native 6-bit) | `head="K6"`, `fp8_head=false` | `fp8_prefill=[Mla, Ffn]` (no FP8 MLA/FFN operands to apply it to) |
| K4-Core-K6, BF16 core (C-K6x) | `kda_fp8=Row128`, 2,844 MiB | `head="FP8"`, `fp8_head=true` | `fp8_prefill=[Mla, Ffn]` |
| K4 (C-K4) | `kda_fp8=Row128`, 2,844 MiB | `head="FP8"`, `fp8_head=true` | `fp8_prefill=[Mla, Ffn]` |
Source: `results/2026-11-03-cuteafd-core-swap` server logs, s1 launches (not published; lines 75-80 of each).
The two serving configs differ only in MODEL_ID and MODEL_REVISION.

## Code (read)
- MLA (`q_a|kv_a`, `q_b`, `o_proj`), dense and shared-expert projections are FP8 only: the checkpoint's E4M3 blocks, or
  128x128 blocks quantized from BF16 at load; BF16 is never resident (`rust/crates/cuteafd-daemon/src/families/glm5_flash/weights.rs:3-10`).
- KDA in/out projections and the LM head take FP8 (E4M3, per row x 128-K scales) when selected
  (`weights.rs:3-10`). The launcher's `auto` selects both: `GLM5_FLASH_KDA_FP8` auto -> row128
  (`scripts/launch/run-family.sh:2355-2363`), `GLM5_FLASH_FP8_HEAD` auto -> on (`run-family.sh:2409-2417`).
- With a native 6-bit core the daemon turns KDA FP8 off and, with a native `lm_head`, the FP8 head off
  (`rust/crates/cuteafd-daemon/src/families/glm5_flash/mod.rs:1716-1723`). So the BF16-core checkpoint gets FP8 KDA and an
  FP8 head; the 6-bit checkpoint does not.
- The KDA FP8 input operand packs q, k, v and the f_a, g_a and b projections; f_a/g_a/b are BF16 in both checkpoints and stay
  BF16 on the 6-bit path (`weights.rs:731-746`, native: separate BF16 `w_aux`; loader
  `rust/crates/cuteafd-loader/src/families/glm5_flash/resident.rs:94-104`, converted: one input operand, 1 byte per value with FP8).
- The option's own documentation: row128 "costs 3.4 points top-1 (89.1% -> 85.7%) and doubles verify-vs-decode rounding
  ... enough to flip greedy output under speculation; opt-in", CLI default off (`mod.rs:189-198`).
- Scale rule for FP8 copies made at load: default pow2 (smallest power of two >= amax/448) (`mod.rs:284-294`).
- Prefill: MLA and FFN run W8A8 (dynamic FP8 activations) by default (`GLM5_FLASH_FP8_PREFILL`, `run-family.sh:2446-2465`);
  on the 6-bit path these operands are 6-bit trellis kernels (FP16 weights, FP32 accumulate) with no activation quantization.

- Added 2026-11-07: on a two-GPU head split the launcher's `auto` also adds token-row KDA output ownership
  (`--kda-output-shard --kda-prefill-expanded`) unless KDA FP8 is off (`run-family.sh:2366`); the daemon accepts these
  only with `--kda-fp8 row128` or `channel` (`mod.rs:1296-1299`) and clears them for a native 6-bit core (`mod.rs:1716-1722`).
  So `GLM5_FLASH_KDA_FP8=off` on two GPUs also returns KDA to the partials split path.

## Unchanged between the two (read)
KV records (FP8 MLA latents), KDA state (F32), index cache, drafter weights and draft mode, prefill rows, sampling code.
The drafter reads the target head, so the drafter's head is FP8 on the BF16-core arm and 6-bit on the other.

## Switches that exist on v4 (read)
`GLM5_FLASH_KDA_FP8=off` (BF16 KDA), `GLM5_FLASH_FP8_HEAD=off` (BF16 head), `GLM5_FLASH_FP8_PREFILL=off`, `FP8_SCALES`.
MLA and dense/shared MLP have no BF16 option.

## Reading
The "BF16 core" arm on CuteAFD differs from the 6-bit arm in more than the core's weights: KDA projections (34 layers,
including three projections outside the core), the vocabulary head and prefill activations are FP8 on it. K4 is served the
same way. Which of these goes with the shorter code reasoning is not separated (inferred candidates, no measurement).
