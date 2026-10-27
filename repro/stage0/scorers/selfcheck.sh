#!/bin/bash
# Stage 0 CPU checks for the scorers. No GPU, no server, no container start/stop
# (test_cuteafd_compare.py runs the CuteAFD image's `bench fidelity compare` with --network none).
# Each step's exit code is checked explicitly.
cd "$(dirname "$0")" || exit 1
PY=<venv>/bin/python
rc=0
$PY -B -W ignore tests/test_scorers.py || { echo "unit tests FAILED"; rc=1; }
$PY -B -W ignore tests/test_cuteafd_compare.py || { echo "cuteafd compare cross-check FAILED"; rc=1; }
$PY -B plans.py --out plans --panels pa,pb || { echo "plans FAILED"; rc=1; }
# P-A on real data: the teacher as its own engine (KL must be 0, NLL = teacher NLL), and the
# v0.8.0 K3.25 capture re-scored (must reproduce <runs>/kld/...+v0.8.0/kld.json).
$PY -B score_pa.py score \
  --arm teacher=<datasets>/glm53-flash-teacher-logits/logits \
  --arm k325v080="<runs>/kld/glm53-flash-exl3-k3.25@tpurtell+v0.8.0/candidate-logits" \
  --pair teacher,k325v080 --out selfcheck/pa --jobs 8 || { echo "P-A self-check FAILED"; rc=1; }
exit $rc
