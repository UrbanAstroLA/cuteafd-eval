# CuteAFD v3.0.1: counterparts of the vLLM-engine issues D1-D7 and E1 found during evaluation

Read-only source audit, 2026-10-26. No GPU, no container, nothing run in the image.

**Sources read**
- CuteAFD at tag v3.0.1, commit `9098781f`, in `<cuteafd>`. Paths below without a prefix are relative to it.
- The `third_party/sparkinfer` submodule is pinned at `d3c13652e7dec7b046fe22de59f7340844822cc7` (`third_party/sparkinfer.lock.json`). Its files were read one at a time with `gh api repos/tpurtell/sparkinfer-glmrt/contents/<path>?ref=d3c13652`. Paths prefixed `si:` are in that repository at that commit.
- The local K3.25 checkpoint `wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-v1@0490d2f7`: `config.json` and the safetensors headers only.
- The local `incoai/GLM-5.3-Flash-DFlash2` `config.json`.

**What each issue is.** The definitions come from:
- `https://github.com/UrbanAstroLA/local-inference-evals/blob/main/investigations/2026-10-glm53-completion/README.md`: the matrix of items, the kpool tail ring, stage A, D7 and "Observations recorded separately".
- `<runs>/investigations/2026-10-glm53-completion/upstream-drafts/v2/`: `tpurtell/0{1..5}-*/COMMIT.md` and `vllm/ISSUE.md`.

## Which code paths serve 2 RTX, local experts, no Sparks

The answer depends on the attention placement, so it is settled first.

| Placement | How it is selected | DSA index cache served | Evidence |
|---|---|---|---|
| `context` (token-split MLA) | **auto on two GPUs**; fails closed if the image lacks its programs | compact (per-sequence open-pool tails) | `rust/crates/cuteafd-loader/src/placement/families/glm5_flash.rs:57-75` ("Auto is `context` on two GPUs"); `rust/crates/cuteafd-daemon/src/families/glm5_flash/mod.rs:1383-1390` (`Context => Compact`) |
| `heads` (head split) | explicit `ATTENTION_PLACEMENT=heads` | keys (per-token key, gate row) | same `mod.rs:1388` (`Heads if split => Keys`); `python/tools/aot/export_b12x_dsv4_aot.py:441` ("The head split keeps the per-token index keys") |
| `layers` | explicit only | whatever was requested; the launcher passes keys on a split | `mod.rs:1389`; `scripts/launch/run-family.sh:2018-2030` |

- The v3 2-RTX release card is `benchmarks/glm5_flash/2026-10-18-…-2rtx-glm53f-exl3-max/report.json`. It reads "2 RTX (head split) · experts on the coordinator".
- Both index-cache variants were audited below. The `layers` placement uses the same programs as `heads` and was not audited separately.

## Summary

