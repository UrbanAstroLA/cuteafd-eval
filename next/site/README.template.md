# cuteafd-eval

Maintained by Michael M: [UrbanAstroLA](https://github.com/UrbanAstroLA) on GitHub, [@UrbanAstroFella](https://x.com/UrbanAstroFella) on X.

Measurements of two inference engines by the same author, **CuteAFD** ([tpurtell/cuteafd](https://github.com/tpurtell/cuteafd))
and **tpurtell's vLLM fork** ([tpurtell/glm-5.3-flash-ext3-2x-rtx](https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx)),
and of several quantized checkpoints of **GLM-5.3-Flash**, on one machine: two RTX PRO 6000 Blackwell Max-Q GPUs at
300 W. The aim is evidence for choosing a deployment: what each engine and each precision cut costs or buys in distance
from the BF16 model, task accuracy at long context, thinking length, speed and memory. Nothing here is a recommendation.

**Site:** <{{site}}> · **For agents:** [`docs/findings.json`](docs/findings.json),
[`docs/runs.json`](docs/runs.json), [`docs/llms.txt`](docs/llms.txt)

## How results are stated

Every result is a **finding**: one measured quantity with its sign convention, unit, n, interval, scope (engine and
version, checkpoint, items, context, path, hardware), whether it was planned or found after looking, and a pointer into
the file it was read from. **Judgements across studies** cite their findings, carry a strength and say what they do
not show:

- *established*: pre-set rules agree on two or more independent item sets, launches or engines;
- *supported*: a pre-set rule on one item set, not contradicted;
- *indicated*: found after looking, or exploratory;
- *open*: the evidence is mixed or missing.

An interval that includes 0 is reported as *not detected*, with the largest effect it does not exclude.

## Answers so far

{{answers-md}}

## Studies

Kind, from each run's RUN.json: *measurement* (a frozen protocol), *exploratory* (criteria fixed before computing, but not a full protocol), *check* (source reading or CPU checks).

{{runs-md}}

## Checking the numbers

`python3 next/tools/build.py --check` re-reads every finding's value from its file, refuses any number in a finding,
judgement or page that does not trace to the data, and checks that every published file under `results/` belongs to
exactly one goal of the run index. Corrections made when the site was rebuilt are listed on the
[audit page]({{site}}audit.html#corrections).

## Layout

```
results/<date>-<run>/   one folder per run: RUN.json, README.md, MANIFEST.json, summaries, receipts (frozen)
protocol/               the first comparison's frozen protocol, amendments, follow-ups and sources
repro/                  REPRODUCE.md, drivers, scorers, launch files, the local loader modification of the vLLM fork
next/site/              run index, findings, judgements and page text: the source of the site
next/tools/             build.py (checks and site), check_runs.py, tables.py
docs/                   the site, built from next/site
```

Published copies replace local paths with placeholders such as `<run>/` and `<hf-hub>/`. No logit dumps, token ids
or generated reply texts are published.

## Licences

Code: Apache-2.0 (`LICENSE`). Results and documentation: CC BY 4.0 (`LICENSE-DATA.md`). Third-party material is
attributed in [`NOTICE.md`](NOTICE.md) and stays under its own licence. Cite with [`CITATION.cff`](CITATION.cff).
