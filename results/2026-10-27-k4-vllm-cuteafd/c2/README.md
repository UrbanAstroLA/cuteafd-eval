# Q2 document c2 on K4: a window where vLLM also differs from itself

CPU-only reading of the K4 Block Q captures (top-20 rows), arms V-r1 and V-r2 (two vLLM launches) and C-r1
(CuteAFD). Document c2 is a concatenation of vLLM's own Python source. Its three Q2 windows are prefixes of one token
stream (c2-032k = tokens 0-32K, c2-064k = 0-64K, c2-128k = 0-128K), and each scores its last 4,096 rows.

| Window (scored rows) | NLL, V-r1 | Top-20 entropy, V-r1 | Rows with \|ΔNLL\| > 1 nat: V-r1 vs V-r2 | V-r1 vs C-r1 | V-r2 vs C-r1 |
|---|---|---|---|---|---|
| c2-032k (28,671-32,766) | 0.448 | 0.313 | 9 | 34 | 29 |
| **c2-064k (61,439-65,534)** | **1.013** | 0.463 | **192** | 292 | 298 |
| c2-128k (126,975-131,070) | 0.611 | 0.334 | 70 | 67 | 90 |
| c0-064k (code control) | 0.508 | 0.344 | 8 | 25 | 23 |
| c1-064k (code control) | 0.586 | 0.416 | 9 | 15 | 14 |
| pg28988-064k (prose control) | 1.804 | 1.336 | 0 | 1 | 3 |

KL20n per window (the frozen Q2 scorer's engine-against-engine form) on c2-064k: vLLM against its second launch
0.094, vLLM against CuteAFD 0.148 and 0.168 (one value per vLLM launch). On the other 17 windows the same pairs read
0.003-0.039 (vLLM against vLLM) and 0.005-0.066 (vLLM against CuteAFD).

What the rows show:

1. **On c2-064k the two vLLM launches disagree with each other on 192 rows by more than 1 nat.** vLLM's
   run-to-run variation alone produces nat-scale changes there; CuteAFD's count against either launch (292, 298) is
   of the same order. The K3.25 run had no vLLM repeat of c2, and its audit recorded that this window "cannot be
   attributed to either engine". On K4 the window is sensitive for vLLM against itself as well.
2. **The sensitivity is specific to the document and the position.** It is small at 32K, largest at 61-65K and
   smaller again at 127-131K of the same stream; the c0, c1 and prose windows show 0-9 such rows between the vLLM
   launches. The text is ordinary code throughout (no long lines, runs, binary or non-ASCII stretches, scanned in
   4K-token blocks).
3. **Many of the volatile rows are confident ones.** Of the 192 vLLM-against-vLLM rows on c2-064k, 38 have one
   launch giving the actual token more than 0.9 probability; 20 are top-1/top-2 swaps between the launches. The
   window's NLL (1.01) is more than twice its top-20 entropy (0.46): the model is confident there and often does not
   predict the actual token.
4. **Long-range exact copying accounts for part of it.** Rows whose next token completes a 12-gram that also occurs
   more than 2,048 tokens earlier are about three times as volatile between the vLLM launches on c2-064k (14% against
   4.4%); c1-128k has 287 such rows and none of them is volatile.

Open question (not tested): whether near-duplicate code earlier in the stream, and which earlier variant the
sparse-attention indexer selects, accounts for the confident flips. Answering it needs per-layer indexer selections
from two launches.

The protocol reports `q2-code-c2-064k` separately and also gives the Q2 numbers without it (`../q/q2-top20.json`,
`without_outlier`). Files: `c2-summary.json` (the table and items 2-3, from `c2_summary.py`), `c2-rows.json` (per
window and pair: mean ΔNLL, rows above 1 nat by quarter of the window, the largest ΔNLL rows with their positions),
`copy-rows.json` (item 4).