| Issue (vLLM engine) | CuteAFD verdict | Key citation |
|---|---|---|
| **D1**: keeps 511 of 512 selected pools (drops column 511) | **handled correctly**: all 512 selected pools are expanded, plus the open tail pool, into a 2,112-slot row | `si:b12x/integration/cuteafd/_glmf_kernels.py:1058-1077` (`if j < Int64(self.pools)` … `lengths[row] = Int32(filled + tail)`); `engine.rs:89-90` (`SPARSE_TOPK = 2112`, "2048 + 3") |
| **D2**: tail ring written without positions (null block, foreign blocks) | **not applicable (different design)**: there is no tail-ring view or generic mapping fallback; every slot comes from the row's own position | `engine.rs:653-665` (`record`, `pool_slot` from `position`), `engine.rs:3226-3240` (`rows()` per position); compact tails take `positions`/`seq_first`/`kda_slots` (`engine.rs:4615-4622`) |
| **D3**: router logits computed in bf16 on SM12x | **handled correctly**: BF16 operands, FP32 accumulation and an FP32 store on both GEMM routes; the bias is added and selection runs in FP32 | `si:…/glmf.py:1249` (`RoutedBf16Projection(e, h, out_dtype=cutlass.Float32)`); `si:b12x/gemm/bf16_gemv/_skinny.py:201`, `si:…/_prefill.py:408`; `native/shared/cuda/expert_router.cu:80,85,103` |
| **D4**: routed SwiGLU limit not passed | **handled correctly** for local EXL3 routed experts: compiled at 10, and the runtime refuses a package without it. Shared and dense MLPs are also clamped at 10 | `python/tools/aot/package_exl3_aot.py:238-242`; `python/tools/aot/export_b12x_exl3_aot.py:214`; `rust/crates/cuteafd-daemon/src/shared/experts/exl3/execution.rs:551`; `si:…/glmf.py:1133` |
| **D5**: workspace not locked after graph capture | **not applicable (different design)**: step workspaces are fixed-capacity, allocated before capture, and never replaced. No resize path was found (not exhaustive, see detail) | `engine.rs:1834` ("Allocate fixed workspaces before measuring the graph executables"), `engine.rs:3085-3091`, `engine.rs:3062-3063` |
| **D6**: stale warm-up tail block ids | **not applicable (different design)**: tables are rebuilt from the placement every step; padding and warm-up rows carry -1 slots; a KDA/tail slot is zeroed before a sequence's first step | `rust/crates/cuteafd-daemon/src/shared/decode_graph.rs:63-65`; `engine.rs:3582-3592`; `engine.rs:2758-2760`, `2860-2868` |
| **D7**: index-K prefill writer assumes pool-aligned chunk starts | **handled correctly** in both index caches. Keys: a pool reads the sequence's own persistent token keys by record slot. Compact: members before the step are read from the sequence's tail | `si:…/_glmf_kernels.py:966` (keys); `si:…/_glmf_kernels.py:1375-1390` (`before = at < first` → tail) |
| **E1**: router weights vary with batch size (fp32 `(s+b)−b` rebuild above 1,024 rows) | **not applicable (different design)** for that mechanism. **Cannot determine** whether router *logits* are bitwise identical across the GEMV/GEMM switch at 160/161 rows | `native/shared/cuda/expert_router.cu:103` (weight read from the unbiased score); `si:…/_skinny.py:232,456` (switch at 160 rows) |

`swiglu_limit` in short:
- Routed EXL3 experts, the shared expert and the dense MLPs all clamp at 10.
- **None of them read the value from `config.json`.** Each value is a constant: the expert-shape constant, the export default, or the AOT geometry.
- `config.json`'s value is parsed and shown in plan notes, but no consumer or equality check was found in the GLM Flash engine.
- The DFlash2 drafter has no experts. Its dense MLP is unclamped, which matches its config: that config has no `swiglu_limit`.
- Details are in the `swiglu_limit` section at the end.

---

## D1: column-511 selection

**The vLLM-engine issue.**
- The indexer selects 512 pools, then keeps output columns 0-510 so that the newest 1-3 tokens fit into 2,048 slots.
- No top-k route sorts its output, so the dropped pool was arbitrary: rank better than 480 in 88.1% of live tiled decode rows.
- Prefill rows with exactly 512 candidates dropped the newest pool.

**CuteAFD counterpart.**
- `engine.rs:24-26`: "The indexer selects every earlier token up to 2051 tokens; past that the top 512 pools (glmf_index_topk) expand to tokens plus the open tail pool."
- Selection width: `engine.rs:89-90` defines `SPARSE_TOPK: usize = 2112`, documented as "2048 + 3, padded to 64". The geometry is `si:…/_common.py:359-361`: `sparse_topk = ceil((index_topk + index_kpool - 1) / 64) * 64`.
- Heads placement, and prefill under every placement: `engine.rs:4689-4704` runs `index_topk_{mode}_{cap}` into `pools`, then `index_expand`.
- `si:…/_glmf_kernels.py:1003-1077` (`GlmfIndexExpand`):
  - rows with `count <= dense_limit` (2,051) select every earlier token (`:1047`);
  - longer rows loop `j < self.pools` (512) and expand each pool to its four record slots (`:1058-1068`);
  - then the open tail pool `count - tail_start` (0-3 tokens) is appended after `filled = pools * kpool` (`:1070-1075`);
  - `lengths = filled + tail` (`:1077`).
  - No column is discarded, so output order cannot matter.
