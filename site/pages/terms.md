# Terms

Each term is defined once here, and the other pages link to these definitions. Where a run used a term more narrowly,
the run's own definition is in its study record.

## Engines and versions {#engines}

### CuteAFD {#t-cuteafd}
tpurtell's engine, built for attention/FFN disaggregation. Here it always ran on two GPUs with the experts local.
Versions tested: v3.0.1 (2026-10-26/27), v4.0.0 (2026-10-30 to 11-06) and v5.0.0 (2026-11-10 to 11-12), all with
the launcher unmodified. Settings are named by their environment variables (e.g. `GLM5_FLASH_KDA_FP8`).

### vLLM fork {#t-vllm-fork}
tpurtell's vLLM fork for GLM-5.3-Flash on two RTX GPUs. v0.9.2 is the release image in every run. The thinking-length
runs also used a v0.9.2-experimental image with a **local loader modification** (route b), which is not a tpurtell
release.

### Machine {#t-machine}
Two NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition GPUs at 300 W. A desktop session held about 2 GB on GPU 1.
Every number on this site comes from this one machine.

## The model and its parts {#parts}

### Routed experts {#t-experts}
The mixture-of-experts matrices that a router selects per token: 94.9% of the language model's weights ([CP-bits-outside-experts](v5.html#f-CP-bits-outside-experts)). The
checkpoints here differ most in how these are quantized.

### Core {#t-core}
Everything in the language model outside the routed experts. That means the attention projections, the shared
experts, the dense feed-forward layers 0-2, the output head, the embedding and the multi-token-prediction block:
the other 5% of the weights. When a page says a configuration's *core* is BF16, K6 or FP8, it means these weights. Some
runs swapped only part of the core; their pages name the part.

