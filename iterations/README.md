# Iterations

How a new iteration enters this repository: a new engine version (for example CuteAFD v3.1 or the vLLM fork's next
release), a new arm (another checkpoint, a configuration switch), or a labelled follow-up. Four steps, always in this
order: **freeze a protocol delta → run → export → verify.**

## 1. Freeze a protocol delta

Copy `TEMPLATE/` to `iterations/<date>-<name>/` and fill in `PROTOCOL-DELTA.md` before the first GPU request:

- what changes against `protocol/PROTOCOL.md` (v2 + A1-A2), and nothing else: the arm, its engine, image digest,
  checkpoint revision and launch config; the blocks it runs (Q, Q2, T, L or a subset); any instrument change;
- the comparison it is meant for, and the reading rule, stated before any result exists;
- the noise floor: the within-arm repeat it will be read against;
- the arm label: a new letter-number pair (`C2`, `V2`, …); never reuse a label for a different build.

Then record the sha256 of the delta and of every driver, scorer and prompt index it uses in its `FROZEN.json`. Changes
after the freeze are dated amendments appended to the delta, never edits.

An iteration that only explores (a quick probe, a single pass, a shortcut) is still recorded, but as **exploratory**: it
gets no freeze, and its results are never placed in a table with measured ones.

## 2. Run

- Nothing else on the GPUs; record the `nvidia-smi` snapshot the drivers take.
- Use the published drivers unchanged (their hashes are checked against the delta), a fresh `--label`, and a distinct
  seed per request (the drivers do this).
- Keep every receipt, including failed and stopped requests. A cell that cannot run is reported as such.

## 3. Export

Create `results/<date>-<run>/` with:

- `RUN.json`: `id`, `kind` (`measurement` only if run under a frozen protocol or delta; otherwise `exploratory`; `check`
  for deterministic checks), `title`, the arms with engine, image digest and checkpoint revision, and `slots` (each
  `done` with its files, or `pending`);
- `README.md`: results first, direction and size before significance; runs that are not measurements open with a banner
  naming their kind;
- the per-block summaries and receipts: small JSON and markdown only, no logit dumps, per-row files or generated texts;
- paths replaced by placeholders (`<run>/`, `<datasets>/`, …).

Then add a dated line to the ledger in `tools/README.template.md`, and rebuild:

```bash
python3 tools/build_readme.py
python3 tools/build_site.py
```

Once published, a result later found to be confounded keeps its folder: its `kind` becomes `withdrawn`, its README opens
with a banner saying why and what replaced it, and the ledger gets a dated line.

## 4. Verify

```bash
python3 tools/verify.py
```

It must print `OK`. It checks every manifest hash, every published copy against its recorded hash, the kind labels and
banners, that the README's results section cites measurement runs only, and scans every file for local paths, names,
addresses, credentials and other content that must not be published. Write the manifests last
(`results/<run>/MANIFEST.json`, then the top-level `MANIFEST.json`), after every other file is final.

## Comparability

A comparison table lines up arms that share the protocol (or a frozen delta of it), the hardware and the model family.
Fixtures are not comparable across model families, and NLL is per tokenizer; say so wherever such numbers appear
together. Single-pass NLL varies by about ±0.002 on a non-deterministic engine: score every candidate at least twice.