- Context decode (the 2-GPU default): `engine/context.rs:15-19` describes "merge into the global top-512 by (score desc, logical asc)".
  - `si:…/context_split.py:236-280` (`_CandidateMerge`): "A + reverse(B) is bitonic … Its first compare-exchange retains exactly the global best K pairs" (`:237-238`), with K = 512.
  - Each GPU then expands its share in `si:…/_glmf_kernels.py:1080-1172` (`GlmfIndexExpandOwned`): `picked = local_lengths * 4` plus the tail on its owner (`:1155-1172`). "Shard unions equal the full selection."
- The exactly-512-pools case: 512 complete pools means 2,048-2,051 tokens, which is at or below `dense_limit` = 2,051. Those rows take the dense branch and select every token.

**Verdict: handled correctly.** The 512-pool selection is kept whole on every path read. The tail tokens have their own columns.

**Not audited.** Whether the b12x top-k kernel's selected *set* is exact: the GLM index top-k is `dsv4_indexer._TopK`, called from `si:…/glm_indexer.py`. That is outside D1. The vLLM investigation measured the set exact apart from ties on its own b12x kernels, and this audit did not compare CuteAFD's kernel revision with those.

## D2: kpool tail ring without positions

**The vLLM-engine issue.**
- `prepare_attn` built attention metadata without `positions`.
- The tail-ring group then fell back to the generic mapping: column `pos // 8` of the tail block table, which is normally the null block, sometimes a stale block id.
- 98% of tail writes went to the null block, and some went into live attention blocks.

**CuteAFD counterpart.** CuteAFD has no tail ring and no per-group block-table mapping.
- **Keys cache** (heads):
  - Every token's key and gate row is stored at the row's own MLA record slot (`si:…/_glmf_kernels.py:911-918`, "stored … at `token_keys[slots[row]]` (negative slots skip)").
  - Pools read it back by record slot (`:966`).
- **Compact cache** (context, one GPU):
  - The open pool's at most three rows live in a per-sequence tail inside the sequence's KDA slot region (`engine.rs:20-23`; `TAIL_BYTES` at `engine.rs:176-179`).
  - The producer receives `positions`, `kda_slots` and `seq_first` explicitly (`engine.rs:4615-4622`; kernel `si:…/_glmf_kernels.py:1293-1476`).
- **Slot addressing** is computed on the host from the row's position and its own sequence's pages:
  - `engine.rs:653-656`: `record(position)` = `pages[position / 64] * 64 + position % 64`.
  - `engine.rs:659-665`: `pool_slot(position)` is -1 unless `position % 4 == 3`.
  - `engine.rs:3226-3240`: `rows()` pushes `positions`, `kv_slots`, `pool_slots`, `kda_slots`, `seq_first` and `cache_lengths = (position + 1) / 4` per row.
  - A position outside the sequence's pages is an error (`.context("position past the sequence's pages")`), not a fallback.

**Verdict: not applicable (different design).** The function the vLLM tail ring serves is carried out by position-addressed, per-sequence storage.
- In speculative steps, the compact tails stay unchanged during verify.
- `GlmfIndexTailCommit` (`si:…/_glmf_kernels.py:1479-1545`) rebuilds them from the kept rows.

## D3: router logits in bf16 on SM12x