### KDA and MLA {#t-kda}
The model has two kinds of attention layer. The engine calls one kind KDA (in v5.0.0's loader source) and the other
MLA. `q_b_proj` and `o_proj` are two of the MLA projections (12 and 46 matrices); they are the projections that the
HQA and compact modes treat differently.

### Output head {#t-head}
The final projection from hidden state to vocabulary logits.

## Checkpoints and configurations {#checkpoints}

| Name | What it is |
|---|---|
| K3.25 | wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-v1: routed experts in the 3.25-bit format (three quarters of the expert matrices at 3 bits, one quarter at 4) |
| K3.25-Core-FP8 | the same experts with 179 core projections replaced by FP8 copies (byte-checked); what CuteAFD runs as K3.25. In the v5 study it is the configuration `k325-fp8` |
| K4 | brandonmusic GLM-5.3-Flash-tr3-4bpw: routed experts at 4 bits, core BF16 (CuteAFD converts the BF16 projections to FP8 at load by default) |
| K4-Core-K6 | wrldsuksgo2mars (tpurtell) checkpoint: its own 4-bit routed experts, a different quantization and calibration from K4's, with a 6-bit (K6) core |
| K4-Core-K6-HQA | the same experts and K6 core, plus BF16 copies of `q_b_proj` and `o_proj`; `ATTENTION_MODE` picks which copy loads |
| anchor | v5 study: the K4-Core-K6 experts with the original BF16 core and BF16 head, FP8 conversions off. A locally derived checkpoint, used as the reference, not as a recommendation |
| hqa | v5 study: K4-Core-K6-HQA in its default mode: BF16 `q_b_proj` and `o_proj`, the rest of the core and the head K6 |
| compact | v5 study: the same checkpoint with `ATTENTION_MODE=compact`: K6 core and head |
| exlr8-k4 | v5 study: kindlingai EXLR8 K4 checkpoint, a different quantization of the whole model; differences from it are whole-checkpoint differences |
| k325-fp8 | v5 study: K3.25-Core-FP8 under CuteAFD v5.0.0 defaults |

## Measures {#measures}

### KL from BF16 {#t-kl}
How far a configuration's next-token distribution is from the unquantized BF16 model's on the same text, in nats per
position (0 = identical). It is measured on the prefill path only, and only to 14.4K tokens of context, because no
BF16 reference exists beyond that on this machine. Three variants appear, and they **are not comparable with each
other**:
- **full-vocabulary KL** on the teacher panel;
- **coarse KL** on the fidelity set: the reference's top 1,024 tokens plus one term for the rest;
- **top-20 KL** (KL20, KL_pb20): used where only top-20 logits were kept (the K4 run).

### Teacher panel (P-A) {#t-teacher-panel}
Published BF16 teacher logits for GLM-5.3-Flash on 25 windows of 2,048 tokens (51,175 scored rows). The panel shares
its source with the evidence set brandonmusic published for K4 (the windows are document-disjoint from that set's
calibration windows), so it can favour K4. It cannot be expected to favour K4-Core-K6 or the v5 probe arms, which carry
K4-Core-K6's experts, calibrated on another panel ([CP-panel-tilt](v5.html#f-CP-panel-tilt)).

### Fidelity set (P-B) {#t-fidelity-set}
The engine author's published set: 64 windows, contexts to 14.4K, scored on 15,104 generated positions in 53
windows. Its relation to any checkpoint's calibration data is not known.

### NLL {#t-nll}
Negative log-likelihood of given text, in nats per token. It is per tokenizer, so it is comparable only within one
model family. Q2 used it to compare the two engines at 32K-128K, where there is no BF16 reference.

### Field score {#t-field-score}
The v5 graded tasks: correct fields / fields in a reply that finished on its own. A reply that hit the cap or the
repetition abort scores 0. **Every field right** is the share of replies scoring 1.

### Unfinished reply {#t-unfinished}
A reply that did not end with `stop`, because it reached the reply cap or the repetition abort.

### Thinking length ratio {#t-ratio}
The thinking-length runs: the geometric mean over paired (prompt, seed) replies of reasoning tokens A / B, counting
only pairs where both replies finished. The interval is a bootstrap over prompts.

### Stop decision {#t-stop}
On fixed reasoning traces: the log-probability the model gives to closing its reasoning (`</think>`) at the point
where the trace closed. It is used to ask whether a change to the weights moves *when* the model decides to stop,
without sampling.

## Status of a result {#status}

| Status | Meaning |
|---|---|
| protocol {#t-protocol} | The question, the analysis and the decision rule were frozen (hashes recorded) before the first request |
| amendment | Added by a dated amendment, written after earlier results were read and before its own first request |
| follow-up | A later measurement planned before its own data, outside the frozen protocol |
| post hoc {#t-post-hoc} | An analysis chosen after the data were seen; it can suggest, it cannot confirm |
| exploratory | A probe run to learn what to measure; useful evidence, not a comparison |
| check | Verification of inputs, tools or reproducibility |
| source reading | Read in the engine's source code or logs; nothing measured |
| accounting | Counted from files (e.g. checkpoint headers); nothing run |

## Result classes {#classes}

| Class | Meaning |
|---|---|
| difference | The 95% interval excludes 0 (or 1 for ratios) |
| not detected | The interval includes 0. The finding states the largest effect the interval does not exclude; it never says "no effect" |
| descriptive | Counts or values without an interval or rule |
| source reading, accounting | As in the status table |

## Strength of a synthesis {#strength}

A synthesis is a judgement across findings. Its strength can be no higher than its weakest essential finding.

| Strength | Rule |
|---|---|
| established | Pre-set rules hold on two or more independent item sets, launches or engines, in the same direction |
| supported | A pre-set rule on one item set, not contradicted |
| indicated | Post hoc, exploratory, or a single interval read after looking |
| open | Evidence mixed or missing |

## Intervals and multiplicity {#intervals}
Intervals are 95% percentile bootstraps over the unit each finding names: items, prompts, windows, documents or
questions. The number of draws and the seed are stated per finding. Where many intervals were computed in one
family, each finding says how many and how many exclude 0. About 1 in 20 would exclude 0 by chance if there were no
difference anywhere. No correction is applied unless the protocol said so.
