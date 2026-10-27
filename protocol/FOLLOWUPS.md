# Labelled follow-ups (outside the frozen protocol) — declared 2026-10-26 before running

Approved by the maintainer after Block Q results were known. They are diagnostic, labelled as follow-ups, and
reported separately from the frozen comparison. Design fixed here before any request.

## F1 — CuteAFD FP8 ablation on the 8-16K precision gap

Question: which of CuteAFD's FP8 choices account for its P-B gap to vLLM at 8-16K (C1 − V1 KL +0.0044,
top-1 −1.04 pts, generated rows)? CuteAFD is bit-deterministic, so single runs per arm suffice.

| Arm | Change from C1's scoring launch | What it tests |
|---|---|---|
| F1a | `GLM5_FLASH_KDA_FP8=off` | FP8 row128 KDA projections → BF16 |
| F1b | `GLM5_FLASH_FP8_HEAD=off` | FP8 output head → BF16 |
| F1c | `GLM5_FLASH_FP8_PREFILL=off` | W8A8 prefill GEMMs → W8A16 |
| F1d | all three | combined |

Not testable: MLA / shared / dense projections stay FP8 (no BF16 option in v3.0.1; source).
Measure: tpurtell's CLI, `--tier full --score-path prefill`, same dataset pin; our validated port; paired against
C1 (same engine) and V1 (vLLM) on generated rows, overall and by bucket (0-2K / 2-8K / 8-16K) and block.
Cost: ~2 min launch + ~5 min scoring per arm, about 30 min of both GPUs. Run between CuteAFD's Block T and L.
Reading rule (declared now): an arm "accounts for" the gap at 8-16K if it moves C1's 8-16K KL toward V1 by more
than the paired interval of C1 − V1; partial movement is reported as partial. Any arm that fails memory
admission is reported as not runnable.

## F2 — vLLM v0.9.2 prefix cache: why 0 cached tokens on a repeated 8K prompt

Observation (Block T cached cell): the same 8,192-token prompt sent 4 times in sequence got
`cached_tokens` 0 and TTFT 2.10 s each time, with `--enable-prefix-caching --mamba-cache-mode align`.
Design, on the normal served v0.9.2 container (no plugin), one stream, thinking on, max_tokens 16:
- identical prompts at 1K, 4,352, 8,192, 8,704 and 17,408 tokens (multiples of 4,352 included because of the
  align mode's block size, per discovery), each sent 3 times in sequence;
- record usage `cached_tokens`, TTFT, and `/metrics` prefix-cache query/hit counters before and after;
- grep the server log for cache-mode and block-size lines.
Cost: a few minutes during the final vLLM session. Reported as: hits or no hits per length, and the evidence for
the mechanism if it is visible; no fix attempted.

### F1 amendment A1 (2026-10-27 ~00:30, before any F1 request)

Framing: the engine's intent is precision kept within a bar while optimizing speed, so F1 must also show
each switch's speed cost. Added per arm, after its precision scoring and on the same launch:
- a speed subset with the Block T driver: inputs 1K and 8K, 1 and 8 streams, prose and code, replicates 0 and 1
  (16 batches, thinking on, temperature 1.0 / top_p 0.95, same seeds as Block T);
- a baseline arm **F1-base** = C1's scoring launch unchanged (precision already known: identical bytes to C1),
  speed subset only, because the scoring launch (bench endpoint, all-row prefill logits) is not the serving launch.
Speed is reported as each arm's per-stream decode and aggregate relative to F1-base, cell by cell.

## Declared 2026-10-27 ~01:15 after the independent audit (`AUDIT-2026-10-27.md`), before any of these requests

**F1 note.** `GLM5_FLASH_KDA_FP8=off` also drops `--kda-output-shard --kda-prefill-expanded` (launcher coupling,
run-family.sh around line 2014), so arms F1a and F1d change two things at once; reported that way.

**Drift (protocol principle 6; the repeat subset was never declared before now).** Same driver, the same seeds and
the **same nonce salt** as each engine's own Block T run, so prompts are byte-identical to that engine's earlier cells:
inputs 1K and 32K, 1 and 8 streams, code and prose, replicates 0 and 1 (`block_t.py --lengths 1024 32768 --levels 1 8
--contents code prose --reps 0 1 --no-cached-cell --nonce-salt <salt>`).
- CuteAFD: right after its Block L, on the same serving launch, salt `C1-r1:1793079558737877023`.
- vLLM: at the end, on the normal served launch, salt `V1-r1:1793064953235561649`.
Reported per cell as later / earlier median. GPU telemetry (clocks, power, temperature, throttle reasons) is logged
every 5 s from 01:06 onward (first sample; file name says 0050) (`gpu-telemetry-from-0050.csv`).

**F3 — second vLLM launch for precision (audit I1).** vLLM's multi-chunk prefill is not run-to-run deterministic, so
CuteAFD is compared against more than one vLLM draw. A new capture-mode launch (fresh process) captures P-B and P-A
once more (run tag v2-r1). Headline then pairs CuteAFD against the mean of all vLLM runs; launch-to-launch spread is
reported next to within-launch spread.

**M2 (draft acceptance, partial).** vLLM's `/metrics` speculative-decoding counters are read before and after each drift
cell. CuteAFD exposes no acceptance counter on its API; none is reported for it.

**F2** as declared above, on the final normal vLLM launch.

Order after CuteAFD Block L: CuteAFD drift → stop → vLLM capture launch (F3) → stop → vLLM normal launch (drift, F2).