**The vLLM-engine issue.**
- The GLM-5.3-Flash checkpoint asks for fp32 routing: `moe_router_dtype: "float32"` in the local K3.25 `config.json`.
- vLLM's gate ran bf16 `F.linear` and then cast. The corrected form is `torch.mm(out_dtype=fp32)`: BF16 operands with FP32 output.

**CuteAFD counterpart.**
- Call site: `engine.rs:4779-4787` (`moe_front`), and `engine.rs:2484-2492` for the second rank under a split.
  - `router_scores` writes `router_logits`, which is `experts * 4` bytes per row (FP32).
  - `router_select(…, routed_scale, true /* sigmoid */, …)` follows.
- Program: `si:…/glmf.py:1246-1270`.
  - `_RouterScores` uses `RoutedBf16Projection(e, h, out_dtype=cutlass.Float32)` (`:1249`).
  - Its doc: "FP32 router logits `x @ gate^T` (BF16 operands, FP32 accumulation)" (`:1260`).
- Both routes keep FP32 to the store:
  - Skinny GEMV, up to 160 rows for N = 288: `si:b12x/gemm/bf16_gemv/_skinny.py:191-203`. The FP32 `total` is converted to `out_dtype` (Float32) and stored (`:201`).
  - TMA tensor-core GEMM above 160 rows: `si:…/_prefill.py:213-214` accepts a Float32 output, and `:408` stores `acc[index].to(output.element_type)` from FP32 accumulators.
- Selection: `native/shared/cuda/expert_router.cu:73-113`, `select_fast_kernel<true,true>` (dispatched at `:296`).
  - FP32 sigmoid of the FP32 logit (`:80`).
  - FP32 `score + e_score_correction_bias` for ranking (`:85`).
  - The weight is the unbiased sigmoid score read back from memory (`:103`), normalised and scaled by `routed_scaling_factor` (`:111`).
- Operand dtypes:
  - `weights.rs:588-589` loads `mlp.gate.weight` as stored and `e_score_correction_bias` widened to FP32.
  - The local K3.25 headers show `mlp.gate.weight` BF16 `[288, 4096]` and `e_score_correction_bias` F32 `[288]`, so the GEMM operands are the checkpoint's own BF16.
- CuteAFD does not read `moe_router_dtype` (no reference in `rust/` or `python/` for this family). The FP32 path is unconditional.

**Verdict: handled correctly.** The computation is the upstream fp32-output form: BF16 operands, FP32 accumulation, FP32 logits. Only the summation order differs from `torch.mm`. This verdict is from source; no numerical comparison was run.

## D4: routed SwiGLU limit not passed

**The vLLM-engine issue.** The EXL3 MoE method planned the b12x kernels without `swiglu_limit`. The fix passes it to the projection-mixed caps and to `compile_mixed_trellis` (`tpurtell/04-d4-routed-swiglu-limit/patches/port-exl3-routed-swiglu-limit.py:4-10,53,73`).

**CuteAFD counterpart: local EXL3 routed experts on RTX.**
- **Export.**
  - `python/tools/aot/package_exl3_aot.py:236-242`: `SWIGLU_LIMITS = {'glm': None, 'qwen4': None}` and `swiglu_limit(geometry)` returns `SWIGLU_LIMITS.get(geometry, 10.0)`. The GLM 5.3 Flash geometry is `glmf` (`rust/crates/cuteafd-core/src/expert_geometry.rs:242`), so it gets 10.0.
  - `python/tools/aot/export_b12x_exl3_aot.py:117` defaults `swiglu_limit=10.0`, and `:214` passes `swiglu_limit=swiglu_limit` into the options of `compile_mixed_trellis` (`:230`). That is the same b12x entry point the vLLM fix patched.
  - The manifest records it (`:281`).
