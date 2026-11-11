#!/bin/bash
# Turn check, one arm (PROTOCOL-DRAFT.md section 4). Called by chain.sh turncheck with the arm already up in turn
# form (prefix cache on, bench route on); output goes to stdout, which the chain appends to logs/turncheck-<arm>.log. No `set -e`: every conversation is attempted and its exit code logged.
# 12 conversations: 3 families x {16k, 64k} x {single + follow-up, 8 parts}. Pilot items (exploratory set).
arm="$1"; tag="${2:-r0}"
R=<runs>/2026-11-10-context-probe
PY=<runs>/2026-10-27-long-context-pilot2/.venv/bin/python
say() { echo "$(date -Is) $*"; }
cd "$R/drivers" || exit 1
for len in 16k 64k; do
  for fam in ledger join trace; do
    for mode in single turns; do
      extra=(); [ "$mode" = turns ] && extra=(--parts 8)
      "$PY" -B turn_check.py run --arm "$arm" --run-tag "$tag" --item "$fam-000-$len" --mode "$mode" "${extra[@]}" \
        --max-tokens 16384 --dump-root "$R/turncheck/dumps"
      say "$arm $fam-000-$len $mode rc $?"
    done
  done
done
"$PY" -B turn_check.py report --arm "$arm" --run-tag "$tag"; say "report rc $?"
# Repeat check (PROTOCOL-DRAFT.md section 4a), same launch: one greedy 16K prompt, 4 times alone then 256 times at
# concurrency 8; are the outputs the same text? About 10 min.
"$PY" -B repeat_check.py run --arm "$arm" --run-tag "$tag" --api-key-file <secrets>/bench-api-key
say "$arm repeat check rc $?"
