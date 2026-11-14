# Method: how the results are made and how to weigh them

:::answer
Every result on this site is a **finding**: one measured quantity, with its sign convention, unit, sample size,
interval, scope and the file it was read from. Findings were written from the published data of each run, and the
build refuses any number that does not trace to that data. **Judgements across runs** are separate entries, each with a
strength (*established*, *supported*, *indicated* or *open*) set by a fixed rule, the findings it rests on, and the
nearest stronger claim it does not support. Comparison rules were frozen before the data in every run that had a
protocol; anything decided after looking is labelled *post hoc* or *exploratory* wherever it appears.
:::

## What is measured {#what-was-measured}

| Instrument | What it measures | Path | Reference | Runs |
|---|---|---|---|---|
| Teacher panel (P-A) | full-vocabulary KL from BF16 next-token probabilities, 25 windows of 2,048 tokens | prefill (the engine scores given text) | BF16 model's logits on the same tokens | v3.0.1, K4, v4, v5 |
| Fidelity set (P-B) | KL from BF16 on generated positions, 64 prompts to 14.4K tokens; top-20 or coarse measures | prefill | a BF16 run stored as its top 1,024 tokens | v3.0.1, K4, v4, v5 |
| Long documents (Q2) | NLL of each engine on six human-written documents at 32K-128K tokens | prefill | none: engine against engine and against its own repeats | v3.0.1, K4 |
| Speed grid (Block T) | decode tokens per second per stream, aggregate throughput and time to first token, 1K-128K prompts, 1-16 requests at once | serving | the other engine, or the same engine as shipped | v3.0.1, K4, v4 |
| Long output (Block L) | whether replies of up to 128K tokens finish and pass machine checks (tests, answers, schema, length) | generation | none: pass counts per engine | v3.0.1, K4, v4 |
| Thinking length | reasoning tokens or characters per reply, and how each reply ended, with distinct seeds per repeat | generation | another core, engine or setting on the same prompts | thinking-length, core-swap, code-thinking, FP8 ablation, new questions |
| Stop decision | the probability of ending the thinking at a fixed point of a fixed trace | prefill (teacher-forced traces) | another core on the same traces | thinking-length, core-swap, new questions |
| Graded long-context tasks | field score on synthetic join, ledger and trace items at 4K-127K tokens | generation | the BF16-core configuration (anchor) | v5 |
| Tool calling | points on a multi-turn tool-calling benchmark | generation | the other engine or checkpoint | tool calling |

Fixtures are not comparable across model families, and NLL and KL are per tokenizer: every number on this site is
one model (GLM-5.3-Flash) and one tokenizer.

## What each instrument resolves {#resolves}

How large a difference each instrument can see on this setup, from repeats of the same arm. A difference smaller
than an instrument's own repeat spread is not read as an effect.

**Distance from BF16 (prefill).** CuteAFD repeats bit for bit; the vLLM fork's mean moves little between runs, but its
rows vary beyond the first prefill chunk, so CuteAFD is paired against more than one vLLM run.

{{cite V3-repeat-cuteafd V3-repeat-vllm-pb V3-i1-selfdiv V3-f3-pa-launch K4-vllm-pb-spread CP-bf16-repeat}}

**Stop decision (prefill on fixed traces).** On the vLLM fork two launches of one arm differ by about as much as the
core contrast; CuteAFD launches are bit-identical.

{{cite TL-launch-stop TL-launch-kl AP-cuteafd-cross-day}}

**Graded tasks (generation).** Rerunning the same arm with new seeds changes about a fifth of every-field-right
outcomes; four passes narrow the intervals by about a fifth over two.

{{cite CP-flip-floor CP-fourpass-family}}

**Speed.** Re-runs and drift repeats set each run's band.

{{cite V3-m1-noise V3-drift K4-t-drift}}

**Long documents (NLL, engine against engine).** Six documents bound an NLL difference to a few thousandths of a nat.

{{cite V3-q2-nll K4-q2-cross-floor}}

## Leads that did not repeat {#leads}

{{synthesis M-leads}}

## The standard every finding meets {#standard}

| Field | What it holds |
|---|---|
| quantity, sign | what was measured and which way is up, with the difference named (`b − a`) |
| unit, n | the unit of analysis (window, item, question, prompt, document, cell) and how many |
| interval | level and method: bootstrap over which unit, how many replicates, which seed; or none (descriptive) |
| scope | engine and version, checkpoint, item set, context range, path (prefill or generation), hardware |
| status | protocol, amendment, follow-up, post hoc, exploratory, check, source reading, accounting |
| family | how many intervals were computed alongside it in the same table, and how many excluded 0 |
| replication | replicated, failed to replicate (with a link), or not attempted |
| class | **difference** (interval excludes 0) · **not detected** (interval includes 0; the largest effect not excluded is stated) · **descriptive** (counts, no interval) · **source reading** · **accounting** |

Wording follows the class. An interval that includes 0 is written as "not detected; a cost up to X is not
excluded", never as "no difference". A result found on one item set is not generalised past it. A lead that failed
to replicate stays published beside the replication, and each links to the other. Intervals are reported as
computed; they are not corrected for multiplicity unless a protocol said so, and the family size beside each one
says how many were computed.

## How strong a judgement is {#strength}

The strength vocabulary is defined on the [terms page](terms.html#strength). A judgement is never stronger than its
weakest essential finding, and each states what it does *not* show.

## Protocols and the order things ran {#protocols}

<span id="k4-protocol"></span><span id="k325-protocol"></span>

A protocol fixes the arms, items, measures and reading rules before the first comparison request. Follow-ups were
declared after earlier results were read, each before its own requests; they are labelled as such. Amendments are
listed with the time they were written.

{{protocols}}

## Setup {#setup}

One machine throughout: two NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition GPUs at 300 W. Engines run
as their author ships them, plus a short list of local settings recorded with each run (listen address, request
logging, output limit, memory utilization on the vLLM fork). Where a run modified an engine, it says so: the vLLM
fork runs with the local core loader are a local loader modification, not a release of the engine.

{{setup}}

## Every run {#timeline}

{{runs}}

## Changes {#changes}

- **2026-11-13** Rebuilt on findings. The instrument table, the protocol table, the setup table and the run list
  are generated from the run index, so they cover every run. The day-by-day timeline of the first two runs is
  replaced by the protocol table and each run's own record; the earlier page is in the repository history
  (`docs/method.html` before this change).
