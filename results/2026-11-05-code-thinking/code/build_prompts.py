#!/usr/bin/env python3
"""Build the code-thinking prompt set in the Block L layout (stage0/prompts/L/{index.json,p<i>.json,code/<project>/}),
so the frozen Block L driver and analyzer read it unchanged. p0-p3: the four Block L code projects, copied byte for byte
(same specs, tests and reference). p4-p15: the twelve projects authored 2026-11-05 (prompts/code/<project>), in
alphabetical order. Wrapper: the authored L_code wrapper (stage0 prompts/authored/wrappers.json), filled with
str.replace. Prompt token counts: K3.25 tokenizer on the user message plus the chat-template overhead measured on p0-p3
(template_with_nonce minus message tokens), recorded as an estimate. Standard library on the host; tokenization in the CPU
image (no network)."""
import hashlib, json, os, shutil, subprocess, sys

D = "<ct-run>"; S0 = "<run>/stage0/prompts"
OUT = f"{D}/stage0/prompts"; NEW = f"{D}/prompts/code"
OLD = ["minicalc", "kvstore", "graphkit", "csvreport"]
IMG = "sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a"
REPO = "<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K3.25-v1"
TOK = "/repo/snapshots/0490d2f708b12145f6516555ab066aaeb401cd21/tokenizer.json"
wrap = json.load(open(f"{S0}/authored/wrappers.json"))["L_code"]
old_cells = {}
for i in range(4):
    c = json.load(open(f"{S0}/L/code/p{i}.json")) if os.path.exists(f"{S0}/L/code/p{i}.json") else json.load(open(f"{S0}/L/p{i}.json"))
    old_cells[i] = c
assert [old_cells[i]["checker"]["project"] for i in range(4)] == OLD, [old_cells[i]["checker"]["project"] for i in range(4)]
new = sorted(os.listdir(NEW)); assert len(new) == 12, new
if os.path.exists(f"{OUT}/L/code"):
    sys.exit("exists: stage0/prompts/L/code (built already)")
os.makedirs(f"{OUT}/L/code")
for p in OLD:
    shutil.copytree(f"{S0}/L/code/{p}", f"{OUT}/L/code/{p}", ignore=shutil.ignore_patterns("__pycache__"))
for p in new:
    shutil.copytree(f"{NEW}/{p}", f"{OUT}/L/code/{p}", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
cells = {}
for i, p in enumerate(OLD):
    cells[i] = old_cells[i]
for j, p in enumerate(new):
    i = 4 + j; spec = open(f"{OUT}/L/code/{p}/SPEC.md").read()
    tests = sorted(f for f in os.listdir(f"{OUT}/L/code/{p}/tests") if f.endswith(".py"))
    msg = wrap.replace("{spec}", spec.rstrip("\n")).replace("{package}", p)
    cells[i] = {"id": f"CT-code-p{i}", "block": "L", "content": "code", "prompt_index": i, "thinking": False,
                "messages": [{"role": "user", "content": msg}], "nonce": old_cells[0]["nonce"],
                "prompt_tokens": {}, "checker": {"kind": "code", "project": p, "package": p,
                "tests_dir": f"L/code/{p}/tests", "tests_sha256": {t: hashlib.sha256(open(f"{OUT}/L/code/{p}/tests/{t}", "rb").read()).hexdigest() for t in tests}},
                "item": {"source": "authored 2026-11-05", "project": p}}
# check the old wrapper reproduces p0-p3 exactly (same construction for the new ones)
for i, p in enumerate(OLD):
    spec = open(f"{OUT}/L/code/{p}/SPEC.md").read()
    assert wrap.replace("{spec}", spec.rstrip("\n")).replace("{package}", p) == old_cells[i]["messages"][0]["content"], p
texts = {i: c["messages"][0]["content"] for i, c in cells.items()}
json.dump(texts, open(f"{D}/.msgs.json", "w"))
code = ("import json;from tokenizers import Tokenizer;t=Tokenizer.from_file('%s');m=json.load(open('/d/.msgs.json'));"
        "print(json.dumps({k:len(t.encode(v,add_special_tokens=False).ids) for k,v in m.items()}))" % TOK)
r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "CUDA_VISIBLE_DEVICES=",
                    "-v", f"{D}:/d:ro", "-v", f"{REPO}:/repo:ro", "--entrypoint", "python3", IMG, "-c", code], capture_output=True, text=True)
os.remove(f"{D}/.msgs.json")
n = {int(k): v for k, v in json.loads(r.stdout.strip().splitlines()[-1]).items()}
over = [old_cells[i]["prompt_tokens"]["template_with_nonce"] - n[i] for i in range(4)]
assert len(set(over)) == 1, over
for i in range(4, 16):
    cells[i]["prompt_tokens"] = {"template_with_nonce": n[i] + over[0], "estimate": "message tokens + measured template overhead"}
idx = {"rule": {"code_items": "p0-p3: the Block L code projects (unchanged); p4-p15: projects authored 2026-11-05, alphabetical",
                "thinking": "on (the v4 driver sends enable_thinking=true)"}, "prompts": []}
for i, c in sorted(cells.items()):
    f = f"L/p{i}.json"; b = (json.dumps(c, indent=1) + "\n").encode()
    open(f"{OUT}/{f}", "wb").write(b)
    idx["prompts"].append({"id": c["id"], "file": f, "sha256": hashlib.sha256(b).hexdigest(), "content": "code", "prompt_index": i})
json.dump(idx, open(f"{OUT}/L/index.json", "w"), indent=1)
print({i: (c["checker"]["project"], c["prompt_tokens"]["template_with_nonce"]) for i, c in sorted(cells.items())})
