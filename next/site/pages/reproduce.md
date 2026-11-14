# Reproduce

Each study publishes how to reproduce it. The first two studies (K3.25 and K4, CuteAFD v3.0.1 against the vLLM fork)
share the procedure below; every later run's `README.md` has its own section on reproducing it, and
[runs.json](runs.json) lists every file each goal produced.

| Study | Where its procedure is |
|---|---|
| K3.25 and K4 engine comparisons | below ([repro/REPRODUCE.md](https://github.com/UrbanAstroLA/cuteafd-eval/blob/main/repro/REPRODUCE.md)) |
| Every other run | its own `README.md` in [results/](https://github.com/UrbanAstroLA/cuteafd-eval/tree/main/results), section on reproducing |
| Every finding | `python3 next/tools/build.py --check` re-reads each finding's value from its file and refuses a number that does not trace |

{{include repro/REPRODUCE.md}}
