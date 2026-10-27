#!/usr/bin/env python3
"""Build README.md and the comparison run's summaries from the published results.

    python3 tools/build_readme.py

Reads results/<run>/ (SUMMARY.md, RUN.json, Block Q score summaries, Block T receipts, Block L analyses) and writes:
  README.md                                     from tools/README.template.md
  results/2026-10-26-cuteafd-vs-vllm/README.md  per-block detail and slot status
  results/2026-10-26-cuteafd-vs-vllm/t/SUMMARY.md   (only while the run has no T-SUMMARY.md of its own)
  results/2026-10-26-cuteafd-vs-vllm/l/SUMMARY.md
Cells whose engine run has not finished print "pending". Standard library only (Python 3.10+).
"""
import json, re, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = "2026-10-26-cuteafd-vs-vllm"
D = ROOT / "results" / RUN
ENG = {"V1": "vLLM fork v0.9.2", "C1": "CuteAFD v3.0.1"}
PENDING = "pending"


def load(p):
    return json.loads(Path(p).read_text())


def f4(x): return f"{x:.4f}"
def sgn(x, nd=4): return f"{x:+.{nd}f}"
def ci(c, nd=4, scale=1.0): return f"[{c[0] * scale:+.{nd}f}, {c[1] * scale:+.{nd}f}]"
def pct(x): return f"{100 * x:.2f}%"
def zero(x, nd=4): return "0 (bit-identical)" if x == 0 else sgn(x, nd)


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ------------------------------------------------------------------ the run's SUMMARY.md (the basis of the results section)

LINK = {"PROTOCOL-DRAFT.md": "protocol/PROTOCOL.md", "FROZEN.json": "protocol/FROZEN.json", "FOLLOWUPS.md": "protocol/FOLLOWUPS.md"}


def link_refs(text, prefix):
    """`file` references in the run's documents -> links where the file is published. prefix: path from the output
    document to the run folder ("results/<run>/" for README.md, "" for the run's own README)."""
    up = "" if prefix else "../../"
    def rep(m):
        name = m.group(1)
        if name in LINK and (ROOT / LINK[name]).exists(): return f"[`{name}`]({up}{LINK[name]})"
        if (D / name).is_file(): return f"[`{name}`]({prefix}{name})"
        hits = [q for q in D.rglob(name) if q.is_file()] if "/" not in name else []
        if len(hits) == 1: return f"[`{name}`]({prefix}{hits[0].relative_to(D).as_posix()})"
        return m.group(0)
    return re.sub(r"`([A-Za-z0-9_./-]+\.(?:md|json|csv))`", rep, text)


def summary_sections(prefix):
    """(intro, {heading: (heading line, body)}) of SUMMARY.md, headings demoted one level, file references linked."""
    p = D / "SUMMARY.md"
    if not p.exists(): return "", {}
    text = link_refs(p.read_text(), prefix)
    parts = re.split(r"(?m)^## ", text)
    intro = "\n".join(l for l in parts[0].splitlines() if not l.startswith("# ")).strip()
    secs = {}
    for s in parts[1:]:
        head, _, body = s.partition("\n")
        secs[head.split(" (")[0].strip()] = ("### " + head.strip(), body.strip())
    return intro, secs


def sec(secs, key):
    h, b = secs.get(key, (f"### {key}", "_Not written yet._"))
    return h + "\n\n" + b


# ------------------------------------------------------------------ Block Q

def q_buckets():
    """P-B generated rows by bucket, CuteAFD minus the mean of the vLLM runs (pb-vs-vllm-mean3.json), with F1 arms."""
    q = D / "q"
    m3 = q / "pb/pb-vs-vllm-mean3.json"
    if not m3.exists(): return ""
    m = load(m3); pair = load(q / "pb/pb-pair-V1-C1.json")["gen"]
    nrows = {"all": pair["overall"]["rows"], **{k: v["rows"] for k, v in pair["by_bucket"].items()}}
    def kl(k): return f"{sgn(m[k][0])} {ci(m[k][1:])}" if k in m else "n/a"
    def t1(k): return f"{100 * m[k][0]:+.2f} pts {ci(m[k][1:], 2, 100)}" if k in m else "n/a"
    rows = [[{"all": "all generated rows"}.get(b, b), f"{nrows.get(b, 0):,}", kl(f"{b}|kl|C1"), t1(f"{b}|top1|C1"),
             kl(f"{b}|kl|F1c"), kl(f"{b}|kl|F1d")] for b in ("all", "0-2K", "2-8K", "8-16K")]
    return ("Panel P-B, generated rows, against the mean of the three vLLM runs (two launches; `pb-vs-vllm-mean3.json`). "
            "The 8-16K bucket is block B, long code reading; whether length or content drives the difference is not "
            "separated here. F1c and F1d are follow-up F1 arms of CuteAFD, outside the frozen protocol.\n\n" +
            table(["Bucket", "Rows", "KL, CuteAFD − vLLM", "Top-1, CuteAFD − vLLM", "KL, F1c (W8A16 prefill) − vLLM",
                   "KL, F1d (KDA, head, prefill) − vLLM"], rows))


