# Precision: how far from the BF16 model, and why

:::answer
**Most of the distance comes from the routed experts.** Going from 3.25-bit to 4-bit experts moves a checkpoint
several times further toward the BF16 model than switching engines or changing the core's precision does
(*established*). **CuteAFD is slightly farther than the vLLM fork on the same checkpoint**, most of all on long code
(*established*). On K3.25 most of that long-code gap goes with its FP8 prefill, which a setting can remove for about
4% more first-token time; on K4 no setting tried closes it (*supported*). **Distance at short context predicts long-context
accuracy only in part** (*indicated*). The measurements are the prefill path only, to 14.4K tokens of context.
:::

[KL from BF16](terms.html#t-kl) measures how far a configuration's next-token distribution is from the unquantized
model's on the same text. It is measured on the prefill path only (the engine scores given text) and only to
14.4K tokens of context, because no BF16 reference exists beyond that on this machine. Each judgement below cites
the findings it rests on and states what it does not show. The strength rules are on the [terms page](terms.html#strength).

## Every configuration on one measure {#table}

Full-vocabulary KL from BF16 on the [teacher panel](terms.html#t-teacher-panel) (25 windows of 2,048 tokens). This is
the one distance measure taken the same way in every study, so these rows can be compared with each other (see
[S-reproducible](#s-S-reproducible)). Lower is closer. Intervals are shown where the study published one per
configuration. The v4 run published intervals on the *differences* instead; those are in the findings cited below.

{{table precision_teacher}}

The [fidelity set](terms.html#t-fidelity-set), with contexts to 14.4K, uses a different measure (coarse KL), so its
values are not comparable with these. Its rows for the five v5 configurations are on the [v5 record](v5.html#bf16).

## Where the distance comes from {#sources}

{{synthesis S-experts}}

## Engine against engine {#engines}

<span id="long-code"></span>

{{synthesis S-engine-gap}}

## CuteAFD's FP8 settings {#settings}

What each setting costs in speed and memory, on every engine version, is on the [settings page](settings.html).

{{synthesis S-fp8-settings}}

## Does distance predict long-context accuracy? {#tasks}

{{synthesis S-distance-tasks}}

## Comparing across studies {#reproducible}

{{synthesis S-reproducible}}

## Data tables {#tables}

:::more How KL from BF16 is spread over positions (tails), K3.25 and K4 on v3.0.1 {#tails}
K3.25:

{{table kl_tails 2026-10-26-cuteafd-vs-vllm}}

K4 (top-20 measures):

{{table kl_tails 2026-10-27-k4-vllm-cuteafd}}

By position within the teacher panel's windows, K3.25:

{{table kl_tails_position 2026-10-26-cuteafd-vs-vllm pa}}
:::

:::more Fidelity set by context bucket, K3.25 on v3.0.1 (A = the vLLM fork's first run, B = CuteAFD) {#buckets}
The judgements above pair CuteAFD against the mean of three vLLM runs; this table is against the first run alone.

{{table pb_buckets results/2026-10-26-cuteafd-vs-vllm/q/pb/pb-pair-V1-C1.json}}
:::

## Not measured {#limits}

- Distance on the decode path, the path generated tokens take. Every row above scores given text.
- Distance beyond 14.4K tokens of context. At 32K-128K only engine-against-engine NLL exists.
- Other model families, tokenizers, GPUs or power limits. KL and NLL are per tokenizer, so these numbers are not
  comparable with any other model's.

## Changes {#changes}

- **2026-11-13** Rebuilt on the cross-study findings. Changes from the earlier page:
  - Every judgement now states its strength and what it does not show.
  - The table covers every configuration measured (v3.0.1 to v5.0.0) on one measure.
  - Engine versions are named in every row.
  - Corrections:
    - "No difference resolved below 8K on K3.25" now reads: not detected at 0-2K and 2-8K on the fidelity set, beside
      the teacher panel's resolved +0.0017.
    - The BF16 head's effect was given as "no change". It is a resolved, very small change.
  - research.html's precision tables move here.
