# Block Q per-position scores

One row per scored position, one column set per arm, from the scored rows of Block Q. No token ids, logits or texts:
each value is a number computed at that position. Values are rounded to 7 significant digits. Tail and position
statistics computed from these files: `../tails/` (`tools/kl_tails.py`; `python3 tools/kl_tails.py --check`
reproduces them, and `tools/verify.py` runs that check).

Conventions shared by all files: `row` r is the distribution after tokens 0..r, which predicts token r+1; `context` is
the history behind that prediction, r + 1 tokens. The last scored position of every window is its last token, so a
window's length is its largest `context` + 1. `top1_<arm>` is 1 when the arm's most likely token is the reference's
(ties to the lower id). KL and NLL are in nats. Arms: V1, V1r (two vLLM fork runs, one launch), V2 (a second launch,
follow-up F3), C1 (CuteAFD as shipped), C0 (CuteAFD on K3.25-v1, P-B only). CuteAFD repeats are byte-identical to C1
and are not repeated here.

KL is not comparable across panels, and NLL is per tokenizer and per text.

## `pb-rows.csv`: panel P-B (64 windows, 32,768 positions)

tpurtell's `cuteafd-fidelity` panel, config `glm5_flash-v2_20261005_bf16root`. Every window's last 512 positions;
15,104 of them are generated text (`role` = `gen`, the panel's primary rows), the others
context (`ctx`). `block` and `bucket` are the panel's own labels (`bucket` labels the window, so a 0-2K window can have
positions past 2,048).

| Column | Meaning |
|---|---|
| `window`, `block`, `bucket`, `role` | the panel's window id and labels |
| `row`, `context` | see above (`context` = the panel's predicted position) |
| `ref_nll` | the reference's NLL of the actual next token (from the panel's `next_token_log_prob`) |
| `ref_confident` | 1 when the reference's top probability is at least 0.5 |
| `kl_<arm>` | coarse KL(reference ‖ arm) over the reference's top 1,024 ids plus one tail bin (tpurtell's rule; a lower bound on full-vocabulary KL) |
| `nll_<arm>` | the arm's NLL of the actual next token |
| `top1_<arm>` | top-1 agreement with the reference |

Derived from `wrldsuksgo2mars/cuteafd-fidelity` @ `a7e7d1b4`, MIT licence, Copyright (c) 2026 T.J. Purtell
(https://huggingface.co/datasets/wrldsuksgo2mars/cuteafd-fidelity). The scores are released under CC BY 4.0
with that attribution, except the `ref_nll` and `ref_confident` columns, which restate values from the panel and
remain under its MIT licence (Copyright (c) 2026 T.J. Purtell).

## `q2-rows.csv`: Q2 (18 windows, 73,728 positions)

Six human-written documents (three PG-19 books, three Apache-2.0 vLLM source files) at 32K, 64K and 128K tokens; the
last 4,096 positions of each window. No reference: the KL columns measure disagreement between two engines, not
distance from BF16.

| Column | Meaning |
|---|---|
| `window`, `doc_type`, `length` | window id, prose or code, 32K / 64K / 128K |
| `row`, `context` | see above |
| `nll_C1`, `nll_V1` | each engine's NLL of the actual next token |
| `kl_C1_V1` | full-vocabulary KL(C1 ‖ V1), the direction of the published Q2 figure (the reverse direction is in `../q2/q2-C1-vs-V1.json` as `kl_ba`, by window) |
| `top1_C1_V1` | 1 when both engines' most likely token is the same |
| `kl_V1_V1r`, `top1_V1_V1r` | the same between two vLLM runs (the within-engine floor); empty where that window was not repeated |

## `pa-rows.csv`: panel P-A (25 windows, 51,175 positions)

brandonmusic's BF16 teacher panel: every position of each 2,048-token window (rows 0-2046), so the history behind a
scored token runs from 1 to 2,047 tokens. Columns: `window`, `domain`, `row`, `context`, `teacher_nll`,
`teacher_confident` (teacher top probability at least 0.5), and per arm (V1, V1r, V2, C1) `kl_<arm>`
(full-vocabulary KL(teacher ‖ arm), float64 before rounding), `nll_<arm>`, `top1_<arm>`.

**P-A's file is not in this repository.** The teacher dataset's card gives its licence as "other" and does not state terms for redistributing values derived per position, so only summaries computed against it are published (`../pa/`, `../tails/pa-tails.json`). `pa-tails.json` records the sha256 of the file it was computed from (fd188e513b658e8e…), so a copy can be checked if it is released later.
