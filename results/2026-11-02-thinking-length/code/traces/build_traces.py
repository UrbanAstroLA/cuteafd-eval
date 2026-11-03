#!/usr/bin/env python3
"""Build the stop-decision trace set (G2 input) from the looping investigation's stored GPQA reasoning samples.

Selection (deterministic, Random(20261102)): finished samples (finish stop, </think> position known) with total length
<= 160K tokens, 12 per document, spread over length tertiles within the document; non-finished samples (loop or
exhaust at the cap) 6 per document, truncated to the first 64K tokens. Documents 79, 13, 127, 88, 121.
Token sequence = zai/checkpoint chat template (one user message from lm-eval's GPQA rendering, enable_thinking on,
generation prompt, ends in <think>) + the stored reasoning text + (finished only) </think>. The reasoning text is
re-tokenized: the stored text is what the model wrote; its token ids may differ from the generated ids at a few
boundaries, which is the same for every arm.
Writes registry entries for the capture plugin (reduced mode: top 64 + </think> + <|user|> + chosen) and an index.
Runs in the v0.9.2-experimental image (tokenizers, jinja2), --network none.
"""
import glob, hashlib, json, os, random, re, sys
import jinja2, jinja2.ext
from jinja2.sandbox import ImmutableSandboxedEnvironment
from tokenizers import Tokenizer
DIAG, OUT = "/diag", "/traces"
SET = os.environ.get("SET", "tr")                   # registry set name
SRC_GLOB = os.environ.get("SRC_GLOB", f"{DIAG}/*/**/doc*_rep*.json")
CK_ALL = os.environ.get("CK_ALL")                    # checkpoint label for every sample (on-policy set)
DOCS_ENV = os.environ.get("DOCS")
FIN_PER_DOC = int(os.environ.get("FIN_PER_DOC", "8"))
NON_PER_DOC = int(os.environ.get("NON_PER_DOC", "3"))
MAX_FIN = int(os.environ.get("MAX_FIN_TOKENS", "96000"))
NON_TRUNC = int(os.environ.get("NON_TRUNC", "32768"))
STRIDE, LAST = 64, 512                               # stored rows: every 64th reasoning row + the last 512 before the end
SAMPLES = "/gpqa-samples.jsonl"
TEMPLATE = open("/template.jinja").read()
tok = Tokenizer.from_file("/tokenizer.json")
THINK_CLOSE, USER = 154842, None
DOCS = tuple(int(x) for x in DOCS_ENV.split(",")) if DOCS_ENV else (79, 13, 127, 88, 121)
CK = {"empties-k4-v0.8.0-2026-09-29": "K4", "k4-k5-share-screen-2026-10-01": "K4"}

def render(messages):
    e = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=[jinja2.ext.loopcontrols])
    e.filters["tojson"] = lambda x, ensure_ascii=False, indent=None, separators=None, sort_keys=False: json.dumps(
        x, ensure_ascii=ensure_ascii, indent=indent, separators=separators, sort_keys=sort_keys)
    e.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(jinja2.exceptions.TemplateError(m))
    return e.from_string(TEMPLATE).render(messages=messages, add_generation_prompt=True, enable_thinking=True)

msgs = {}
for l in open(SAMPLES):
    d = json.loads(l)
    if d["doc_id"] in DOCS:
        a = d["arguments"]["gen_args_0"]["arg_0"]; msgs[d["doc_id"]] = json.loads(a[0] if isinstance(a, list) else a)
assert set(msgs) == set(DOCS), sorted(msgs)
USER = tok.token_to_id("<|user|>"); assert tok.token_to_id("</think>") == THINK_CLOSE and USER is not None
prompt_ids = {doc: tok.encode(render(m), add_special_tokens=False).ids for doc, m in msgs.items()}
for doc, ids in prompt_ids.items():
    assert ids[-1] == tok.token_to_id("<think>"), (doc, tok.decode(ids[-3:]))

pool = []
for j in sorted(glob.glob(SRC_GLOB, recursive=True)):
    try: d = json.load(open(j))
    except Exception: continue
    if not isinstance(d, dict) or d.get("doc") not in DOCS: continue
    t = j[:-5] + ".reasoning.txt"
    if not os.path.exists(t): continue
    screen = j.split("/")[2]; arm = "/".join(j.split("/")[3:-1]) or "-"
    pool.append({"src": j, "screen": screen, "arm": arm, "ck": CK_ALL or CK.get(screen, "K3.25"),
                 "doc": d["doc"], "rep": d.get("rep"), "seed": d.get("seed"), "finish": d.get("finish_reason"),
                 "cls": d.get("cls"), "completion_tokens": (d.get("usage") or {}).get("completion_tokens"), "txt": t})
