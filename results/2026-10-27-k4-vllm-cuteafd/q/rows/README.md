# K4 Block Q per-position scores

One row per scored position, one column set per arm, from the K4 Block Q captures (the engines' own top-20 responses,
scored by the frozen K4 scorers). No token ids, logits or texts: each value is a number computed at that position,
rounded to 7 significant digits. Tail and position statistics computed from these files: `../tails/`
(`python3 tools/kl_tails.py --run k4`; `--check` reproduces them, and `tools/verify.py` runs that check).

**These are top-20 measures, not full-vocabulary KL.** Do not compare them with the K3.25 run's `q/rows/` files as the
same quantity: on P-A, KL20 reads about 0.8 of full-vocabulary KL; on P-B generated rows, KL_pb20 keeps about 98-99% of
the published coarse KL (`../../METHOD.md`, Calibration). NLL and top-1 are exact under top-20. KL is not comparable
across panels, and NLL is per tokenizer and per text.

Conventions as in the K3.25 run: `row` r is the distribution after tokens 0..r, which predicts token r+1; `context` is
the history behind that prediction, r + 1 tokens. `top1_<arm>` is 1 when the arm's most likely token is the
reference's (P-A, P-B) or when both arms' most likely tokens agree (Q2). Arms: `Vr1` and `Vr1b` (vLLM launch 1, P-B
repeated on that launch), `Vr2` (vLLM launch 2), `Cr1` (CuteAFD; its repeat C-r1b is byte-identical and not repeated).
The published headline pairs CuteAFD against the per-row mean of `Vr1` and `Vr2`.

## `pa-rows.csv`: panel P-A (25 windows, 51,175 positions)

brandonmusic's BF16 teacher panel, every position of each 2,048-token window (rows 0-2046). Columns: `window`, `domain`,
`row`, `context`, `teacher_nll`, `teacher_confident` (teacher top probability at least 0.5), and per arm (Vr1, Vr2,
Cr1) `kl20_<arm>` (KL20: KL(teacher ‖ arm) on the arm's 20 ids plus the actual token plus one rest cell), `nll_<arm>`,
`top1_<arm>`.

The teacher logits are brandonmusic's, from
[`brandonmusic/GLM-5.3-Flash-ShapleyMCG-K4-Evidence`](https://huggingface.co/datasets/brandonmusic/GLM-5.3-Flash-ShapleyMCG-K4-Evidence)
@ `32afb887` (BF16 teacher of `zai-org/GLM-5.3-Flash-BF16`; that repository states no licence); window identity and
hashes as in the K3.25 run's `q/pa/PROVENANCE.json`. The file holds scores only, no logits and no token ids. Our KL,
NLL and top-1 columns are CC BY 4.0; `teacher_nll` and `teacher_confident` are derived from brandonmusic's teacher
logits and are credited to him.

## `pb-rows.csv`: panel P-B (64 windows, 32,768 positions)

tpurtell's `cuteafd-fidelity` panel, config `glm5_flash-v2_20261005_bf16root`: every window's last 512 positions;
15,104 of them are generated text (`role` = `gen`, the panel's primary rows).
`window`, `block`, `bucket`, `role`, `row`, `context`, `ref_nll` and `ref_confident` are the same panel values as in the
K3.25 run's `pb-rows.csv` (rows matched one to one). Per arm (Vr1, Vr1b, Vr2, Cr1): `klpb20_<arm>` (KL_pb20, the
top-20 truncation of tpurtell's top-1,024-plus-tail rule), `nll_<arm>`, `top1_<arm>`.

Derived from `wrldsuksgo2mars/cuteafd-fidelity` @ `a7e7d1b4`, MIT licence, Copyright (c) 2026 T.J. Purtell
(https://huggingface.co/datasets/wrldsuksgo2mars/cuteafd-fidelity). The scores are released under CC BY 4.0 with that
attribution, except the `ref_nll` and `ref_confident` columns, which restate values from the panel and remain under its
MIT licence (Copyright (c) 2026 T.J. Purtell).

## `q2-rows.csv`: Q2 (18 windows, 73,728 positions)

Six human-written documents (three PG-19 books, three Apache-2.0 vLLM source files) at 32K, 64K and 128K tokens; the
last 4,096 positions of each window. No reference: the KL columns measure disagreement between two runs, not distance
from BF16.

| Column | Meaning |
|---|---|
| `window`, `doc_type`, `length` | window id, prose or code, 32K / 64K / 128K |
| `nll_Vr1`, `nll_Vr2`, `nll_Cr1` | each run's NLL of the actual next token |
| `kl20n_Vr1_Cr1`, `kl20n_Vr2_Cr1` | KL20n(vLLM launch ‖ CuteAFD): the top-20 intersection cells plus rest, the frozen Q2 scorer's `kl20_xy` per row |
| `top1_Vr1_Cr1`, `top1_Vr2_Cr1` | 1 when both runs' most likely token is the same |
| `kl20n_Vr1_Vr2`, `top1_Vr1_Vr2` | the same between the two vLLM launches (the within-engine floor) |

The frozen Q2 scorer writes window and document means only; these per-row values apply its own definitions to the same
captures (`../q2_rows.py`), and the export checks that their window means equal the scorer's.
