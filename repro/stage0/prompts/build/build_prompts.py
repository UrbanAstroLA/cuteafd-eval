#!/usr/bin/env python3
"""Stage 0 prompt build for the CuteAFD v3.0.1 vs vLLM v0.9.2 comparison (Blocks Q2, T, L). CPU only, no network.

Runs inside a CPU-only container (see run_build.sh) with:
  /ds    = <datasets>/2026-10-26-engine-compare           (read-only; hashes checked against SOURCES.json)
  /vsrc  = vLLM python sources copied out of image ea0430aa  (read-only)
  /repo  = models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K3.25-v1 (read-only; tokenizer + chat template)
  /out   = stage0/prompts                                      (written)
Every rule and seed used here is also written to /out/RULES.json; nothing is chosen by hand.
"""
import hashlib
import json
import random
import sys
from pathlib import Path

import jinja2
import pyarrow.parquet as pq
from tokenizers import Tokenizer

DS, VSRC, REPO, OUT = Path("/ds"), Path("/vsrc"), Path("/repo"), Path("/out")
SNAP = REPO / "snapshots/0490d2f708b12145f6516555ab066aaeb401cd21"
sys.path.insert(0, str(OUT / "checkers"))
import math_check  # noqa: E402

SEEDS = {"code_file_order": 261001, "T_prose": 261002, "T_code_humaneval": 261003, "T_code_mbpp": 261004,
         "math_level5": 261005, "nonce_verify": 261006}
PROSE_SKIP_CHARS = 16384
CODE_MIN_BYTES = 2048
Q2_LENGTHS = (32768, 65536, 131072)
Q2_ROWS = 4096
T_LENGTHS = (1024, 8192, 32768, 131072)
T_LENGTHS_SHORT_ONLY = (1024, 8192)
BARE_MAX = 896  # a T task (frame + empty context + nonce + template) must fit in 1,024 - 128 tokens
TEMPLATE_PREFIX = "[gMASK]<sop><|system|>Reasoning Effort: Max<|user|>"
TEMPLATE_SUFFIX = "<|assistant|><think>"
REF_NONCE = "000000000000"

