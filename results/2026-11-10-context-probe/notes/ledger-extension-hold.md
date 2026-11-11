# Ledger extension: held (2026-11-10)

Not run. It can be added after the base runs without loss, as a declared amendment (PROTOCOL.md section 13
already names it), provided these stay as they are:

- coordinator image `ghcr.io/tpurtell/cuteafd-coordinator:v5.0.0@sha256:6194637e…` (pinned by digest in the configs)
- the two model snapshots (Core-K6-HQA and the derived BF16core) and the arm settings in `chain.sh`
- `drivers/gen_tasks.py` and `tasklib.py` at the frozen hashes (new items: `ledger` indices 120-159, a new set
  folder with its own index and freeze; item and request seeds derive from the index, so nothing collides)
- cap 32,768, concurrency 8, same pass structure

Trigger, written before the measured data: run it if, on `ledger` at 64K or 127K, an arm's paired difference from
`anchor` has an interval that includes both zero and a loss of 0.10 or more in field score, or if the
dropped-record count (exploratory reading) differs between arms beyond the two-repeat floor. Arms equal on both:
not needed. Reading: the extension set is reported on its own and pooled with the base `ledger` items, and the
table says the extension was added after the base results were seen.
