# Long tasks: long prompts and long replies

:::answer
**Accuracy on graded long-context tasks falls with length in every configuration**, the BF16 core included
(*supported*); much of the fall is replies that did not finish. **Precision showed as a task cost at 127K, for some
configurations**: K3.25-Core-FP8 against three 4-bit-expert configurations (*supported*), and compact against hqa
but not against the BF16 core (*indicated*); nothing was detected at 4K and 16K.
**Long replies to 130K tokens finish and pass** their code and math checks on both engines (*supported*, 8 replies per
cell). Prompts of 256K-1M tokens were accepted and used in a one-request pilot (*indicated*).
:::

## Accuracy against length {#fall}

{{synthesis S-long-fall}}

## Where precision costs accuracy {#cost}

{{synthesis S-long-cost}}

{{synthesis S-long-cost-compact}}

How far each configuration is from BF16, and whether that distance predicts these results, is on the
[precision page](precision.html#tasks).

## Long replies {#long-output}

{{synthesis S-long-output}}

## Very long prompts {#long-prompts}

{{synthesis S-long-retrieval}}

## Not measured {#limits}

- Real documents or tasks other than the synthetic join, ledger and trace items at long context.
- Accuracy at long context on the vLLM fork: the graded long-context study ran on CuteAFD v5.0.0 only.
- Long replies with intervals: 8 replies per cell.

## Changes {#changes}

- **2026-11-13** Rebuilt on findings. Long-reply results from three runs are now one judgement with its basis; loop
  counts follow the audit's rule throughout. The earlier page is in the repository history.