RULES = {
    "tokenizer": "tokenizer.json of K3.25-v1 snapshot 0490d2f7 (both engines use this vocabulary); encode(text, "
                 "add_special_tokens=False)",
    "text_normalization": "PG-19 books: bytes decoded as UTF-8, CRLF -> LF. vLLM sources: decoded as UTF-8 (files "
                          "that fail are excluded), otherwise verbatim.",
    "prose_front_matter_skip": f"drop the first {PROSE_SKIP_CHARS} characters, then everything up to and including the "
                               "next blank line (first '\\n\\n' at or after that offset), then any further leading "
                               "newlines; the document starts at the next character.",
    "pg19_book_roles": "books in pg19/SELECTION.json 'picked' order (seed 70901 there): 1st-3rd -> Q2 prose windows; "
                       "4th -> Block T prose context; 5th -> Block T reasoning context (8K).",
    "code_eligible_files": f".py files under vllm/ in image ea0430aa whose first 5 lines contain "
                           f"'SPDX-License-Identifier: Apache-2.0' and whose size is >= {CODE_MIN_BYTES} bytes; sorted "
                           f"by relative path; shuffled with random.Random({SEEDS['code_file_order']}).shuffle.",
    "code_documents": "documents are built by walking the shuffled list once, without reuse: each document appends "
                      "files ('# ===== file: <relative path> =====\\n' + file text, newline-terminated, + '\\n'; each "
                      "file keeps its own license/header lines) until its tokenization reaches the needed length. "
                      "Documents 0-2 -> Q2 code windows (need 131,072 tokens); document 3 -> Block T code context "
                      "(need 131,072); document 4 -> Block T JSON context (need 8,192). Code front-matter skip: none "
                      "(0 characters).",
    "q2_windows": "tokens = first L ids of the whole document's tokenization (raw text, no chat template, no BOS), "
                  "L in 32,768 / 65,536 / 131,072, so the shorter windows of one document are prefixes of the longer; "
                  "rows = the last 4,096 row indices L-4,096 .. L-1, where row p is the position whose prediction of "
                  "token p is scored (it has seen tokens 0..p-1).",
    "chat_template": "checkpoint chat_template.jinja (byte-identical to vLLM's glm53-zai-a5b45eb.jinja) renders one "
                     "user message as TEMPLATE_PREFIX + content + TEMPLATE_SUFFIX; build verifies this with jinja2. "
                     "The template has no thinking switch: CuteAFD renders thinking-off as an extra '</think>' (+1 "
                     "token); vLLM renders the same text for on and off (its glm47 parser then streams the reasoning "
                     "as content). Recorded prompt_tokens are for the template text including the nonce line.",
    "T_prompt_shape": "user message = nonce line + '\\n' + context_frame(context prefix, task). The context prefix is "
                      "cut at a token boundary of the context document's own tokenization (character offset of the "
                      "k-th token) and stripped of trailing whitespace, k searched so that the full templated prompt with the nonce line is exactly the "
                      "target length (1,024 / 8,192 / 32,768 / 131,072); if no k gives an exact count, the character "
                      "cut is moved character by character outward from the binary-search cut (within +-64 tokens), trying at each position the stripped cut and then the raw cut (trailing whitespace kept), and the nearest exact cut is taken (later cut first); any residual deviation is recorded per cell.",
    "T_contexts": "prose -> PG-19 book 4; code -> code document 3; reasoning -> PG-19 book 5; json -> code document 4. "
                  "One fixed context per content type; prompts differ only in the task and in where the cut falls.",
    "T_lengths": "prose and code at 1K/8K/32K/128K; reasoning and json at 1K and 8K only (protocol).",
    "T_prose_items": f"LongBench-Write items with length >= 1,000 words, excluding the 4 Block L prose items, sorted "
                     f"by file index; random.Random({SEEDS['T_prose']}).shuffle; first 4.",
    "T_code_items": f"HumanEval+ task_ids sorted by number, random.Random({SEEDS['T_code_humaneval']}).shuffle, first "
                    f"2 whose bare prompt fits {BARE_MAX} tokens; MBPP+ task_ids sorted, random.Random("
                    f"{SEEDS['T_code_mbpp']}).shuffle, first 2 that fit (MBPP prompt + test_list[0]). Prompt indices: "
                    "HumanEval 0,1 then MBPP 2,3.",
    "math_items": f"MATH-500 level-5 items sorted by unique_id, random.Random({SEEDS['math_level5']}).shuffle; walk the "
                  "list keeping items whose reference solution's last \\boxed answer is_equiv() its `answer` "
                  f"(checkers/math_check.py) and whose bare prompt fits {BARE_MAX} tokens; first 4 -> Block T, "
                  "next 4 -> Block L.",
    "json_items": "authored/json_task.json: Block T variants_T (n = 40); Block L themes with n from variants_L_rule.",
    "L_prose_items": "LongBench-Write items sorted by required length descending, ties by file index ascending; "
                     "first 4.",
    "L_code_items": "the 4 authored projects in prompts/L/code (minicalc, kvstore, graphkit, csvreport), SPEC.md in "
                    "the L_code wrapper; hidden tests in each tests/ directory.",
    "L_prompt_shape": "user message = nonce line + '\\n' + task (no context).",
    "thinking": "on for reasoning (chat_template_kwargs.enable_thinking=true), off for prose, code, json.",
    "nonce": "see authored/wrappers.json nonce_rule; NONCE_GROUPS in prompts/nonce_groups.json.",
}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(Path(p).read_bytes())