- **Runtime guard.**
  - `rust/crates/cuteafd-daemon/src/shared/experts/exl3/execution.rs:546-553`, in `with_modules`, the constructor every EXL3 execution goes through, including local RTX `shared/experts/local.rs:314` and TP2 `shared/experts/rtx/exl3.rs:445`.
  - It requires `meta.swiglu_limit == cuteafd_core::expert_geometry().swiglu_limit()`, or startup fails with "EXL3 export/residency geometry mismatch".
  - The expected value is `expert_geometry.rs:251-253`: `Some(10.0)` for every shape except GLM 5, MiMo and Qwen 4.
  - The manifest field is `Option<f32>` (`execution.rs:179`), so a package without the key reads as `None` and is refused.
  - The same key is part of the reduction-plan signature (`execution.rs:118`).
- **Shared expert and dense MLPs.**
  - `si:…/glmf.py:1133`: `GlmSwiGLU(self.i, limit=g.swiglu_limit)`, used by the BF16, FP8 and W8 variants (`:1124-1190`).
  - `si:…/_glm_kernels.py:551-553`: `gate = fmin(gate, limit)`; `up = fmax(fmin(up, limit), -limit)`.
  - The geometry is `si:…/_common.py:315`, `swiglu_limit: float = 10.0`.
  - The head-split half geometry keeps it (`python/tools/aot/export_b12x_dsv4_aot.py:711-713` changes heads and intermediates only).

**Verdict: handled correctly.** The limit reaches the compiled routed-expert kernels, and the runtime enforces it.

**Not read.** The clamp's implementation inside b12x `mixed_trellis`. Whether activations reach 10 was not measured here; it was not measured in the vLLM investigation either.

## D5: workspace not locked after graph capture

**The vLLM-engine issue.** The workspace manager is never locked after CUDA-graph capture, so a later resize could move buffers that captured graphs point at. Stage A did not exercise it: resizes happened only during profiling.

**CuteAFD counterpart.**
- Decode is captured per segment (`engine.rs:4221-4290`). Replay assumes "the graph's pointers are persistent engine buffers of that rank" (`:4234`).
- The capture itself states: "capture records this stream's launches; nothing in a segment synchronizes the host or allocates" (`:4250-4251`).
- The decode workspace:
  - is allocated once at the configured decode capacity, only when absent (`engine.rs:3080-3093`, `if cell.borrow().is_none()`);
  - is allocated before startup capture (`engine.rs:1833-1836`, "Allocate fixed workspaces before measuring the graph executables' physical memory");
  - cannot be installed a second time (`engine.rs:3056-3066`, "step workspaces already allocated").
- `prepare_serving_workspaces` (`engine.rs:1805-1813`) allocates the decode workspaces, prefill lanes and drafter workspace before readiness.
- Prefill lanes can only be appended (`engine.rs:3097-3115`), and prefill runs eagerly.
- The DFlash2 drafter is eager: "Eager per-round launch" (`rust/crates/cuteafd-daemon/src/families/glm5/dflash.rs:966-967`). Its workspace is recreated only if smaller than the step (`:951-955`), and it is always sized at `max_sequences`.

**Verdict: not applicable (different design).** There is no growable shared workspace, so there is nothing to lock. Within `glm5_flash/engine.rs` and the drafter, no path reallocates a buffer that a captured graph references.

**Limit of this audit.** Not every shared component was audited for lazily grown device buffers referenced inside decode segments: the EXL3 shared arenas, peer-exchange buffers and token I/O.

## D6: stale warm-up tail block ids

**The vLLM-engine issue.** The model runner's start-up warm-up left a two-block tail entry in every runner row that was never cleared. Without D2's fix, those stale ids were the source of foreign writes.

**CuteAFD counterpart.**
- There is no persistent per-runner-row block table. Each step's tables are built on the host from the sequences' placements and uploaded before the step (`engine.rs:3582-3592`, `put_tables`). Under context, they are uploaded "after both streams drained" (`engine/context.rs:32-33`).
- Padding rows, and the all-masked startup graph captures (`engine.rs:1569-1575`, `startup_tables`), use `masked_row` (`rust/crates/cuteafd-daemon/src/shared/decode_graph.rs:63-65`):
  - `position: -1, kv_slot: -1, pool_slot: -1, state_slot: -1`.
  - The writers skip negative slots (`si:…/_glmf_kernels.py:911-912`; pool keys only for `pool >= 0`, `:965`, `:1381`).
  - `GlmfIndexExpand` gives a negative position an empty selection (`count <= dense_limit` with count 0).