rng = random.Random(20261102)
fin = [p for p in pool if p["finish"] == "stop" and p["cls"] in ("ok", None) and p["completion_tokens"] and p["completion_tokens"] <= MAX_FIN]
non = [p for p in pool if p["finish"] == "length"]
pick = []
for doc in DOCS:
    f = sorted([p for p in fin if p["doc"] == doc], key=lambda p: p["completion_tokens"])
    if len(f) <= FIN_PER_DOC:
        pick += [dict(p, kind="finished") for p in f]
    else:   # spread over length: FIN_PER_DOC evenly spaced ranks, random within each slice
        edges = [round(i * len(f) / FIN_PER_DOC) for i in range(FIN_PER_DOC + 1)]
        pick += [dict(rng.choice(f[edges[i]:edges[i + 1]]), kind="finished") for i in range(FIN_PER_DOC)]
    n = [p for p in non if p["doc"] == doc]
    pick += [dict(p, kind="not_finished") for p in rng.sample(n, min(NON_PER_DOC, len(n)))]
os.makedirs(f"{OUT}/reg/{SET}", exist_ok=True)
index = []
for i, p in enumerate(pick):
    reason = open(p["txt"]).read()
    r_ids = tok.encode(reason, add_special_tokens=False).ids
    pre = prompt_ids[p["doc"]]
    if p["kind"] == "finished":
        ids = pre + r_ids + [THINK_CLOSE]
    else:
        ids = (pre + r_ids)[:NON_TRUNC]
    first, last = len(pre) - 1, len(ids) - 2       # rows predicting the first reasoning token .. the last token
    rows = sorted(set(range(first, last + 1, STRIDE)) | set(range(max(first, last - LAST + 1), last + 1)))
    wid = f"{SET}{i:03d}-d{p['doc']}-{p['kind'][:3]}"
    entry = {"window_id": wid, "set": SET, "tokens": ids, "rows": rows,
             "meta": {"reduce": {"topk": 64, "token_ids": [THINK_CLOSE, USER]}, "doc": p["doc"], "kind": p["kind"]}}
    json.dump(entry, open(f"{OUT}/reg/{SET}/{wid}.json", "w"))
    index.append({"window_id": wid, "kind": p["kind"], "doc": p["doc"], "ck": p["ck"], "screen": p["screen"], "arm": p["arm"],
                  "rep": p["rep"], "seed": p["seed"], "cls": p["cls"], "src": p["src"],
                  "reasoning_sha256": hashlib.sha256(reason.encode()).hexdigest(), "prompt_tokens": len(pre),
                  "reasoning_tokens_retok": len(r_ids), "completion_tokens_logged": p["completion_tokens"],
                  "tokens_total": len(ids), "rows": len(rows)})
json.dump({"set": SET, "selection": {"fin_per_doc": FIN_PER_DOC, "non_per_doc": NON_PER_DOC, "max_fin_tokens": MAX_FIN,
           "non_trunc": NON_TRUNC, "rows": f"every {STRIDE}th reasoning row + last {LAST}", "docs": DOCS},
           "n": len(index), "tokens_total": sum(x["tokens_total"] for x in index), "rows_total": sum(x["rows"] for x in index),
           "windows": index}, open(f"{OUT}/index/index-{SET}.json", "w"), indent=1)
print(json.dumps({"n": len(index), "finished": sum(x["kind"] == "finished" for x in index),
                  "not_finished": sum(x["kind"] != "finished" for x in index),
                  "tokens_total": sum(x["tokens_total"] for x in index), "rows_total": sum(x["rows"] for x in index),
                  "by_ck": {c: sum(x["ck"] == c for x in index) for c in ("K3.25", "K4")},
                  "retok_vs_logged_median_ratio": sorted(x["reasoning_tokens_retok"] / x["completion_tokens_logged"]
                      for x in index if x["kind"] == "finished" and x["completion_tokens_logged"])[len(index) // 3]}, indent=1))
