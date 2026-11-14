# Thinking length: what changes how long the model thinks

:::answer
**On code, CuteAFD's FP8 KDA setting accounts for most of a length gap between its two arms** (*supported*): switched
off, the BF16-core arm thinks about as long as the native 6-bit core. On the vLLM fork the core's stored precision
changed nothing detectable. **On science questions, the core's precision was not detected to change the stop
decision on either engine** (*established*), but **how long the model thinks in free generation there is not known**
(*open*: one question, one engine). **Whether shorter thinking costs correctness is open**.
:::

The science-question runs use a public multiple-choice benchmark; its name appears only in those runs' files.
Thinking length is measured as reasoning tokens or characters per reply, with distinct seeds per repeat.

## Code: the FP8 KDA setting {#code}

{{synthesis S-think-code-kda}}

## Science questions: the stop decision {#stop-decision}

{{synthesis S-think-stop}}

## Science questions: free-generation length {#science-length}

{{synthesis S-think-science-length}}

## Does shorter thinking cost correctness? {#correctness}

{{synthesis S-think-correctness}}

## A lead that did not repeat {#lead}

A layout lead on the vLLM fork (two attention projection groups in BF16) was found after looking at 11 questions and
tested on 30 new ones, where it was not detected; see [leads that did not repeat](method.html#s-M-leads).

## Not measured {#limits}

- Free-generation length on science questions beyond one question, and on CuteAFD at all.
- Whether the KDA projection format or KDA output sharding drives the code result.
- Other prompt families than code and science questions.

## Changes {#changes}

- **2026-11-13** Rebuilt on findings. Corrected: the earlier page said neither thinking length nor the stop decision
  changes with the core, "on 41 questions and both engines". The stop decision was measured on both engines; free
  generation on science questions was one question on one engine, inconclusive ([corrections](audit.html#c01)).