- A new sequence's KDA state and compact tails are zeroed before its first step: `start()` (`engine.rs:2758-2760`) calls `reset_slot` (`:2860-2868`), from `prefill_step` when `start == 0` (`engine.rs:3297-3298`).
- A prefix restore copies a captured mark, including the tails, into the sequence's own slot (`prefix.rs:413-423`).

**Verdict: not applicable (different design).** No warm-up state is carried in slot tables, and every per-sequence state region is reset or restored before use.

## D7: index-K prefill writer assumes pool-aligned chunk starts

**The vLLM-engine issue.**
- `_kpool_compress_insert` pools batch rows t−3..t.
- When a chunk starts at s with s mod 4 ≠ 0, the straddling pool is either never written (first prefill row in the step) or pooled from the previous request's tokens (another request precedes it).

**CuteAFD counterpart, keys cache (heads).**
- `GlmfPoolKeys` (`si:…/_glmf_kernels.py:922-1000`): "The pool is the row's own token and the three before it (record slots `slots[row] - 3 .. slots[row]`: a pool never crosses a 64-row page)".
- `first = slots[token] - 3` (`:966`). Members come from `token_keys` at the sequence's own record slots, not from neighbouring batch rows.
- Those keys persist from the earlier chunk or step (`GlmfIndexPost`, `:908-919`), and the post runs before the pool in the same program (`si:…/glmf.py:1362-1363`).
- Record slots are per-sequence (`engine.rs:653-656`). A 4-aligned pool lies in one 64-row page, so its four slots are contiguous.

