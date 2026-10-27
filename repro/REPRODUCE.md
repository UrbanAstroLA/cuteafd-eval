# Reproducing the comparison

Step by step, from the frozen protocol (`../protocol/PROTOCOL.md`) to the published summaries. Each step names the files
that carry the exact commands; this page puts them in order.

## Placeholders

The published copies replace local paths with placeholders. Substitute your own:

| Placeholder | Meaning |
|---|---|
| `<run>` | the run folder that receives receipts, captures and scores |
| `<runs>` | the parent folder of runs |
| `<datasets>` | where the prompt sources are downloaded (`../protocol/SOURCES.json`) |
| `<cuteafd>` | a checkout of tpurtell/cuteafd at v3.0.1; `<cuteafd>/local/` holds the configs from `cuteafd/configs/` |
| `<vllm-stack>` | a checkout of tpurtell/glm-5.3-flash-ext3-2x-rtx with its `start.sh`; `local-start.sh` / `local-env.sh` are thin local wrappers that export the settings below and call it |
| `<hf-home>`, `<hf-hub>` | the Hugging Face cache (`HF_HOME`) and its `hub/` folder |
| `<venv>` | a Python environment with numpy and scipy (scorers) |
| `<secrets>` | a directory, mode 0700, for CuteAFD's bench API key |
| `<kld>` | the earlier KL-divergence tooling the P-A scorer was cross-checked against (its `kld_score.py`); not needed to run the scorers here |
| `<recipes>` | where the local launch settings for an engine (an `env.sh` exporting the settings in step 3) are kept |
| `<cache>` | a cache directory for the engines' state |
| `<user>` | the account that runs the tools |
| `<tmp>`, `<data>` | a scratch directory; a generic data directory (also the mount point inside the prompt-build container) |

## 0. What you need

- Two GPUs of the RTX PRO 6000 Blackwell class (about 96 GB each), Docker with the NVIDIA container toolkit.
- About 300 GB for the checkpoints and images, and several hundred GB of scratch for the Block Q captures (full-vocabulary
  rows: about 160 GB per engine for P-A, P-B and Q2 with repeats).
- Python 3.10+ (drivers and checkers: standard library), and an environment with numpy and scipy for the scorers.
- Nothing else on the GPUs. `nvidia-smi --query-compute-apps` does not list every graphics client; check the full
  `nvidia-smi` output.

## 1. Checkpoints and images

Pin everything by revision and digest (values in `../README.md`, Setup):

```bash
huggingface-cli download wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-v1       --revision 0490d2f708b12145f6516555ab066aaeb401cd21
huggingface-cli download wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-Core-FP8 --revision d31ebc921f1f098b4a56d37aaccb3cdef4096184
huggingface-cli download incoai/GLM-5.3-Flash-DFlash2                      --revision bf582e4eacc1810f76656d1811693ff6c6737d2a
docker pull ghcr.io/tpurtell/cuteafd-coordinator:v3.0.1@sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a
docker pull ghcr.io/tpurtell/glm-5.3-flash-exl3-4bpw-2x-rtx@sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2
```

Optional checks of the checkpoint relation (CPU only): `../results/2026-10-26-cuteafd-setup-checks/` (`bytecheck.py`,
`fp8check.py`).

## 2. Prompt sources and the prompt set

1. Download each source in `../protocol/SOURCES.json` at its revision into `<datasets>/2026-10-26-engine-compare/`, and
   check every file against the sha256 listed there.
2. Build the prompt set (CPU only, about 11 minutes; runs in `--network none` containers):
   ```bash
   ./stage0/prompts/build/run_build.sh <scratch dir>
   python3 stage0/prompts/checkers/selftest.py
   python3 stage0/prompts/build/make_manifest.py
   ```
3. Compare the result with `stage0/prompts/MANIFEST.json`: every hash must match. The build is deterministic. The Block T
   contexts and Q2 windows are not published here (they are long excerpts of the sources); the manifest hashes confirm a
   rebuild. Rules, seeds and selections: `stage0/prompts/README.md`, `stage0/prompts/RULES.json`.

## 3. Serve vLLM (arm V1)

tpurtell/glm-5.3-flash-ext3-2x-rtx at v0.9.2, image by digest as above, served with `MODEL_PROFILE=k325` (K3.25-v1),
`GPU_MEMORY_UTILIZATION=0.95`, DFlash2 with 3 draft tokens, prefix caching in `align` mode, 16 sequences, listening on
`127.0.0.1:8001`. The settings are the release's; 0.95 instead of 0.97 is the only change, so that the server starts
beside a desktop session.