def write_json(path, obj, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        if compact:
            json.dump(obj, f, separators=(",", ":"))
        else:
            json.dump(obj, f, indent=1)
        f.write("\n")


def main():
    tok = Tokenizer.from_file(str(SNAP / "tokenizer.json"))

    def enc(s):
        return tok.encode(s, add_special_tokens=False)

    def ntok(s):
        return len(tok.encode(s, add_special_tokens=False).ids)

    # ---- verify sources against SOURCES.json ----
    sources = json.loads((DS / "SOURCES.json").read_text())
    used_src = ["pg19/SELECTION.json", "longwriter/longbench_write_en.jsonl", "math500/test.jsonl",
                "humanevalplus/data/test-00000-of-00001-5973903632b82d40.parquet",
                "mbppplus/data/test-00000-of-00001-d5781c9c51e02795.parquet"]
    sel = json.loads((DS / "pg19/SELECTION.json").read_text())
    used_src += ["pg19/" + Path(b["file"]).name for b in sel["picked"]]
    src_hashes = {}
    for rel in used_src:
        h = sha256_file(DS / rel)
        if sources["files"].get(rel) != h:
            sys.exit(f"source hash mismatch: {rel}")
        src_hashes[rel] = h
    tok_hash = sha256_file(SNAP / "tokenizer.json")

    # ---- chat template check ----
    tmpl_text = (SNAP / "chat_template.jinja").read_text()
    env = jinja2.Environment(loader=jinja2.BaseLoader(), trim_blocks=True, lstrip_blocks=True,
                             extensions=["jinja2.ext.loopcontrols"])
    env.filters["tojson"] = lambda v, ensure_ascii=False: json.dumps(v, ensure_ascii=ensure_ascii)
    t = env.from_string(tmpl_text)
    for flag in (True, False):
        r = t.render(messages=[{"role": "user", "content": "PROBE"}], add_generation_prompt=True,
                     enable_thinking=flag)
        if r != TEMPLATE_PREFIX + "PROBE" + TEMPLATE_SUFFIX:
            sys.exit(f"template rendering differs from TEMPLATE_PREFIX/SUFFIX: {r!r}")

    def render(content):
        return TEMPLATE_PREFIX + content + TEMPLATE_SUFFIX

    # ---- nonce groups ----
    groups = [f"{i:03d}" for i in range(1000) if len(enc(f"{i:03d}").ids) == 1]
    wrappers = json.loads((OUT / "authored/wrappers.json").read_text())
    nonce_fmt = wrappers["nonce_line"]

    def nonce_line(n):
        return nonce_fmt.replace("{nonce}", n) + "\n"

    write_json(OUT / "nonce_groups.json", {"rule": wrappers["nonce_rule"], "groups": groups})

    # ---- documents ----
    def prose_doc(name):
        text = (DS / "pg19" / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        j = text.find("\n\n", PROSE_SKIP_CHARS)
        start = j + 2
        while start < len(text) and text[start] == "\n":
            start += 1
        return text[start:], {"file": f"pg19/{name}", "sha256": src_hashes[f"pg19/{name}"], "start_char": start,
                              "chars_after_crlf_normalization": len(text)}

    books = [Path(b["file"]).name for b in sel["picked"]]
    eligible = []
    for p in sorted(VSRC.rglob("*.py")):
        rel = p.relative_to(VSRC).as_posix()
        b = p.read_bytes()
        if len(b) < CODE_MIN_BYTES:
            continue
        try:
            s = b.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if "SPDX-License-Identifier: Apache-2.0" not in "\n".join(s.split("\n")[:5]):
            continue
        eligible.append(rel)
    eligible.sort()
    order = list(eligible)
    random.Random(SEEDS["code_file_order"]).shuffle(order)
    cursor = 0

    def code_doc(need):
        nonlocal cursor
        parts, files, est = [], [], 0
        while True:
            while est < need + 512:
                rel = order[cursor]
                cursor += 1
                s = (VSRC / rel).read_text(encoding="utf-8")
                chunk = f"# ===== file: {rel} =====\n" + s + ("" if s.endswith("\n") else "\n") + "\n"
                parts.append(chunk)
                files.append({"path": rel, "sha256": sha256_bytes((VSRC / rel).read_bytes())})
                est += ntok(chunk)
            doc = "".join(parts)
            if ntok(doc) >= need:
                return doc, {"files": files, "first_file_index_in_order": cursor - len(files)}
            est = ntok(doc)

    # ---- Q2 windows ----
    q2_index = []
    q2_docs = [("prose", f"pg{books[i].split('.')[0]}", *prose_doc(books[i])) for i in range(3)]
    for i in range(3):
        d, meta = code_doc(max(Q2_LENGTHS))
        q2_docs.append(("code", f"c{i}", d, meta))
    for kind, name, doc, meta in q2_docs:
        e = enc(doc)
        if len(e.ids) < max(Q2_LENGTHS):
            sys.exit(f"document {name} too short: {len(e.ids)}")
        for L in Q2_LENGTHS:
            end_char = e.offsets[L - 1][1]
            wid = f"q2-{kind}-{name}-{L // 1024:03d}k"
            w = {"window_id": wid, "kind": kind, "length": L, "tokens": e.ids[:L],
                 "rows": list(range(L - Q2_ROWS, L)),
                 "source": dict(meta, document=name, text_end_char=end_char,
                                text_sha256=sha256_bytes(doc[:end_char].encode()),
                                document_tokens=len(e.ids)),
                 "tokenization": "raw text, add_special_tokens=False, no chat template, no BOS"}
            write_json(OUT / "q2" / f"{wid}.json", w, compact=True)
            q2_index.append({"window_id": wid, "kind": kind, "length": L, "document": name,
                             "first_row": L - Q2_ROWS, "last_row": L - 1, "file": f"q2/{wid}.json"})
    write_json(OUT / "q2/index.json", {"rule": RULES["q2_windows"], "windows": q2_index})

    # ---- items ----
    lw = [json.loads(line) for line in (DS / "longwriter/longbench_write_en.jsonl").open()]
    L_prose_idx = sorted(range(len(lw)), key=lambda i: (-lw[i]["length"], i))[:4]
    cand = sorted(i for i in range(len(lw)) if lw[i]["length"] >= 1000 and i not in L_prose_idx)
    random.Random(SEEDS["T_prose"]).shuffle(cand)
    T_prose_idx = cand[:4]

    frame = wrappers["context_frame"]

    def framed(ctx, task):
        return frame.replace("{context}", ctx).replace("{task}", task)

    def bare_ok(task):
        return ntok(render(nonce_line(REF_NONCE) + framed("", task))) <= BARE_MAX

    he = pq.read_table(DS / "humanevalplus/data/test-00000-of-00001-5973903632b82d40.parquet").to_pylist()
    he.sort(key=lambda r: int(r["task_id"].split("/")[1]))
    random.Random(SEEDS["T_code_humaneval"]).shuffle(he)
    mb = pq.read_table(DS / "mbppplus/data/test-00000-of-00001-d5781c9c51e02795.parquet").to_pylist()
    mb.sort(key=lambda r: r["task_id"])
    random.Random(SEEDS["T_code_mbpp"]).shuffle(mb)

    def he_task(r):
        return wrappers["T_code_humaneval"].replace("{prompt}", r["prompt"])

    def mb_task(r):
        return wrappers["T_code_mbpp"].replace("{prompt}", r["prompt"]).replace("{test}", r["test_list"][0])

    code_items = [("humanevalplus", r["task_id"], he_task(r)) for r in he if bare_ok(he_task(r))][:2]
    code_items += [("mbppplus", r["task_id"], mb_task(r)) for r in mb if bare_ok(mb_task(r))][:2]

    math = [json.loads(line) for line in (DS / "math500/test.jsonl").open()]
    l5 = sorted((r for r in math if r["level"] == 5), key=lambda r: r["unique_id"])
    random.Random(SEEDS["math_level5"]).shuffle(l5)

    def math_task(r):
        return wrappers["reasoning"].replace("{problem}", r["problem"])

    math_ok = [r for r in l5 if math_check.is_equiv(math_check.last_boxed(r["solution"]), r["answer"])
               and bare_ok(math_task(r))]
    T_math, L_math = math_ok[:4], math_ok[4:8]

    jt = json.loads((OUT / "authored/json_task.json").read_text())
    schema_text = json.dumps(jt["record_schema"], indent=1)

    def json_task(theme, n):
        return (jt["prompt_template"].replace("{theme}", theme).replace("{n}", str(n))
                .replace("{schema}", schema_text))

    T_items = {
        "prose": [{"source": "longwriter", "index": i, "required_words": lw[i]["length"],
                   "task": wrappers["T_prose"].replace("{prompt}", lw[i]["prompt"])} for i in T_prose_idx],
        "code": [{"source": s, "task_id": tid, "task": task} for s, tid, task in code_items],
        "reasoning": [{"source": "math500", "unique_id": r["unique_id"], "answer": r["answer"],
                       "task": math_task(r)} for r in T_math],
        "json": [{"source": "authored/json_task.json", "theme": v["theme"], "n": v["n"],
                  "task": json_task(v["theme"], v["n"])} for v in jt["variants_T"]],
    }
    for c, items in T_items.items():
        if len(items) != 4:
            sys.exit(f"T {c}: {len(items)} items")

    # ---- T contexts ----
    ctx_docs = {}
    d, m = prose_doc(books[3])
    ctx_docs["prose"] = (d, dict(m, kind="pg19"))
    d, m = code_doc(max(T_LENGTHS))
    ctx_docs["code"] = (d, dict(m, kind="vllm-source", document="c3"))
    d, m = prose_doc(books[4])
    ctx_docs["reasoning"] = (d, dict(m, kind="pg19"))
    d, m = code_doc(8192)
    ctx_docs["json"] = (d, dict(m, kind="vllm-source", document="c4"))
    ctx_enc = {}
    for c, (d, _) in ctx_docs.items():
        e = enc(d)
        ctx_enc[c] = [o[1] for o in e.offsets]

    def fit(c, task, target):
        doc, offs = ctx_docs[c][0], ctx_enc[c]
        nl = nonce_line(REF_NONCE)

        def cut(endc):
            # endc >= 0: doc[:endc] stripped of trailing whitespace; endc < 0: raw doc[:-endc] (fallback only)
            return doc[:endc].rstrip() if endc >= 0 else doc[:-endc]

        def total_chars(endc):
            return ntok(render(nl + framed(cut(endc), task)))

        def total(k):
            return total_chars(offs[k - 1] if k > 0 else 0)

        if total(0) > target:
            sys.exit(f"task does not fit {target}")
        lo, hi = 0, min(len(offs), target)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if total(mid) <= target:
                lo = mid
            else:
                hi = mid - 1
        k = lo
        endc = offs[k - 1] if k > 0 else 0
        n = total_chars(endc)
        if n != target:
            # the count is not monotone in the cut (merges at the cut): search character cuts outward from the
            # binary-search cut, nearest first (later cut first on equal distance), within +-64 tokens of k
            a = offs[k - 65] if k > 65 else 0
            b = offs[min(k + 64, len(offs) - 1)]
            for d in range(0, max(endc - a, b - endc) + 1):
                cands = [e2 for e2 in (endc + d, endc - d) if a <= e2 <= b and (e2 > 0 or d == 0)]
                cands = [e2 for e2 in cands if d > 0 and total_chars(e2) == target] + \
                        [-e2 for e2 in cands if e2 > 0 and total_chars(-e2) == target]
                if cands:
                    endc, n = cands[0], target
                    break
        return cut(endc), endc, n

    T_index = []
    for c, items in T_items.items():
        lengths = T_LENGTHS if c in ("prose", "code") else T_LENGTHS_SHORT_ONLY
        for L in lengths:
            for p, it in enumerate(items):
                ctx_text, endc, n = fit(c, it["task"], L)
                content = framed(ctx_text, it["task"])
                cid = f"T-{c}-{L // 1024:03d}k-p{p}"
                cell = {"id": cid, "block": "T", "content": c, "input_length": L, "prompt_index": p,
                        "thinking": c == "reasoning",
                        "messages": [{"role": "user", "content": content}],
                        "nonce": {"line_format": nonce_fmt, "insert": "prepend nonce line + '\\n' to messages[0]"
                                  ".content"},
                        "prompt_tokens": {"template_with_nonce": n, "target": L, "deviation": n - L,
                                          "cuteafd_thinking_off_adds": 0 if c == "reasoning" else 1},
                        "context": {k: v for k, v in ctx_docs[c][1].items() if k != "files"} |
                                   {"chars_used": len(ctx_text), "cut": "raw" if endc < 0 else "rstrip",
                                    "files_used": [f["path"] for f in ctx_docs[c][1].get("files", [])
                                                   if f"# ===== file: {f['path']} =====" in
                                                   ctx_text] if "files" in ctx_docs[c][1] else None},
                        "item": {k: v for k, v in it.items() if k != "task"}}
                f = OUT / "T" / c / f"{L // 1024:03d}k" / f"p{p}.json"
                write_json(f, cell)
                T_index.append({"id": cid, "content": c, "input_length": L, "prompt_index": p,
                                "thinking": cell["thinking"], "prompt_tokens": n, "deviation": n - L,
                                "file": str(f.relative_to(OUT)), "sha256": sha256_file(f)})
                print(cid, n, flush=True)

    # nonce token-count invariance on one 1K cell per content
    rng = random.Random(SEEDS["nonce_verify"])
    nonce_check = {}
    for c in T_items:
        cell = json.loads((OUT / "T" / c / "001k" / "p0.json").read_text())
        counts = set()
        for _ in range(500):
            nn = "".join(rng.choice(groups) for _ in range(4))
            counts.add(ntok(render(nonce_line(nn) + cell["messages"][0]["content"])))
        nonce_check[c] = sorted(counts)
        if counts != {cell["prompt_tokens"]["template_with_nonce"]}:
            sys.exit(f"nonce changes token count for {c}: {counts}")

    # ---- L prompts ----
    rec_line = json.dumps(jt["example_record"])
    tpr = ntok(rec_line) + 2
    L_json = []
    for theme, (cap, frac) in zip(jt["variants_L_themes"], jt["variants_L_fractions"]):
        n = int(round(cap * frac / tpr / 10.0)) * 10
        L_json.append({"theme": theme, "n": n, "est_tokens": n * tpr, "cap_ref": cap, "fraction": frac})
    projects = [("minicalc", "minicalc"), ("kvstore", "kvstore"), ("graphkit", "graphkit"),
                ("csvreport", "csvreport")]
    L_items = {
        "prose": [{"source": "longwriter", "index": i, "required_words": lw[i]["length"],
                   "task": wrappers["L_prose"].replace("{prompt}", lw[i]["prompt"]),
                   "checker": {"kind": "prose", "required_words": lw[i]["length"]}} for i in L_prose_idx],
        "code": [{"source": "authored", "project": proj,
                  "task": wrappers["L_code"].replace("{spec}", (OUT / "L/code" / proj / "SPEC.md").read_text()
                                                     .strip()).replace("{package}", pkg),
                  "checker": {"kind": "code", "project": proj, "package": pkg,
                              "tests_dir": f"L/code/{proj}/tests",
                              "tests_sha256": {f.name: sha256_file(f) for f in
                                               sorted((OUT / "L/code" / proj / "tests").glob("*.py"))}}}
                 for proj, pkg in projects],
        "reasoning": [{"source": "math500", "unique_id": r["unique_id"], "answer": r["answer"],
                       "task": math_task(r), "checker": {"kind": "math", "answer": r["answer"]}} for r in L_math],
        "json": [{"source": "authored/json_task.json", "theme": v["theme"], "n": v["n"],
                  "est_output_tokens": v["est_tokens"], "task": json_task(v["theme"], v["n"]),
                  "checker": {"kind": "json", "n": v["n"], "schema": "authored/json_task.json#record_schema"}}
                 for v in L_json],
    }
    L_index = []
    for c, items in L_items.items():
        if len(items) != 4:
            sys.exit(f"L {c}: {len(items)} items")
        for p, it in enumerate(items):
            content = it["task"]
            n = ntok(render(nonce_line(REF_NONCE) + content))
            cid = f"L-{c}-p{p}"
            cell = {"id": cid, "block": "L", "content": c, "prompt_index": p, "thinking": c == "reasoning",
                    "messages": [{"role": "user", "content": content}],
                    "nonce": {"line_format": nonce_fmt, "insert": "prepend nonce line + '\\n' to messages[0].content"},
                    "prompt_tokens": {"template_with_nonce": n,
                                      "cuteafd_thinking_off_adds": 0 if c == "reasoning" else 1},
                    "checker": it["checker"],
                    "item": {k: v for k, v in it.items() if k not in ("task", "checker")}}
            f = OUT / "L" / c / f"p{p}.json"
            write_json(f, cell)
            L_index.append({"id": cid, "content": c, "prompt_index": p, "thinking": cell["thinking"],
                            "prompt_tokens": n, "checker": it["checker"]["kind"], "file": str(f.relative_to(OUT)),
                            "sha256": sha256_file(f)})

    write_json(OUT / "T/index.json", {"rule": {k: RULES[k] for k in ("T_prompt_shape", "T_contexts", "T_lengths",
                                                                      "T_prose_items", "T_code_items", "math_items",
                                                                      "json_items", "thinking", "nonce")},
                                      "nonce_token_invariance": nonce_check, "cells": T_index})
    write_json(OUT / "L/index.json", {"rule": {k: RULES[k] for k in ("L_prose_items", "L_code_items", "math_items",
                                                                      "json_items", "L_prompt_shape", "thinking",
                                                                      "nonce")},
                                      "json_tokens_per_record_estimate": tpr, "json_variants": L_json,
                                      "prompts": L_index})
    write_json(OUT / "RULES.json", {
        "rules": RULES, "seeds": SEEDS, "constants": {
            "PROSE_SKIP_CHARS": PROSE_SKIP_CHARS, "CODE_MIN_BYTES": CODE_MIN_BYTES, "Q2_LENGTHS": Q2_LENGTHS,
            "Q2_ROWS": Q2_ROWS, "T_LENGTHS": T_LENGTHS, "BARE_MAX": BARE_MAX, "TEMPLATE_PREFIX": TEMPLATE_PREFIX,
            "TEMPLATE_SUFFIX": TEMPLATE_SUFFIX, "REF_NONCE": REF_NONCE},
        "sources": {"dataset_files_sha256": src_hashes, "tokenizer_json_sha256": tok_hash,
                    "chat_template_sha256": sha256_file(SNAP / "chat_template.jinja"),
                    "vllm_image": "sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2",
                    "vllm_eligible_files": len(eligible),
                    "vllm_eligible_list_sha256": sha256_bytes("\n".join(eligible).encode()),
                    "vllm_files_consumed": cursor},
        "selection": {"pg19_books_in_order": books, "L_prose_index": L_prose_idx, "T_prose_index": T_prose_idx,
                      "T_code": [[s, tid] for s, tid, _ in code_items],
                      "T_math": [r["unique_id"] for r in T_math], "L_math": [r["unique_id"] for r in L_math],
                      "L_json": L_json}})
    print("done", len(q2_index), "windows,", len(T_index), "T cells,", len(L_index), "L prompts")


if __name__ == "__main__":
    main()
