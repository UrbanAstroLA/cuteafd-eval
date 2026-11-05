"""Shared definitions for the CuteAFD v4.0.0 engine rerun (2026-10-30). Copied from the K4 three-engine comparison
(2026-10-27); the declared edits are listed in ../PROTOCOL.md section D (paths, engine table, input check for three
checkpoints). Salts and seeds are unchanged, so every request equals the 2026-10-27 run's. Standard library only.

Reuses, read-only, the K3.25 comparison's Stage 0 (prompt sets, client, Block T/L helpers) and the K4 discovery's
top-20 definitions. Nothing here writes into those folders: bytecode writing is switched off before they are imported.

Arms:  V   tpurtell vLLM fork v0.9.2 (image ea0430aa), recipes glm53-flash-exl3-{k3.25,k4}@tpurtell+v0.9.2
       C   tpurtell CuteAFD v4.0.0 (image e257bc61), stack <stacks>/cuteafd-v4, configs local/*.config
       C3  tpurtell CuteAFD v3.0.1 (image 392db7c0), Block Q relaunch only (version contrast on today's stack)
Checkpoints: K3.25 (V: K3.25-v1 0490d2f7; C/C3: K3.25-Core-FP8 d31ebc92, same expert bytes), K4 (tr3-4bpw
a5fee929), K4-Core-K6 (5d3fffe1, C only). One engine at a time on 127.0.0.1:8001.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the reused K3.25 / discovery folders

RUN = Path("<runs>/2026-10-30-cuteafd-v4")
K325 = Path("<run>")
STAGE0 = K325 / "stage0"
DRIVERS0 = STAGE0 / "drivers"
PROMPTS = STAGE0 / "prompts"
PLANS = STAGE0 / "scorers" / "plans"
DISC = Path("<k4-discovery>")
GRID = RUN / "GRID.json"
FROZEN = RUN / "FROZEN.json"
BASE_URL = "http://127.0.0.1:8001"

MODEL_ID = "brandonmusic/GLM-5.3-Flash-tr3-4bpw"
MODEL_REVISION = "a5fee929cf4888b1824323e33e8a19b60129e025"
K4_SNAPSHOT = Path("<hf-hub>/models--brandonmusic--GLM-5.3-Flash-tr3-4bpw/snapshots") / MODEL_REVISION
K325_SNAPSHOT = Path("<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K3.25-v1/snapshots/"
                     "0490d2f708b12145f6516555ab066aaeb401cd21")
SNAPSHOTS = {  # every checkpoint served in this run; all must carry the shared tokenizer
    "K3.25-v1": K325_SNAPSHOT,
    "K3.25-Core-FP8": Path("<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K3.25-Core-FP8/snapshots/"
                           "d31ebc921f1f098b4a56d37aaccb3cdef4096184"),
    "K4": K4_SNAPSHOT,
    "K4-Core-K6": Path("<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K4-Core-K6/snapshots/"
                       "5d3fffe1df9c4a109bbbdafb60dc19df9fac019d"),
}
TOKENIZER_SHA256 = "19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d"  # K4 == K3.25-v1
K325_FROZEN_SHA256 = {  # from <run>/FROZEN.json (reused inputs only)
    "stage0/prompts/MANIFEST.json": "1622039cc2be0af8e97b8f3411aba8fe77acb99bb9573541ed2a77db7755c24b",
    "stage0/drivers/block_t.py": "9497d75bbff4ee2006f6e8efc15bbd2b9fca5e4701ac688613b9717b53dab3e7",
    "stage0/drivers/block_l.py": "efc4754d0133b06557cf7f0e4ec8a3eda8378c538257f653b073ffde84ba8b15",
    "stage0/drivers/analyze_l.py": "0ba724d18fe0f26b1933ac05558478dfb2c5b6b114c0803a425ef5871bfc5ada",
    "stage0/scorers/score_pb.py": "2aabc8ea04bf4983baa41e9c7af00a55a18268020edf0d15c309ef53657830e2",
    "stage0/scorers/plans/pa.cuteafd-plan.json": "c7977da1530072eee26600890da0d36cb07988270d867cc91a35e7cd0d5d7165",
    "stage0/scorers/plans/q2.cuteafd-plan.json": "6d3ad9770a1cc5247f2505109a2e7b4f9d47a2383234c83676368b4492bbe25d",
}
# client.py was not in the K3.25 FROZEN.json; its hash is recorded in every K3.25 receipt (232f9668...)
K325_CLIENT_SHA256_PREFIX = "232f9668"

# ---- request settings, identical on every engine (PROTOCOL.md "Request settings") ----
TEMPERATURE = 1.0
TOP_P = 0.95
TOP_K = -1                    # "off" on all three engines
THINKING = True               # chat_template_kwargs.enable_thinking (no template has an off switch)
NONCE_SALT = {"T": "K4-3E-2026-10-27:T", "T-drift": "K4-3E-2026-10-27:T-drift",
              "L": "K4-3E-2026-10-27:L", "S": "K4-3E-2026-10-27:S", "startup": "K4-3E-2026-10-27:startup"}
SEED_BASE = {"T": 730_000_000,       # block_t.py scheme, unchanged
             "T-drift": 760_000_000, # = T seed + 30,000,000 (repeats of a cell use distinct seeds)
             "L": 840_000_000,       # moved from K3.25's 740M so no K4 seed collides with a Block T seed
             "S": 790_000_000, "startup": 791_000_000, "Q": 792_000_000}
TOP20_K = 20

ENGINES = {  # start/stop commands live in ../chain-k4.sh only (one source); these are what the drivers need
    "V": {"name": "vLLM fork v0.9.2 (tpurtell, image ea0430aa)", "container": "glm53-flash-exl3-b12x-vllm",
          "ready_regex": r"container is ready", "top20_route": "completions", "key": False},
    "C": {"name": "CuteAFD v4.0.0 (tpurtell, image e257bc61)", "container": "cuteafd-coordinator-local-v4",
          "ready_regex": r"API ready at", "top20_route": "probe", "key": True},
    "C3": {"name": "CuteAFD v3.0.1 (tpurtell, image 392db7c0)", "container": "cuteafd-coordinator",
           "ready_regex": r"API ready at", "top20_route": "probe", "key": True},
}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_atomic(path, obj) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def import_stage0():
    """The K3.25 client, block_t and block_l modules (read-only, no bytecode), after checking their hashes."""
    for rel in ("stage0/drivers/block_t.py", "stage0/drivers/block_l.py"):
        got = sha256_file(K325 / rel)
        if got != K325_FROZEN_SHA256[rel]:
            sys.exit(f"reused file changed since the K3.25 freeze: {rel} {got}")
    if not sha256_file(DRIVERS0 / "client.py").startswith(K325_CLIENT_SHA256_PREFIX):
        sys.exit("reused client.py differs from the one the K3.25 receipts recorded")
    if str(DRIVERS0) not in sys.path:
        sys.path.insert(0, str(DRIVERS0))
    import client  # noqa: E402
    import block_t  # noqa: E402
    import block_l  # noqa: E402
    return client, block_t, block_l


def verify_inputs(verbose=False) -> dict:
    """Checks the carried-over inputs: K4 tokenizer == K3.25's, the K3.25 manifest and every prompt file in it,
    the plan files. Returns a report; raises SystemExit on any mismatch."""
    rep = {"checked_at": now(), "files": {}}
    rep["tokenizer_sha256"] = {k: sha256_file(p / "tokenizer.json") for k, p in SNAPSHOTS.items()}
    if set(rep["tokenizer_sha256"].values()) != {TOKENIZER_SHA256}:
        sys.exit(f"tokenizer differs: {rep['tokenizer_sha256']}")
    for rel, want in K325_FROZEN_SHA256.items():
        got = sha256_file(K325 / rel)
        rep["files"][rel] = got
        if got != want:
            sys.exit(f"reused file changed since the K3.25 freeze: {rel}")
    man = json.loads((PROMPTS / "MANIFEST.json").read_text())
    bad = []
    # block_t.py / block_l.py were amended (A2, thinking on) after MANIFEST.json was written; FROZEN.json holds
    # their frozen hashes, checked above, so the manifest's older driver hashes are not used.
    superseded = {"drivers/block_t.py", "drivers/block_l.py"}
    rep["manifest_entries_superseded_by_FROZEN"] = sorted(superseded)
    for rel, want in man["files"].items():
        if rel in superseded:
            continue
        if sha256_file(STAGE0 / rel) != want:
            bad.append(rel)
    rep["manifest_files_checked"] = len(man["files"])
    if bad:
        sys.exit(f"{len(bad)} manifest files differ, e.g. {bad[:3]}")
    if man["sources"]["tokenizer_json_sha256"] != TOKENIZER_SHA256:
        sys.exit("manifest tokenizer hash differs from the K4 tokenizer")
    if verbose:
        print(json.dumps(rep, indent=1))
    return rep


def load_grid(require_filled=True) -> dict:
    g = json.loads(GRID.read_text())
    if require_filled and g.get("status") != "FILLED":
        sys.exit("GRID.json is not filled: run grid_rule.py after Stage 1, then freeze.py")
    return g


def require_frozen(files) -> dict:
    """Comparison blocks run only after the freeze, with every listed file unchanged since it."""
    if not FROZEN.exists():
        sys.exit("FROZEN.json missing: comparison requests are not allowed before the freeze (PROTOCOL.md F)")
    fz = json.loads(FROZEN.read_text())
    for f in [GRID, *map(Path, files)]:
        key = str(Path(f).resolve())
        want = fz["sha256"].get(key)
        if want is None or sha256_file(f) != want:
            sys.exit(f"{f} is not in FROZEN.json or changed since the freeze")
    return fz


def read_key(path):
    if not path:
        return None
    return Path(path).read_text().strip() or None


def headers(key):
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def chat_body(model, messages, max_tokens, seed, stream=True):
    """The one chat request shape every arm receives (sampling sent explicitly: CuteAFD is greedy without it)."""
    body = {"model": model, "messages": messages, "max_tokens": int(max_tokens), "temperature": TEMPERATURE,
            "top_p": TOP_P, "top_k": TOP_K, "seed": int(seed), "stream": stream,
            "chat_template_kwargs": {"enable_thinking": THINKING}}
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def lcm(a, b):
    from math import gcd
    return a * b // gcd(a, b)