# ------------------------------------------------------------------ Block T

def t_receipts():
    """One finished receipt per arm: its full run (label <arm>-r1) if present, else the one with most measured batches."""
    out = {}
    for p in sorted((D / "t").glob("*-block-t.json")):
        d = load(p)
        if not d.get("finished"): continue
        arm, n = d["label"].split("-")[0], sum(b["kind"] == "measured" for b in d["batches"])
        key = (d["label"].endswith("-r1"), n)
        if arm not in out or key > out[arm][0]: out[arm] = (key, d)
    return {a: d for a, (_, d) in out.items()}


def t_cells(d):
    cells = {}
    for b in d["batches"]:
        if b["kind"] == "measured":
            cells.setdefault((b["length"], b["content"], b["level"]), []).append(b["summary"])
    return cells


def t_med(cells, key, k):
    xs = [s.get(key) for s in cells.get(k, []) if s.get(key) is not None]
    return statistics.median(xs) if xs else None


def t_table():
    rec = t_receipts(); cells = {a: t_cells(d) for a, d in rec.items()}
    keys = sorted({k[:2] for c in cells.values() for k in c}) or []
    if not keys: return "_No finished Block T run yet._"
    order = {"prose": 0, "code": 1, "reasoning": 2, "json": 3}
    keys.sort(key=lambda k: (k[0], order.get(k[1], 9)))
    def v(a, k, key, nd):
        if a not in cells: return PENDING
        x = t_med(cells[a], key, k)
        return "n/a" if x is None else f"{x:.{nd}f}"
    rows = []
    for L, c in keys:
        hi = 16 if L < 131072 else 4
        rows.append([f"{L // 1024}K", c,
                     v("V1", (L, c, 1), "decode_tok_s_per_stream_median", 1), v("C1", (L, c, 1), "decode_tok_s_per_stream_median", 1),
                     f"{hi}", v("V1", (L, c, hi), "aggregate_tok_s", 1), v("C1", (L, c, hi), "aggregate_tok_s", 1),
                     v("V1", (L, c, 1), "ttft_median_s", 2), v("C1", (L, c, 1), "ttft_median_s", 2)])
    head = ["Input", "Content", "Decode tok/s per stream, 1 stream: vLLM", "CuteAFD", "Streams",
            "Aggregate tok/s: vLLM", "CuteAFD", "TTFT s, 1 stream: vLLM", "CuteAFD"]
    return table(head, rows)


def t_counts():
    out = []
    for a, d in t_receipts().items():
        ms = [b["summary"] for b in d["batches"] if b["kind"] == "measured"]
        out.append(f"{ENG.get(a, a)}: {sum(s['requests'] for s in ms):,} measured requests in {len(ms)} batches, "
                   f"{sum(s['errors'] for s in ms)} errors, {sum(s.get('content_has_think_close', 0) for s in ms)} replies with "
                   "`</think>` in the content")
    return "; ".join(out) + "." if out else ""


def write_t_summary():
    if (D / "t" / "T-SUMMARY.md").exists():
        stale = D / "t" / "SUMMARY.md"
        if stale.exists(): stale.unlink()
        return
    rec = sorted((D / "t").glob("*-block-t.json"))
    done = [p for p in rec if load(p).get("finished")]
    done.sort(key=lambda p: (0 if p.name.startswith("V1") else 1, p.name))
    if not done: return
    r = subprocess.run([sys.executable, str(D / "t" / "t_summary.py")] + [str(p) for p in done[:2]],
                       capture_output=True, text=True, check=True)
    note = ("Generated by `t_summary.py` from the finished receipts in this folder "
            f"({', '.join(p.name for p in done[:2])}). A ratio column appears once both engines have finished.\n\n")
    cached = []
    for p in done:
        d = load(p)
        for b in d["batches"]:
            if b["kind"] == "cached":
                s = b["summary"]; reqs = [g for grp in b["groups"] for g in grp]
                cached.append([d["label"], f"{s['prompt_tokens'][0]:,}", len(reqs),
                               ", ".join(str(g.get("cached_tokens")) for g in reqs),
                               ", ".join(f"{g['ttft_s']:.2f}" for g in reqs)])
    extra = ("\n### Cached-prompt cell\n\nThe same prompt (8K prose, prompt 0, one nonce) sent in sequence after a primer request; "
             "measured requests only.\n\n" + table(["Run", "Prompt tokens", "Requests", "cached_tokens per request",
                                                      "TTFT s per request"], cached) + "\n") if cached else ""
    (D / "t" / "SUMMARY.md").write_text("# Block T summary\n\n" + note + r.stdout + extra)


# ------------------------------------------------------------------ Block L

def l_summaries():
    out = {}
    for p in sorted((D / "l").glob("*analysis*.json")):
        for s in load(p)["summary"]:
            out[(s["label"].split("-")[0], s["stage"], s["content"])] = s
    return out