## 4. Serve CuteAFD (arms C1 and C0)

```bash
git clone https://github.com/tpurtell/cuteafd <cuteafd> && cd <cuteafd> && git checkout v3.0.1
git apply <this repo>/repro/cuteafd/patches/0001-coordinator-infiniband-guard.patch    # only if the host has no /dev/infiniband
mkdir -p local && cp <this repo>/repro/cuteafd/configs/*.config local/
HF_HOME=<hf-home> ./run.sh --config local/glm53-flash-exl3-k3.25-core-fp8-2rtx.config --dry-run
HF_HOME=<hf-home> ./run.sh --config local/glm53-flash-exl3-k3.25-core-fp8-2rtx.config --restart
```

- `glm53-flash-exl3-k3.25-core-fp8-2rtx.config`: serving (Blocks T and L).
- `…-core-fp8-2rtx-score.config` (C1) and `…-v1-2rtx-score.config` (C0): Block Q scoring launches; they add the bench
  endpoint, an API key file (`API_KEY_FILE=<secrets>/bench-api-key`; create it with `umask 077`, delete it afterwards),
  full prefill logits and a dump directory.
- `…-score-f1{a,b,c,d}.config`: follow-up F1 arms.
- `cuteafd/receipts/dry-run-*.log`: the plans the launcher resolved for the serving and scoring configs here, for
  comparison with yours.

## 5. Block Q: precision

Order: C1 twice, C0 once, then V1 twice. Exact commands are in the instrument READMEs:

- **CuteAFD, P-B**: tpurtell's own fidelity CLI, full tier, prefill score path, dataset revision `a7e7d1b4`; then the
  validation of our port against it (`stage0/scorers/README.md`, section 6, "P-B validation plan"). **P-A and Q2**: the
  engine's `glmf-teacher-kl.py` path through the bench endpoint, with the plans from `plans.py` (section 2).
- **vLLM, all panels**: restart the v0.9.2 server in capture mode with `stage0/capture-vllm/start-v092-capture.sh`, run
  `capture.py capture` per panel and pass, `capture.py verify`, then restore the normal server
  (`stage0/capture-vllm/README.md`, "Commands for the GPU stage").
- **Scoring**: `stage0/scorers/README.md`, section 9, "Commands after capture" (`score_pa.py`, `score_pb.py`,
  `score_q2.py`). Run `stage0/scorers/selfcheck.sh` first.

The published summaries are in `../results/2026-10-26-cuteafd-vs-vllm/q/`.

## 6. Block T: throughput

On each served engine in turn (vLLM first in this run), with nothing else on the GPUs:

```bash
python3 stage0/drivers/block_t.py --base-url http://127.0.0.1:8001 --label V1-r1 --out <run>/t/V1-r1-block-t.json
python3 stage0/drivers/block_t.py --base-url http://127.0.0.1:8001 --label C1-r1 --out <run>/t/C1-r1-block-t.json
python3 <this repo>/results/2026-10-26-cuteafd-vs-vllm/t/t_summary.py <run>/t/V1-r1-block-t.json <run>/t/C1-r1-block-t.json
```

The driver refuses to start if any prompt differs from `stage0/prompts/T/index.json`, inserts a per-request nonce so no
prompt is served from cache, records every request's seed, and writes no text. `--dry-run` prints the plan.

## 7. Block L: long output

One stage per invocation, checking the engine's logs and memory between stages:

```bash
python3 stage0/drivers/block_l.py --base-url http://127.0.0.1:8001 --label V1-r1 --out <run>/l/V1-r1-L1.json --stages L1
#   then --stages L2, L3 and L3s, each with its own --out
python3 stage0/drivers/analyze_l.py <run>/l/V1-r1-L1.json <run>/l/V1-r1-L2.json <run>/l/V1-r1-L3.json <run>/l/V1-r1-L3s.json --out <run>/l/V1-analysis.json
```

`analyze_l.py` re-tokenizes in a CPU-only container and runs each code reply's hidden tests in a `--network none`
sandbox (`stage0/drivers/README.md`).

## 8. Summaries and checks

Put the summaries into `results/<run>/` (local paths replaced by placeholders), then:

```bash
python3 tools/build_readme.py
python3 tools/build_site.py
python3 tools/verify.py
```

To add another engine version, arm or follow-up, see `../iterations/`.
