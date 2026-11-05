#!/usr/bin/env python3
"""Write FROZEN.json: sha256 of every file the core-swap protocol names. Run once, at the freeze."""
import glob, hashlib, json, os, time
R = "<cs-run>"; C = "<stacks>/cuteafd-v4/local"
SNAP = "<hf-hub>/models--derived--GLM-5.3-Flash-EXL3-K4-Core-K6-BF16core/snapshots/049c0180c693ebbad90190dca8d5f0a7ca4d3753"
files = [f"{R}/PROTOCOL.md", f"{R}/chain-cs.sh", *sorted(glob.glob(f"{R}/drivers/*.py")), f"{R}/analysis/analyze_s1.py",
         f"{R}/prep/build_derived.py", f"{R}/prep/hash_core.py", f"{R}/prep/core-hash.json", f"{R}/prep/derived-manifest.json",
         *[f"{C}/glm53-flash-exl3-{n}-2rtx{s}.config" for n in ("k4", "k4-core-k6", "k4-core-k6-bf16core") for s in ("", "-score")],
         f"{SNAP}/config.json", f"{SNAP}/quantize_config.json", f"{SNAP}/model.safetensors.index.json",
         "<tl-run>/analysis/score_stop.py",
         "<tl-run>/capture/plugin/glm53_capture_plugin/core.py",
         "<runs>/2026-10-30-cuteafd-v4/drivers/block_l3.py", "<runs>/2026-10-30-cuteafd-v4/drivers/k4common.py",
         "<run>/stage0/drivers/analyze_l.py",
         *sorted(glob.glob("<tl-run>/traces/reg/tr/*.json")),
         *sorted(glob.glob("<tl-run>/traces/reg/on/*.json"))]
sha = {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
json.dump({"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "note": "core swap on CuteAFD; see PROTOCOL.md", "sha256": sha},
          open(f"{R}/FROZEN.json", "x"), indent=1)
print(len(sha), "files frozen")
