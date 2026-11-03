#!/usr/bin/env python3
"""G0 CPU test of the swap switch: stream the records of one owner per group through dequant_weights with
LOCAL_EXL3_CORE_BF16_SET naming half the groups. Pass: swapped owners equal the BF16 file bit for bit; the others
equal reconstruct_bf16 (the route-b rebuild) bit for bit; unknown groups and a missing file raise."""
import glob, json, os, sys, types
os.environ["LOCAL_EXL3_DEQUANT_NONEXPERT"] = "bf16"; os.environ["LOCAL_EXL3_DEQUANT_DEVICE"] = "cpu"
sys.path.insert(0, "/g0")
import torch, exl3_core_dequant as M
from safetensors import safe_open
K6 = glob.glob("/k6/snapshots/*/")[0]
q = json.load(open(K6 + "quantize_config.json"))["tensor_storage"]; wmap = json.load(open(K6 + "model.safetensors.index.json"))["weight_map"]
pick = ["model.language_model.layers.0.self_attn.q_proj", "model.language_model.layers.0.self_attn.k_proj",
        "model.language_model.layers.0.self_attn.v_proj", "model.language_model.layers.0.self_attn.o_proj",
        "model.language_model.layers.3.self_attn.o_proj", "model.language_model.layers.3.self_attn.q_a_proj",
        "model.language_model.layers.3.self_attn.kv_a_proj_with_mqa", "model.language_model.layers.3.self_attn.q_b_proj",
        "model.language_model.layers.0.mlp.gate_proj", "model.language_model.layers.0.mlp.down_proj",
        "model.language_model.layers.5.mlp.shared_experts.up_proj", "model.language_model.layers.5.mlp.shared_experts.down_proj"]
qc = types.SimpleNamespace(dequant_storage={k: q[k] for k in pick}, _storage_entry=lambda owner, st: st.get(owner))
cfg = types.SimpleNamespace(num_hidden_layers=45)
def stream():
    for o in pick:
        for full in q[o]["stored_tensors"]:
            with safe_open(K6 + wmap[full], "pt") as f: yield full, f.get_tensor(full)
SET = {"kda_q", "kda_o", "mla_q_a", "mla_q_b", "dense_down", "shared_gate_up"}
os.environ["LOCAL_EXL3_CORE_BF16_FILE"] = "/core/core.safetensors"; os.environ["LOCAL_EXL3_CORE_BF16_SET"] = ",".join(sorted(SET))
mla = frozenset(i for i in range(45) if i % 4 == 3)
res = {}
with safe_open("/core/core.safetensors", "pt") as bf:
    for name, w in M.dequant_weights(stream(), qc, cfg, spec=False):
        o = name[:-len(".weight")]; g = M.swap_group(o, mla)
        if g in SET:
            ok = torch.equal(w, bf.get_tensor(name)); kind = "swapped"
        else:
            parts = {}
            for full in q[o]["stored_tensors"]:
                with safe_open(K6 + wmap[full], "pt") as f: parts[full.rsplit(".", 1)[1]] = f.get_tensor(full)
            ok = torch.equal(w, M.reconstruct_bf16(q[o], parts, o, device="cpu")); kind = "rebuilt"
        res[o] = (g, kind, ok); print(g, kind, ok, o, flush=True)
errs = {}
for env, val in (("LOCAL_EXL3_CORE_BF16_SET", "bogus"),):
    os.environ[env] = val
    try: list(M.dequant_weights(stream(), qc, cfg, spec=False)); errs[val] = "no error"
    except ValueError as e: errs[val] = "raised"
os.environ["LOCAL_EXL3_CORE_BF16_SET"] = "kda_q"; os.environ["LOCAL_EXL3_CORE_BF16_FILE"] = ""
try: list(M.dequant_weights(stream(), qc, cfg, spec=False)); errs["no file"] = "no error"
except ValueError: errs["no file"] = "raised"
ok = all(v[2] for v in res.values()) and len(res) == len(pick) and all(v == "raised" for v in errs.values())
json.dump({"owners": {k: list(v) for k, v in res.items()}, "error_cases": errs, "pass": ok}, open("/g0/swap-test.json", "w"), indent=1)
print("PASS" if ok else "FAIL", errs); sys.exit(0 if ok else 1)