**Compact cache (context, one GPU).**
- `GlmfPoolKeysTail` (`si:…/_glmf_kernels.py:1293-1476`): "the ones in this step from its key | gate rows …, the ones before it from the tail of its sequence's KDA slot" (`:1296-1301`).
- `held = start % 4` (`:1375`). For each member, `before = at < first` (the sequence's first step row) selects `tail + TAIL_HEADER + t * KEY_ROW_BYTES` (`:1385-1391`).
- Other sequences' rows are never read, because the boundary is `seq_first`, not the batch.

**Prefix cache.**
- A restore point can be any `kda_len` (`prefix.rs:32-35`, exact frontiers).
- A fork copies a partial tail unit's rows, including token keys in keys mode, and its complete pools (`prefix.rs:439-463`; header `:8-9`).
- Compact tails travel in the KDA mark (`prefix.rs:11-16`).

**Verdict: handled correctly.** Unaligned chunk starts can occur: restores at any length, and prefill after decode. Each straddling pool has a defined source: the sequence's own stored keys, or its own tail.

## E1: batch-size-dependent router weights

**The vLLM observation.**
- Above about 1,024 rows, the served fused router rebuilt the unbiased score as (s+b)−b in fp32, so weights differed slightly from the ≤1,024-row kernel.
- Expert selection was unaffected.

**CuteAFD counterpart.**
- **Selection and weights:** `native/shared/cuda/expert_router.cu:73-113`. One CTA of 512 threads per row. The weight takes `selected[rank]=scores[row*experts+i]` (`:103`), the stored unbiased sigmoid score, not a rebuilt one. No branch depends on the row count.
- **Logits:** `RoutedBf16Projection.__call__` switches route on the live row count (`si:…/_skinny.py:453-465`). For N = 288 the skinny GEMV serves up to 160 rows (`skinny_max_rows`, `:225-232`) and the TMA tensor-core GEMM serves more.
  - Decode and verify steps of 64 or 128 rows fall on the skinny side. Prefill chunks above 160 rows fall on the TMA side.
  - The two routes use different FP32 summation orders. The source makes no bit-equality claim across them; it makes one only within the TMA tile variants (`:288-291`) and within skinny row tiles (`:235-238`).
  - `engine.rs:4767-4771` (`moe_front` doc) runs the router scores over each packed sequence's own rows; `docs/models/glm5_flash.md:123-126` gives the reason: "as its own pass would". `docs/models/glm5_flash.md:395-397` states that batch-invariant prefill and verify are deferred.

**Verdict.**
- The E1 mechanism ((s+b)−b above 1,024 rows): **not applicable (different design)**.
- Router-logit bit equality across the 160/161-row route switch: **cannot determine from source**.
- Measured afterwards on one GPU: see `results/2026-10-26-e1-router-route/` in this repository.

---

## `swiglu_limit` and related keys: what is read from `config.json`

| Consumer | Clamp applied | Source of the value | Reads `config.json`? |
|---|---|---|---|
| Routed experts, local EXL3 (RTX, TP1 or TP2) | 10 | EXL3 export default per geometry (`package_exl3_aot.py:238-242`; `export_b12x_exl3_aot.py:117,214`), checked against the expert-shape constant (`expert_geometry.rs:251-253`; `exl3/execution.rs:551`) | No |
| Shared expert (I = 2048) and dense MLPs (layers 0-2, I = 12288) | 10: gate ≤ 10, up ∈ [−10, 10] | `si:…/_common.py:315` → `glmf.py:1133` → `_glm_kernels.py:551-553`, baked at AOT export | No |
| DFlash2 drafter | none; it has no experts | dense Qwen3-style MLP (local `incoai/GLM-5.3-Flash-DFlash2/config.json`: `model_type` qwen3, `intermediate_size` 12288, no `swiglu_limit`); `native/families/glm5/cuda/glm_dflash.cu:154-160` is an unclamped `silu(g)*u` | n/a (its config has no such key) |

- `config.json`'s `swiglu_limit` is parsed into `GlmNextConfig.swiglu_limit` (`rust/crates/cuteafd-loader/src/families/glm5_flash/config.rs:110`, `unwrap_or(0.0)`). It is printed in plan notes (`rust/crates/cuteafd-loader/src/plan/families/glm.rs:312-315`).
- No GLM Flash engine code that consumes it, and no check that it equals the compiled 10, was found: `grep '\.swiglu_limit'` in `rust/` finds only the EXL3 and FP8 guards and test fixtures.
- The local K3.25 checkpoint carries `swiglu_limit: 10.0`, so compiled and declared values agree for this checkpoint. A checkpoint declaring another value would not be detected.

Related keys:
- `routed_scaling_factor` is read (`config.rs:109`) and used as the selection scale (`engine.rs:4787`).
- `scoring_func`, `n_group` and `norm_topk_prob` are validated: an `ensure!` requires normalized sigmoid with no groups (`config.rs:89-91`).
- `moe_router_dtype` (`"float32"` in the checkpoint) is not read; FP32 logits are unconditional (D3).
- `e_score_correction_bias` is loaded as FP32 (`weights.rs:589`).
- `index_topk` (2048) and `index_kpool` (4) are read (`config.rs:120-121`). The programs are compiled for the same constants (`si:…/_common.py:305-306`), and the pool kernels refuse any `kpool != 4` (`si:…/_glmf_kernels.py:937`, `:1316`, `:1494`).

## Limits of this audit

- Source only. No behaviour was measured, and the released image was not inspected.
- The submodule files were read at the pinned commit. That the image was built from the same commit was not verified.
- Not read: b12x internals (the `dsv4_indexer` top-k, the `mixed_trellis` routed-expert kernels), the FP8 and NVFP4 local expert paths (not this configuration), Spark worker paths (not this configuration), and the `layers` placement.