def l_check(s):
    c, n = s["content"], s["n"]
    if c == "code": return f"all tests pass {s['all_pass']}/{n}"
    if c == "json": return f"valid {s['valid']}/{n}"
    if c == "reasoning": return f"correct {s['correct']}/{n}"
    return f"words/required {s['words_ratio_median']:.2f}"


def l_table(detail=False):
    S = l_summaries()
    keys = sorted({(st, c) for _, st, c in S}, key=lambda k: (["L1", "L2", "L3", "L3s"].index(k[0]), ["prose", "code", "reasoning", "json"].index(k[1])))
    if not keys: return "_No finished Block L run yet._"
    def cell(a, k):
        s = S.get((a,) + k)
        if not s: return [PENDING] * (4 if detail else 3)
        base = [f"{s['stop']} / {s['cap']} / {s['terminal_loops']}", l_check(s), f"{s['decode_tok_s_median']:.1f}"]
        return base + ([f"{s['completion_tokens_median']:,.0f}"] if detail else [])
    rows = []
    for k in keys:
        n = next(S[x]["n"] for x in S if x[1:] == k)
        cap = {"L1": "8K", "L2": "32K", "L3": "128K", "L3s": "128K, 1 stream"}[k[0]]
        rows.append([k[0], cap, k[1], n] + cell("V1", k) + cell("C1", k))
    sub = ["finished / at cap / terminal loops", "check", "decode tok/s"] + (["median tokens"] if detail else [])
    head = ["Stage", "Cap", "Content", "Requests"] + [f"vLLM: {x}" for x in sub] + [f"CuteAFD: {x}" for x in sub]
    return table(head, rows)


def write_l_summary():
    if not l_summaries(): return
    (D / "l" / "SUMMARY.md").write_text(
        "# Block L summary\n\nGenerated from the analysis files in this folder by `tools/build_readme.py`. Per stage and "
        "content: requests that finished on their own (`stop`), that reached the cap, and that ended in a terminal loop (R50 ≥ 0.5 at "
        "the end of the reply); the content check (code: hidden pytest suite; JSON: schema, count, ids; reasoning: MATH-500 answer; "
        "prose: words written over words required); median decode rate.\n\n" + l_table(detail=True) + "\n")


# ------------------------------------------------------------------ status and other runs

def slots():
    return load(D / "RUN.json")["slots"]


def status_lines():
    out = []
    for k, s in slots().items():
        mark = "done" if s["status"] == "done" else "**pending**"
        out.append(f"- {s['title']}: {mark}" + (f" ({s['note']})" if s.get("note") else ""))
    return "\n".join(out)


def other_runs():
    rows = []
    for d in sorted((ROOT / "results").iterdir()):
        if d.is_dir() and (d / "RUN.json").exists() and d.name != RUN:
            r = load(d / "RUN.json")
            rows.append([f"[`{d.name}`](results/{d.name}/)", r["kind"], r["title"]])
    return table(["Run", "Kind", "What it is"], rows)


def t_link():
    return "t/T-SUMMARY.md" if (D / "t" / "T-SUMMARY.md").exists() else "t/SUMMARY.md"


L_NOTE = ("The terminal-loop counts on code replies come from the detector counting the answer restating code drafted in "
          "the reasoning; no periodic structure was found in them (audit U5). The code, JSON and prose tasks were sized for "
          "thinking off: at the L1 and L2 caps, and for the 1,030-record JSON task at L3, the reasoning leaves too little "
          "room for the answer, so those cells measure stop-versus-cap rather than task completion.")


def substitutions(prefix):
    intro, secs = summary_sections(prefix)
    return {"{{STATUS}}": status_lines(), "{{S_INTRO}}": intro, "{{S_PRECISION}}": sec(secs, "Precision"),
            "{{S_THROUGHPUT}}": sec(secs, "Throughput"), "{{S_LONG}}": sec(secs, "Long output to 128K"),
            "{{S_OBSERVATIONS}}": sec(secs, "Observations"), "{{S_LIMITS}}": sec(secs, "Limits"),
            "{{Q_BUCKETS}}": q_buckets(), "{{T_TABLE}}": t_table(), "{{T_COUNTS}}": t_counts(), "{{T_LINK}}": t_link(),
            "{{L_TABLE}}": l_table(), "{{L_DETAIL}}": l_table(detail=True), "{{L_NOTE}}": L_NOTE,
            "{{OTHER_RUNS}}": other_runs()}


def render(template, out, prefix):
    text = (ROOT / "tools" / template).read_text()
    for k, v in substitutions(prefix).items(): text = text.replace(k, v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left: raise SystemExit(f"{template}: unfilled placeholders {left}")
    out.write_text(text)


def main():
    write_t_summary(); write_l_summary()
    render("README.template.md", ROOT / "README.md", f"results/{RUN}/")
    render("RUN-README.template.md", D / "README.md", "")
    print("wrote README.md, results/%s/README.md, l/SUMMARY.md" % RUN)


if __name__ == "__main__":
    main()
