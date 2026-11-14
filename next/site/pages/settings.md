# Settings: what each CuteAFD setting buys and costs

:::answer
**ATTENTION_MODE=hqa** (v5.0.0) holds less memory than a BF16 core with no task cost detected (*supported*);
**compact** saves more and scores below hqa at 127K (*indicated*). **W8A16 prefill** narrows CuteAFD's long-code
distance gap on K3.25 for about 4% first-token time (*supported*); on K4 no setting closes it. **BF16 KDA and head**
shrink the KV pool, and BF16 KDA did not fit a K4 serving launch on v3.0.1 (*supported*); BF16 KDA lengthens code thinking
([thinking](thinking.html#code)).
:::

| Setting | What it changes | Judgement |
|---|---|---|
| `ATTENTION_MODE` (v5) | which copies of two attention projection groups run: BF16 (hqa) or K6 (compact) | [S-set-attention](#s-S-set-attention), [S-set-compact](#s-S-set-compact) |
| `GLM5_FLASH_FP8_PREFILL=off` | W8A16 instead of FP8 prefill GEMMs | [S-fp8-settings](precision.html#s-S-fp8-settings), [S-set-costs](#s-S-set-costs) |
| `GLM5_FLASH_KDA_FP8=off` | BF16 KDA projections; on two GPUs also KDA output sharding | [S-think-code-kda](thinking.html#s-S-think-code-kda), [S-set-costs](#s-S-set-costs) |
| `GLM5_FLASH_FP8_HEAD=off` | BF16 output head | [S-fp8-settings](precision.html#s-S-fp8-settings), [S-set-costs](#s-S-set-costs) |
| scale rule (amax, best) | how FP8 block scales are chosen | [S-fp8-settings](precision.html#s-S-fp8-settings) |
| `MAX_CONTEXT_TOKENS` | the planner's context floor; needed to start K4 on two GPUs at v3.0.1 | [S-run-capacity](running.html#s-S-run-capacity) |

## Attention mode (v5.0.0) {#attention-mode}

{{synthesis S-set-attention}}

{{synthesis S-set-compact}}

## What the FP8 settings cost {#costs}

{{synthesis S-set-costs}}

## Not measured {#limits}

- What these settings do on the decode path's precision: only prefill was scored.
- Settings on engine versions other than those named in each judgement.

## Changes {#changes}

- **2026-11-13** Rebuilt on findings: one row per setting, each linked to the judgement that covers it. Corrected:
  the BF16 head's effect was given as "no change"; it is a resolved, very small change ([corrections](audit.html#c07)).
