#!/usr/bin/env python3
"""Write stage0/prompts/MANIFEST.json: SHA256 of every file under stage0/prompts (except MANIFEST.json itself) and
stage0/drivers, plus the build rules and seeds (RULES.json, embedded). Standard library only; run on the host:
    python3 prompts/build/make_manifest.py
Re-run after any change; a frozen protocol records MANIFEST.json's own SHA256.
"""
import hashlib
import json
import time
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent
STAGE0 = PROMPTS.parent
SKIP_DIRS = {"__pycache__"}


def files(root):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (SKIP_DIRS & set(p.parts)) and p.name != "MANIFEST.json":
            yield p


def main():
    rules = json.loads((PROMPTS / "RULES.json").read_text())
    entries = {}
    for root in (PROMPTS, STAGE0 / "drivers"):
        for p in files(root):
            entries[p.relative_to(STAGE0).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    groups = {
        "q2_windows": sorted(k for k in entries if k.startswith("prompts/q2/")),
        "T_prompts": sorted(k for k in entries if k.startswith("prompts/T/")),
        "L_prompts": sorted(k for k in entries if k.startswith("prompts/L/") and "/code/" not in k),
        "L_code_specs_tests_references": sorted(k for k in entries if k.startswith("prompts/L/code/")),
        "authored": sorted(k for k in entries if k.startswith("prompts/authored/")),
        "checkers": sorted(k for k in entries if k.startswith("prompts/checkers/")),
        "selftest": sorted(k for k in entries if k.startswith("prompts/selftest/")),
        "build": sorted(k for k in entries if k.startswith("prompts/build/")),
        "drivers": sorted(k for k in entries if k.startswith("drivers/")),
    }
    man = {"about": "Stage 0 manifest for the CuteAFD v3.0.1 vs vLLM v0.9.2 comparison (Blocks Q2, T, L). Paths are "
                    "relative to <run>/stage0.",
           "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "n_files": len(entries),
           "rules": rules["rules"], "seeds": rules["seeds"], "constants": rules["constants"],
           "sources": rules["sources"], "selection": rules["selection"],
           "driver_seed_schemes": {
               "block_t": "measured 730,000,000 + rep*10^7 + length_idx*10^6 + content_idx*10^5 + level_idx*10^4 + "
                          "stream; warm-up 739,000,000 + stream; cached cell 738,000,000 + i",
               "block_l": "740,000,000 + stage_idx*10^6 + content_idx*10^5 + prompt*10^3 + rep (L1=0, L2=1, L3=2, "
                          "L3s=3 with rep 9)",
               "nonce": "4 x NONCE_GROUPS[int(sha256(f'{salt}:{seed}:{k}'), 16) % len], salt = label + start time"},
           "groups": groups, "files": entries}
    out = PROMPTS / "MANIFEST.json"
    out.write_text(json.dumps(man, indent=1) + "\n")
    print(out, len(entries), "files; sha256", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
