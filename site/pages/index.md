# Engines and quantizations of GLM-5.3-Flash on two RTX PRO 6000s

:::answer
This site measures **two inference engines** by the same author, CuteAFD and tpurtell's vLLM fork, and **several
quantized checkpoints** of GLM-5.3-Flash, on one machine: two RTX PRO 6000 Blackwell Max-Q GPUs at 300 W. The aim
is evidence for choosing a deployment: what each engine and each precision cut costs or buys in distance from the
original BF16 model, task accuracy at long context, thinking length, speed and memory. Every answer below is a
judgement across studies with a stated strength; each links to the findings it rests on and states what it does not
show. Nothing here is a recommendation.
:::

## Answers so far {#answers}

Strength: *established* (pre-set rules agree on two or more independent item sets, launches or engines),
*supported* (a pre-set rule on one item set, not contradicted), *indicated* (found after looking, or exploratory),
*open* (mixed or missing). A judgement is never stronger than its weakest essential finding.
Definitions are on the [terms page](terms.html#strength).

{{answers}}

## What was compared {#compared}

| | |
|---|---|
| Engines | CuteAFD (attention/FFN disaggregation runtime; v3.0.1, v4.0.0, v5.0.0) and tpurtell's vLLM fork for this model on two RTX GPUs (v0.9.2; in some runs with a local core loader, labelled where used) |
| Checkpoints | K3.25 (3.25-bit experts, two builds), K4 (brandonmusic's 4-bit experts), K4-Core-K6 and K4-Core-K6-HQA (4-bit experts, 6-bit core), a locally derived BF16-core checkpoint, and kindlingai's EXLR8 K4 as a reference; see [checkpoints](checkpoints.html) |
| Machine | two RTX PRO 6000 Blackwell Max-Q Workstation Edition, 300 W; every number on this site is from this one machine |
| Studies | 16 runs, dated 2026-10-26 to 2026-11-10 (the last ran until 2026-11-12); see [studies](studies.html) |

## How to use this site {#use}

- **Question pages** (precision, long tasks, thinking length, settings, checkpoints, speed, running it, tool calling)
  give the current answer, the judgements behind it, and what was not measured.
- **Studies** lists every run, every sub-question it asked and every finding it produced; the
  [v5](v5.html) and [v4](v4.html) records hold those releases' studies in full.
- **Method** says how results are made and how to weigh them; the [audit](audit.html) page lists every published
  statement this rebuild corrected.
- **Machine-readable:** [findings.json](findings.json) (every finding and judgement with source pointers) and
  [runs.json](runs.json) (every run, its goals and the files each goal owns). Start there rather than with the HTML.

## Launch files measured {#settings-measured}

The launch configurations that were measured are on [Running it](running.html#configs), as the files that ran.

## Changes {#changes}

- **2026-11-13** Rebuilt from findings: the answers table replaces the earlier summary sections; each answer now has a
  strength and links to its basis. The earlier page is in the repository history (`docs/index.html` before this
  change).
