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

def q_buckets(prefix=f"results/{RUN}/"):
    """P-B generated rows by bucket, CuteAFD minus the mean of the vLLM runs (pb-vs-vllm-mean3.json), with F1 arms."""
    q = D / "q"
    m3 = q / "pb/pb-vs-vllm-mean3.json"
    if not m3.exists(): return ""
    m = load(m3); pair = load(q / "pb/pb-pair-V1-C1.json")["gen"]
    nrows = {"all": pair["overall"]["rows"], **{k: v["rows"] for k, v in pair["by_bucket"].items()}}
    def kl(k): return f"{sgn(m[k][0])} {ci(m[k][1:])}" if k in m else "n/a"
    def t1(k): return f"{100 * m[k][0]:+.2f} pts {ci(m[k][1:], 2, 100)}" if k in m else "n/a"
    tp = q / "tails/pb-tails.json"
    T = load(tp) if tp.exists() else None
    def hist(b):
        if not T: return "n/a"
        c = T["scored"]["context"] if b == "all" else next(x["context"] for x in T["by_position"] if x["band"] == b)
        n = lambda x: f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"
        return f"{n(c['min'])} / {n(c['median'])} / {n(c['max'])}"
    rows = [[{"all": "all generated rows"}.get(b, b), f"{nrows.get(b, 0):,}", hist(b), kl(f"{b}|kl|C1"), t1(f"{b}|top1|C1"),
             kl(f"{b}|kl|F1c"), kl(f"{b}|kl|F1d")] for b in ("all", "0-2K", "2-8K", "8-16K")]
    return ("Panel P-B, generated rows, against the mean of the three vLLM runs (two launches; `pb-vs-vllm-mean3.json`). "
            "The 8-16K bucket is block B, long code reading; whether length or content drives the difference is not "
            "separated here. F1c and F1d are follow-up F1 arms of CuteAFD, outside the frozen protocol. History: the tokens "
            "before each scored position. Tails (p99, p99.9) and KL by position: [`q/tails/`](" + prefix + "q/tails/).\n\n" +
            table(["Bucket", "Rows", "History, tokens (min / median / max)", "KL, CuteAFD − vLLM", "Top-1, CuteAFD − vLLM", "KL, F1c (W8A16 prefill) − vLLM",
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
        if d.is_dir() and (d / "RUN.json").exists() and d.name not in (RUN, K4):
            r = load(d / "RUN.json")
            rows.append([f"[`{d.name}`](results/{d.name}/)", r["kind"], r["title"]])
    return table(["Run", "Kind", "What it is"], rows)


def t_link():
    return "t/T-SUMMARY.md" if (D / "t" / "T-SUMMARY.md").exists() else "t/SUMMARY.md"


L_NOTE = ("The terminal-loop counts on code replies come from the detector counting the answer restating code drafted in "
          "the reasoning; no periodic structure was found in them (audit U5). The code, JSON and prose tasks were sized for "
          "thinking off: at the L1 and L2 caps, and for the 1,030-record JSON task at L3, the reasoning leaves too little "
          "room for the answer, so those cells measure stop-versus-cap rather than task completion.")


# ------------------------------------------------------------------ K4 run (results/2026-10-27-k4-vllm-cuteafd)
# Every number below is read from the run's published files. Its precision numbers are top-20 measures (KL20, KL_pb20,
# KL20n): they are printed only beside each other or beside the K3.25 run's numbers under the same top-20 definitions
# (q/k325-top20-reference.json), never in a column with full-vocabulary KL.

K4 = "2026-10-27-k4-vllm-cuteafd"
D4 = ROOT / "results" / K4


def k4_ok():
    return (D4 / "q" / "pa20.json").exists()


def k4_num(x): return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"
def k4_hist(c): return f"{k4_num(c['min'])} / {k4_num(c['median'])} / {k4_num(c['max'])}"


def k4_data():
    q = D4 / "q"
    K = {"pa": load(q / "pa20.json"), "pb": load(q / "pb20.json"), "q2": load(q / "q2-top20.json"),
         "T": {k: load(q / "tails" / f"{k}-tails.json") for k in ("pa", "pb", "q2")}, "ref": load(q / "k325-top20-reference.json"),
         "tc": load(D4 / "t" / "t-compare.json"), "su": load(D4 / "startup" / "startup.json"),
         "f1": {k: load(D4 / "f1k4" / "score" / f"{k}.json") for k in ("pa20", "pb20", "q2-top20", "f1c-minus-c1")}}
    import csv
    with open(q / "rows" / "pb-rows.csv", newline="") as f:
        ctx = sorted(int(r["context"]) for r in csv.DictReader(f) if r["role"] == "gen" and r["block"] == "B")
    K["histB"] = {"min": ctx[0], "median": statistics.median(ctx), "max": ctx[-1]}
    return K


def k4_reading(d, ci, floor=None):
    if ci[0] > 0 or ci[1] < 0:
        return "differs" if floor is None or abs(d) > abs(floor) else "within vLLM's launch-to-launch spread"
    return "not resolved"


def k4_precision_rows(K):
    """(label, history, vLLM, CuteAFD, difference text, launch-to-launch text, reading) per headline measure."""
    pa, pb, q2, T = K["pa"], K["pb"], K["q2"], K["T"]
    out = []
    hp = k4_hist(T["pa"]["scored"]["context"])
    for m, lab, fmt, sc in (("kl_e20", "P-A, teacher KL20 (25 windows × 2,048 tokens)", "{:.4f}", 1),
                            ("top1", "P-A, top-1 agreement with the teacher", "{:.2f}%", 100),
                            ("nll", "P-A, NLL of the actual token", "{:.4f}", 1)):
        p = pa["paired"]["C-r1-Vmean"][m]; fl = pa["floors"]["V-r2-V-r1"][m]["B_minus_A"]
        unit = " pts" if sc == 100 else ""; nd = 2 if sc == 100 else 4
        out.append([lab, hp, fmt.format(sc * p["A"]), fmt.format(sc * p["B"]),
                    f"{sc * p['B_minus_A']:+.{nd}f}{unit} {ci(p['ci95'], nd, sc)}", f"{sc * fl:+.{nd}f}{unit}",
                    k4_reading(p["B_minus_A"], p["ci95"], fl)])
    band = {b["band"]: b for b in T["pb"]["by_position"]}
    for g, lab, h in (("gen", "P-B, generated rows, KL_pb20", T["pb"]["scored"]["context"]),
                      ("gen 0-2K", "P-B 0-2K", band["0-2K"]["context"]), ("gen 2-8K", "P-B 2-8K", band["2-8K"]["context"]),
                      ("gen 8-16K", "P-B 8-16K", band["8-16K"]["context"]),
                      ("gen block B", "P-B block B (long code reading; the 8-16K windows)", K["histB"])):
        p = pb["paired"]["C-r1-Vmean"][g]["kl_pb20"]; fl = pb["floors"]["V-r2-V-r1"][g]["kl_pb20"]["B_minus_A"]
        out.append([lab, k4_hist(h), f4(p["A"]), f4(p["B"]), f"{sgn(p['B_minus_A'])} {ci(p['ci95'])}", sgn(fl),
                    k4_reading(p["B_minus_A"], p["ci95"], fl)])
    p = pb["paired"]["C-r1-Vmean"]["gen"]["top1"]; fl = pb["floors"]["V-r2-V-r1"]["gen"]["top1"]["B_minus_A"]
    out.append(["P-B, generated rows, top-1 agreement", k4_hist(T["pb"]["scored"]["context"]), f"{100 * p['A']:.2f}%",
                f"{100 * p['B']:.2f}%", f"{100 * p['B_minus_A']:+.2f} pts {ci(p['ci95'], 2, 100)}", f"{100 * fl:+.2f} pts",
                k4_reading(p["B_minus_A"], p["ci95"], fl)])
    v = q2["vs_vllm_mean"]["C-r1"]["dnll_x_minus_v_documents_t"]
    vm = statistics.mean(q2["per_arm"][a]["nll_mean_of_documents"] for a in ("V-r1", "V-r2"))
    fl = q2["pairs"]["V-r1|V-r2"]["dnll_yx_documents_t"]["mean"]
    out.append(["Q2, NLL on human-written text, 32K-128K (6 documents, t-interval)", k4_hist(T["q2"]["scored"]["context"]),
                f4(vm), f4(q2["per_arm"]["C-r1"]["nll_mean_of_documents"]), f"{sgn(v['mean'])} {ci(v['ci95'])}", sgn(fl),
                k4_reading(v["mean"], v["ci95"])])
    return out


def k4_precision_table(K):
    return table(["Measure (top-20)", "Scored history, tokens (min / median / max)", "vLLM (mean of 2 launches)", "CuteAFD",
                  "CuteAFD − vLLM [95%]", "vLLM launch 2 − launch 1", "Reading"], k4_precision_rows(K))


def k4_quant_rows(K):
    """K3.25 against K4 under the same top-20 definitions, per engine."""
    R = K["ref"]; pa, pb = K["pa"], K["pb"]
    rp, rb = R["pa"], R["pb"]
    vm25 = lambda g: rb["per_arm"]["Vmean3"][g]["kl_pb20"]
    rows = [["P-A, teacher KL20", f4(rp["per_arm"]["V1"]["kl_e20"]), f4(pa["per_arm"]["Vmean"]["kl_e20"]["value"]),
             f4(rp["per_arm"]["C1"]["kl_e20"]), f4(pa["per_arm"]["C-r1"]["kl_e20"]["value"]),
             f"{sgn(rp['C1_minus_V1']['kl_e20']['diff'])} {ci(rp['C1_minus_V1']['kl_e20']['ci95'])}",
             f"{sgn(pa['paired']['C-r1-Vmean']['kl_e20']['B_minus_A'])} {ci(pa['paired']['C-r1-Vmean']['kl_e20']['ci95'])}"],
            ["P-A, top-1 agreement", f"{100 * rp['per_arm']['V1']['top1']:.2f}%", f"{100 * pa['per_arm']['Vmean']['top1']['value']:.2f}%",
             f"{100 * rp['per_arm']['C1']['top1']:.2f}%", f"{100 * pa['per_arm']['C-r1']['top1']['value']:.2f}%",
             f"{100 * rp['C1_minus_V1']['top1']['diff']:+.2f} pts", f"{100 * pa['paired']['C-r1-Vmean']['top1']['B_minus_A']:+.2f} pts"]]
    for g, lab in (("gen", "P-B, generated rows, KL_pb20"), ("gen 8-16K", "P-B 8-16K, KL_pb20")):
        d25 = rb["C1_minus_Vmean3"][g]["kl_pb20"]; d4 = pb["paired"]["C-r1-Vmean"][g]["kl_pb20"]
        rows.append([lab, f4(vm25(g)), f4(pb["per_arm"]["Vmean"][g]["kl_pb20"]["value"]), f4(rb["per_arm"]["C1"][g]["kl_pb20"]),
                     f4(pb["per_arm"]["C-r1"][g]["kl_pb20"]["value"]), f"{sgn(d25['diff'])} {ci(d25['ci95'])}",
                     f"{sgn(d4['B_minus_A'])} {ci(d4['ci95'])}"])
    return rows


def k4_quant_table(K):
    return table(["Measure (top-20, same definition on both)", "vLLM, K3.25", "vLLM, K4", "CuteAFD, K3.25", "CuteAFD, K4",
                  "CuteAFD − vLLM, K3.25", "CuteAFD − vLLM, K4"], k4_quant_rows(K))


def k4_t_groups(K):
    import ast
    G = {}
    for k, c in K["tc"]["cells"].items():
        L, content, lv = ast.literal_eval(k)
        G.setdefault((L, lv), []).append((content, c["V"], c["C"]))
    return dict(sorted(G.items()))


def k4_t_rows(K):
    rows = []
    for (L, lv), cs in k4_t_groups(K).items():
        dec = [c["decode_med_ratio_vs_V"] for _, _, c in cs]; agg = [c["aggregate_ratio_vs_V"] for _, _, c in cs]
        tv = statistics.median(v["ttft_med"] for _, v, _ in cs); tc = statistics.median(c["ttft_med"] for _, _, c in cs)
        rd = lambda key: ", ".join(f"{n} {x}" for x, n in sorted(((x, sum(c[key] == x for _, _, c in cs)) for x in {c[key] for _, _, c in cs})))
        rng = lambda xs: f"{min(xs):.2f}x" if f"{min(xs):.2f}" == f"{max(xs):.2f}" else f"{min(xs):.2f}-{max(xs):.2f}x"
        rows.append([f"{L // 1024}K × {lv}", ", ".join(n for n, _, _ in cs), f"{rng(dec)} ({rd('decode_med_reading')})",
                     f"{rng(agg)} ({rd('aggregate_reading')})", f"{tv:.2f} / {tc:.2f}"])
    return rows


def k4_t_table(K):
    return table(["Input × streams", "Contents", "Decode per stream, CuteAFD ÷ vLLM (readings)", "Aggregate, CuteAFD ÷ vLLM (readings)",
                  "First token, s: vLLM / CuteAFD (median over contents)"], k4_t_rows(K))


def k4_t_counts(K):
    out = []
    for n, lab in (("V-r1", "vLLM"), ("C-r1", "CuteAFD")):
        d = load(D4 / "t" / f"{n}.json")
        ms = [b["summary"] for b in d["batches"] if b["kind"] == "measured"]
        out.append(f"{lab}: {sum(s['requests'] for s in ms)} measured requests, {sum(s['errors'] for s in ms)} errors")
    mm = sum(c["C"]["prompt_token_mismatch"] for c in K["tc"]["cells"].values())
    return "; ".join(out) + (f". Prompt-token counts identical on every cell except the 128K code cell ({mm} CuteAFD "
                             "requests longer: those prompts hold literal `<think>` text, which vLLM parses as a special token).")


def k4_f1_rows(K):
    f = K["f1"]; pa, pb, d = f["pa20"], f["pb20"], f["f1c-minus-c1"]
    def pair(src, key, g=None):
        p = src["paired"][key] if g is None else src["paired"][key][g]
        return p
    rows = []
    for lab, g, dk in (("P-A, teacher KL20", None, "P-A kl_e20"), ("P-B, generated rows", "gen", "P-B gen kl_pb20"),
                       ("P-B 8-16K", "gen 8-16K", "P-B gen 8-16K kl_pb20"), ("P-B block B (long code)", "gen block B", "P-B gen block B kl_pb20")):
        m = "kl_e20" if g is None else "kl_pb20"
        a = pair(pa if g is None else pb, "C-r1-Vmean", g)[m]; b = pair(pa if g is None else pb, "C-f1c-Vmean", g)[m]
        rows.append([lab, f"{sgn(a['B_minus_A'])} {ci(a['ci95'])}", f"{sgn(b['B_minus_A'])} {ci(b['ci95'])}",
                     f"{sgn(d[dk]['diff'])} {ci(d[dk]['ci95'])}"])
    return rows


def k4_f1_speed_rows():
    """Per content cell: median per-request decode and TTFT, W8A16 over the mean of the two base launches."""
    R = {}
    for n in ("C-base1", "C-f1c", "C-base2"):
        cells = {}
        for b in load(D4 / "f1k4" / "t" / f"{n}.json")["batches"]:
            if b["kind"] != "measured": continue
            for g in b["groups"]:
                for r in g:
                    c = cells.setdefault((b["length"], b["level"], b["content"]), {"d": [], "t": []})
                    c["d"].append(r["decode_tok_s"]); c["t"].append(r["ttft_s"])
        R[n] = {k: (statistics.median(v["d"]), statistics.median(v["t"])) for k, v in cells.items()}
    rows = []
    for k in sorted(R["C-f1c"]):
        bd = (R["C-base1"][k][0] + R["C-base2"][k][0]) / 2; bt = (R["C-base1"][k][1] + R["C-base2"][k][1]) / 2
        rows.append([f"{k[0] // 1024}K × {k[1]}, {k[2]}", f"{R['C-f1c'][k][0] / bd:.3f}", f"{R['C-f1c'][k][1] / bt:.3f}",
                     f"{R['C-base2'][k][0] / R['C-base1'][k][0]:.3f}, {R['C-base2'][k][1] / R['C-base1'][k][1]:.3f}"])
    return rows


def k4_f1_tables(K):
    return (table(["Measure (top-20)", "CuteAFD as shipped − vLLM", "CuteAFD W8A16 prefill − vLLM", "W8A16 − as shipped (direct)"],
                  k4_f1_rows(K)) + "\n\n" +
            table(["Cell (input × streams, content)", "Decode, W8A16 ÷ base", "First token, W8A16 ÷ base",
                   "Base launch 2 ÷ base launch 1 (decode, first token)"], k4_f1_speed_rows()))


def k4_startup_rows(K):
    L = K["su"]["launches"]
    return [[n.replace("V-", "vLLM ").replace("C-", "CuteAFD ").replace("score", "scoring launch"), f"{v['t_models_s']:.0f} s",
             f"{v['t_ready_s']:.0f} s", f"{v['capacity']['pool_tokens']:,} tokens, {v['capacity']['max_streams']} requests"]
            for n, v in L.items()]


def k4_facts_text(K):
    """Plain-language headline values used by the summary and the site."""
    pa, pb, R = K["pa"], K["pb"], K["ref"]
    s = {"pa_v": pa["per_arm"]["Vmean"]["kl_e20"]["value"], "pa_c": pa["per_arm"]["C-r1"]["kl_e20"]["value"],
         "pa25_v": R["pa"]["per_arm"]["V1"]["kl_e20"], "pa25_c": R["pa"]["per_arm"]["C1"]["kl_e20"],
         "d_pa": pa["paired"]["C-r1-Vmean"]["kl_e20"], "d_pb": pb["paired"]["C-r1-Vmean"]["gen"]["kl_pb20"],
         "d_816": pb["paired"]["C-r1-Vmean"]["gen 8-16K"]["kl_pb20"], "d25_816": R["pb"]["C1_minus_Vmean3"]["gen 8-16K"]["kl_pb20"]}
    dec1 = [c["decode_med_ratio_vs_V"] for (L, lv), cs in k4_t_groups(K).items() if lv == 1 for _, _, c in cs]
    dec4 = [c["decode_med_ratio_vs_V"] for (L, lv), cs in k4_t_groups(K).items() if lv == 4 for _, _, c in cs]
    s["dec1"], s["dec4"] = (min(dec1), max(dec1)), (min(dec4), max(dec4))
    rd = [c["decode_med_reading"] for cs in k4_t_groups(K).values() for _, _, c in cs]
    s["dec_read"] = (rd.count("faster"), rd.count("level"), rd.count("slower"), len(rd))
    f = K["f1"]; s["f1_816"] = f["f1c-minus-c1"]["P-B gen 8-16K kl_pb20"]; s["f1_pa"] = f["pa20"]["paired"]["C-f1c-Vmean"]["kl_e20"]
    return s


def k4_l_summaries():
    p = D4 / "l" / "L-analysis-VC.json"
    if not p.exists(): return {}
    return {(s["label"].split("-")[0], s["stage"], s["content"]): s for s in load(p)["summary"]}


def k4_l_table():
    """Block L on K4 (V, C) in the K3.25 run's layout; '' while it is pending."""
    S = k4_l_summaries()
    if not S: return ""
    keys = sorted({(st, c) for _, st, c in S}, key=lambda k: (["L1", "L2", "L3", "L3s"].index(k[0]),
                                                              ["prose", "code", "reasoning", "json"].index(k[1])))
    def cell(a, k):
        s = S.get((a,) + k)
        if not s: return [PENDING] * 4
        return [f"{s['stop']} / {s['cap']} / {s['terminal_loops']}", l_check(s), f"{s['decode_tok_s_median']:.1f}",
                f"{s['completion_tokens_median']:,.0f}"]
    rows = []
    for k in keys:
        n = next(S[x]["n"] for x in S if x[1:] == k)
        cap = {"L1": "8,192", "L2": "32,768", "L3": "130,048", "L3s": "130,048, 1 stream"}[k[0]]
        rows.append([k[0], cap, k[1], n] + cell("V", k) + cell("C", k))
    sub = ["finished / at cap / terminal loops", "check", "decode tok/s", "median tokens"]
    return table(["Stage", "Cap", "Content", "Requests"] + [f"vLLM: {x}" for x in sub] + [f"CuteAFD: {x}" for x in sub], rows)


def k4_l_text():
    tb = k4_l_table()
    if not tb: return "Pending: Block L was running when this folder was exported ([`l/`](l/))."
    return ("Per stage and content: requests that finished on their own, that reached the cap, and that ended in a terminal "
            "loop (U5 rule: an exact period; [`l/LOOP-RULES-VC.json`](l/LOOP-RULES-VC.json) has the copy-from-reasoning "
            "category); the content check; median decode rate and reply length. 2 requests in flight (L3s: 1); 2 seeds per "
            "prompt, 4 prompts per content: descriptive. JSON tasks are sized for thinking off and are infeasible by design "
            "where the reasoning fills the cap.\n\n" + tb)


def k4_q2_note(K):
    q2 = K["q2"]; wo = lambda k: q2["pairs"][k]["without_outlier"]["dnll_yx_documents_t"]
    det = K["pb"]["determinism"]["V-r1|V-r2"]
    c2 = load(D4 / "c2" / "c2-summary.json")["windows"]["q2-code-c2-064k"]["rows_absdnll_gt_1nat"]["V-r1|V-r2"]
    return (f"Q2 without the window `q2-code-c2-064k` (reported separately by rule): CuteAFD − vLLM launch 1 "
            f"{sgn(wo('V-r1|C-r1')['mean'])} {ci(wo('V-r1|C-r1')['ci95'])}, CuteAFD − vLLM launch 2 {sgn(wo('V-r2|C-r1')['mean'])} "
            f"{ci(wo('V-r2|C-r1')['ci95'])}. On that window vLLM differs from its own second launch on {c2} rows by more than "
            f"1 nat ([`c2/`](c2/)). Determinism: CuteAFD's two passes were byte-identical on every window (row hashes); "
            f"vLLM's two launches returned identical values on {det['windows_identical_values']} of {det['windows']} P-B "
            "windows and on none of the 25 P-A windows, though their mean KL20 there differs by less than 1e-7.")


def write_k4_docs():
    if not k4_ok(): return
    K = k4_data(); s = k4_facts_text(K); slots_ = load(D4 / "RUN.json")["slots"]
    status = "\n".join(f"- {v['title']}: {'done' if v['status'] == 'done' else '**pending**'}" for v in slots_.values())
    share = -s["f1_816"]["diff"] / s["d_816"]["B_minus_A"]
    m25 = load(D / "q/pb/pb-vs-vllm-mean3.json")
    share25 = (m25["8-16K|kl|C1"][0] - m25["8-16K|kl|F1c"][0]) / m25["8-16K|kl|C1"][0]
    text = f"""# K4 on tpurtell's vLLM fork v0.9.2 and CuteAFD v3.0.1 (2026-10-27/28)

Measurement under a protocol frozen at 2026-10-27T17:58:09-07:00 before the first comparison request
([`METHOD.md`](METHOD.md)). Checkpoint: brandonmusic's GLM-5.3-Flash-tr3-4bpw ("K4",
[`brandonmusic/GLM-5.3-Flash-tr3-4bpw`](https://huggingface.co/brandonmusic/GLM-5.3-Flash-tr3-4bpw) @ `a5fee929`;
author Local Inference Lab, Inc., [local-inference-lab.ai](https://local-inference-lab.ai/); attribution and licence in
[`NOTICE.md`](../../NOTICE.md); attribution implies no endorsement), the same bytes on both engines. Same machine, panels,
prompts and drivers as the K3.25 run ([`results/2026-10-26-cuteafd-vs-vllm`](../2026-10-26-cuteafd-vs-vllm/)).
Generated by `tools/build_readme.py` from the files in this folder.

## Slots

{status}

## In short

- **K4 against K3.25 is a quantization comparison.** On the same panels and the same top-20 definition, K4's 4-bit
  experts sit roughly half as far from the BF16 teacher as K3.25's 3.25-bit experts, on both engines (P-A KL20: vLLM
  {s['pa25_v']:.4f} → {s['pa_v']:.4f}, {s['pa_v'] / s['pa25_v']:.2f} of K3.25; CuteAFD {s['pa25_c']:.4f} →
  {s['pa_c']:.4f}, {s['pa_c'] / s['pa25_c']:.2f}). No interval is computed for the change between checkpoints; at
  {s['pa_v'] - s['pa25_v']:+.4f} (vLLM) and {s['pa_c'] - s['pa25_c']:+.4f} (CuteAFD) it is several times either engine
  difference.
- **Engines on K4: vLLM stays closer to BF16; CuteAFD is faster.** CuteAFD is further from the reference on both
  panels (P-A {sgn(s['d_pa']['B_minus_A'])}, P-B generated rows {sgn(s['d_pb']['B_minus_A'])}), most in long code reading
  (8-16K {sgn(s['d_816']['B_minus_A'])}); on human-written text at 32K-128K no NLL difference is resolved. CuteAFD
  decodes {s['dec1'][0]:.2f}-{s['dec1'][1]:.2f}x as fast at one stream and {s['dec4'][0]:.2f}-{s['dec4'][1]:.2f}x at
  four (faster in {s['dec_read'][0]} of {s['dec_read'][3]} cells, level in {s['dec_read'][1]}, slower in {s['dec_read'][2]}). Its first token comes sooner at one stream from 8K up and at 8K × 4; vLLM's comes sooner at 1K and at
  32K × 4.
- **The engine difference reads larger on K4 than on K3.25** (P-B 8-16K, top-20: {sgn(s['d_816']['B_minus_A'])}
  {ci(s['d_816']['ci95'])} against {sgn(s['d25_816']['diff'])} {ci(s['d25_816']['ci95'])}; the intervals overlap, and the
  change between checkpoints was not tested). On K4 CuteAFD converts K4's BF16 projections, head and KDA projections to
  FP8 at load; on K3.25 the projections came from the official FP8 checkpoint.
- **W8A16 prefill moves less of it on K4** (follow-up F1-K4, outside the frozen protocol): P-B 8-16K
  {sgn(s['f1_816']['diff'])} {ci(s['f1_816']['ci95'])}, about {100 * share:.0f}% of the K4 difference (on K3.25 the same
  switch moved about {100 * share25:.0f}% of its difference). On P-A, CuteAFD with W8A16 is not resolved from vLLM
  ({sgn(s['f1_pa']['B_minus_A'])} {ci(s['f1_pa']['ci95'])}). Time to first token +3-4%.
- **Long output (Block L): {"pending." if not k4_l_summaries() else "see the Block L table below (descriptive)."}**

## Precision (Block Q)

Top-20 measures: the engines' own 20 most likely ids plus the actual token, scored identically on both arms. **Not
comparable in level with the K3.25 run's full-vocabulary KL** (on P-A, KL20 reads about 0.8 of full-vocabulary KL; on
P-B generated rows, KL_pb20 keeps about 98-99% of the published coarse KL; every K3.25 difference kept its sign and
significance under the truncation). Differences are against the per-row mean of two vLLM launches; 95% intervals are
window-cluster bootstrap (P-A, P-B) or Student-t over documents (Q2). Reading rule: "differs" needs the interval to
exclude 0 and the difference to exceed vLLM's launch-to-launch difference on the same rows. Scored history: the tokens
before each scored position. KL is not comparable across panels; NLL is per tokenizer and per text.

{k4_precision_table(K)}

{k4_q2_note(K)} Files: [`q/`](q/); per-position
scores [`q/rows/`](q/rows/) and tails [`q/tails/`](q/tails/).

### K4 against K3.25, same top-20 definition

The K3.25 values are its full-vocabulary captures truncated to each engine's own top 20 before the K4 freeze
([`q/k325-top20-reference.json`](q/k325-top20-reference.json)); the panels and scored rows are the same, so the scored
history is the same as above. K3.25 vLLM: P-A one launch (its three runs agree to 1e-6), P-B the mean of three runs;
K4 vLLM: the mean of two launches. CuteAFD ran K3.25's Core-FP8 checkpoint (official FP8 projections) and converts K4's
BF16 projections at load, so its column also changes that.

{k4_quant_table(K)}

## Throughput (Block T)

Median of 3 replicates per cell, thinking on, 1,024 output tokens, every prompt unique, a distinct seed per request,
the same prompts and seeds on both engines. Grid: 1 and 4 streams at 1K-32K, 1 stream at 128K (common to the
protocol's arms; [`METHOD.md`](METHOD.md)). Readings use the declared band of ±8% (both engines' drift repeats stayed
inside it): "level" inside, "faster" or "slower" outside.

{k4_t_table(K)}

{k4_t_counts(K)} Per cell and replicate: [`t/t-compare.json`](t/t-compare.json); receipts [`t/`](t/).

## Startup (Stage 1, descriptive: one cold and one warm start)

{table(["Launch", "To /v1/models", "To ready", "Capacity at startup"], k4_startup_rows(K))}

## Follow-up F1-K4: CuteAFD with W8A16 prefill (outside the frozen protocol)

Declared after the Block Q results, before any of its requests ([`f1k4/FOLLOWUPS-K4.md`](f1k4/FOLLOWUPS-K4.md)): the K4
scoring launch with `GLM5_FLASH_FP8_PREFILL=off`, and a speed subset on serving launches in the order base, W8A16, base.

{k4_f1_tables(K)}

The speed rows are per content cell (median per request, 16 requests each).
[`f1k4/RESULTS-F1K4.md`](f1k4/RESULTS-F1K4.md) reports medians of batch medians with code and prose pooled per cell;
per content cell the direction is the same for time to first token (+3-4% everywhere) and for single-stream decode (not
slower); at four streams the per-content decode ratios fall on both sides of 1, within the ±8% Block T band.

## Long output (Block L)

{k4_l_text()}

## Files

| Path | What |
|---|---|
| `METHOD.md` | The method: arms, declared differences, order, settings, grid, metrics, reading rules, power, guardrails |
| `startup/startup.json` | Stage 1 startup timing, capacity lines and smoke checks |
| `q/` | Block Q scores (`pa20.json`, `pb20.json`, `q2-top20.json`), scorer logs, `rows/` (per position), `tails/`, the K3.25 reference on the same definitions |
| `t/` | Block T receipts (per request: seed, nonce, prompt id and hash, timings, usage, finish reason; no text), logs, `t-compare.json` |
| `f1k4/` | Follow-up F1-K4: declaration, results, scores, speed receipts |
| `c2/` | Q2 document c2: rows where vLLM differs from itself |
| `l/` | Block L: the frozen analysis and loop rules on the V and C receipts ({"pending" if not k4_l_summaries() else "done"}) |
| `NOT-PUBLISHED.json` | Per-row files with token ids behind `q/rows/`: size and sha256 |
"""
    (D4 / "README.md").write_text(text)


def k4_readme_section():
    """README.md results section for the K4 run (tables built from its published files)."""
    if not k4_ok(): return ""
    K = k4_data(); s = k4_facts_text(K); r = f"results/{K4}/"
    return f"""## Results: K4 checkpoint (2026-10-27)

Measurement under a second frozen protocol, run [`{r}`]({r}) ([`METHOD.md`]({r}METHOD.md)): brandonmusic's
GLM-5.3-Flash-tr3-4bpw ("K4", 4-bit EXL3 experts; author Local Inference Lab, Inc.; attribution in
[`NOTICE.md`](NOTICE.md)) on the same two engines, machine, panels and prompts. Its precision numbers are **top-20
measures** (KL20, KL_pb20): never read them against the full-vocabulary KL above as the same quantity.

- **K4 against K3.25 is a quantization comparison:** under the same top-20 definition K4 sits roughly half as far from
  the BF16 teacher on both engines (P-A KL20: vLLM {s['pa25_v']:.4f} → {s['pa_v']:.4f}, CuteAFD {s['pa25_c']:.4f} →
  {s['pa_c']:.4f}).
- **Engines on K4:** vLLM stays closer to BF16 (P-B 8-16K {sgn(s['d_816']['B_minus_A'])} {ci(s['d_816']['ci95'])}; it
  reads larger than K3.25's {sgn(s['d25_816']['diff'])} under the same definition, with overlapping intervals); CuteAFD decodes
  {s['dec1'][0]:.2f}-{s['dec1'][1]:.2f}x as fast at one stream. W8A16 prefill moves about
  {100 * -s['f1_816']['diff'] / s['d_816']['B_minus_A']:.0f}% of the K4 8-16K difference (follow-up F1-K4). Long output:
  {"pending" if not k4_l_summaries() else f"[`{r}README.md`]({r}README.md)"}.

{k4_precision_table(K)}

{k4_t_table(K)}

Detail, the K3.25-against-K4 table, startup and F1-K4: [`{r}README.md`]({r}README.md).
"""


def k4_status():
    if not k4_ok(): return ""
    return "\n".join(f"- K4: {v['title']}: {'done' if v['status'] == 'done' else '**pending**'}"
                     for v in load(D4 / "RUN.json")["slots"].values())


def substitutions(prefix):
    intro, secs = summary_sections(prefix)
    return {"{{STATUS}}": status_lines(), "{{S_INTRO}}": intro, "{{S_PRECISION}}": sec(secs, "Precision"),
            "{{S_THROUGHPUT}}": sec(secs, "Throughput"), "{{S_LONG}}": sec(secs, "Long output to 128K"),
            "{{S_OBSERVATIONS}}": sec(secs, "Observations"), "{{S_LIMITS}}": sec(secs, "Limits"),
            "{{Q_BUCKETS}}": q_buckets(prefix), "{{T_TABLE}}": t_table(), "{{T_COUNTS}}": t_counts(), "{{T_LINK}}": t_link(),
            "{{L_TABLE}}": l_table(), "{{L_DETAIL}}": l_table(detail=True), "{{L_NOTE}}": L_NOTE,
            "{{OTHER_RUNS}}": other_runs(), "{{K4_RESULTS}}": k4_readme_section(), "{{K4_STATUS}}": k4_status()}


def render(template, out, prefix):
    text = (ROOT / "tools" / template).read_text()
    for k, v in substitutions(prefix).items(): text = text.replace(k, v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left: raise SystemExit(f"{template}: unfilled placeholders {left}")
    out.write_text(text)


def main():
    write_t_summary(); write_l_summary(); write_k4_docs()
    render("README.template.md", ROOT / "README.md", f"results/{RUN}/")
    render("RUN-README.template.md", D / "README.md", "")
    print("wrote README.md, results/%s/README.md, l/SUMMARY.md" % RUN)


if __name__ == "__main__":
    main()
