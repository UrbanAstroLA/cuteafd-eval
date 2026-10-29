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


def k4_f1_speed_counts():
    """How many requests the F1-K4 speed receipts hold: per (input, streams, content) cell and per launch."""
    per_cell, per_launch = set(), set()
    for n in ("C-base1", "C-f1c", "C-base2"):
        cells = {}
        for b in load(D4 / "f1k4" / "t" / f"{n}.json")["batches"]:
            if b["kind"] != "measured": continue
            for g in b["groups"]:
                for r in g:
                    k = (b["length"], b["level"], b["content"]); cells[k] = cells.get(k, 0) + 1
        per_cell |= set(cells.values()); per_launch.add(sum(cells.values()))
    j = lambda xs: "/".join(str(x) for x in sorted(xs))
    return f"{j(per_cell)} requests per cell, {j(per_launch)} per launch"


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

The speed rows are per content cell (median per request, {k4_f1_speed_counts()}).
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
    """README.md results section for the K4 run: its tables, built from its published files."""
    if not k4_ok(): return ""
    K = k4_data(); r = f"results/{K4}/"
    return f"""### K4: precision (top-20 measures)

Run [`{r}`]({r}) ([`METHOD.md`]({r}METHOD.md)); brandonmusic's GLM-5.3-Flash-tr3-4bpw ("K4"; author Local Inference
Lab, Inc.; attribution in [`NOTICE.md`](NOTICE.md)). Its precision numbers are **top-20 measures** (KL20, KL_pb20):
never read them against the full-vocabulary or coarse KL above as the same quantity. CuteAFD against the per-row mean
of two vLLM launches.

{k4_precision_table(K)}

### K4: throughput

{k4_t_table(K)}

Detail, K4 against K3.25 under the same top-20 definition, startup, Block L and the follow-ups:
[`{r}README.md`]({r}README.md).
"""


def capacity_table():
    """KV capacity and request limits as each engine reported them at startup (K3.25: the run's startup lines; K4: Stage 1)."""
    if not k4_ok(): return ""
    L = k4_data()["su"]["launches"]
    return table(["", "vLLM fork", "CuteAFD"], [
        ["K3.25, KV cache at startup", f"{KV_K325[0]:,} tokens", f"{KV_K325[1]:,} tokens"],
        ["K4, KV cache at startup", f"{L['V-warm']['capacity']['pool_tokens']:,} tokens", f"{L['C-warm']['capacity']['pool_tokens']:,} tokens "
         f"(scoring launch {L['C-score']['capacity']['pool_tokens']:,})"],
        ["Requests at once", f"{L['V-warm']['capacity']['max_streams']} (`max-num-seqs`)", f"{L['C-warm']['capacity']['max_streams']} (`CONCURRENCY` default)"]])


def k4_startup_table():
    return table(["Launch", "To /v1/models", "To ready", "Capacity at startup"], k4_startup_rows(k4_data())) if k4_ok() else ""


def k4_status():
    if not k4_ok(): return ""
    return "\n".join(f"- K4: {v['title']}: {'done' if v['status'] == 'done' else '**pending**'}"
                     for k, v in load(D4 / "RUN.json")["slots"].items() if not (k == "k4e" and v["status"] != "done"))


# ------------------------------------------------------------------ canonical numbers and the front-page text
# One value per quantity, read from the published files; the README and the site's home page are both written from
# home_parts() (README: links into the repository; site: links to its pages). The choices, stated once:
#   K3.25 long-code (P-B 8-16K) difference: against the mean of the three vLLM runs (pb-vs-vllm-mean3.json).
#   K4 long-code difference: against the per-row mean of the two vLLM launches (pb20.json), a top-20 measure.
#   K3.25 "overall" precision: P-A full-vocabulary KL (V1; its three runs agree to 1e-6); P-B is always named as P-B.
#   Settings: the share of the long-code difference a setting closes is (shipped - setting) / shipped against vLLM.
#   First token at 1K etc.: the median over the content types of the cell medians (Block T, 1 stream).
#   Speed noise: NOISE_K325 and NOISE_K4 below, the same sentence wherever a band is used.

FP8_PB = 0.0216     # tpurtell's published baseline for the official FP8 model on panel P-B (quoted in q/RESULTS-Q.md)
KV_K325 = (4707515, 4726784)   # startup lines of the K3.25 run (vLLM fork, CuteAFD), as in the README's Setup table
NOISE_K325 = ("K3.25 speed noise: a repeat hours later moved the median by under 2% and single cells by up to 13%; "
              "single-cell ratios within ±10% read as level.")
NOISE_K4 = ("K4 speed noise: a ±8% band declared before the run (both engines' drift repeats stayed inside it); single-cell "
            "ratios within ±8% read as level.")
K4E = "2026-10-27-k4-vllm-cuteafd"     # K4e lives in the K4 run's f1k4/ folder
NEEDLE_RUN = "2026-10-27-long-context-pilot"


def k325_cells():
    """K3.25 Block T: {(input, content, streams): {'dec', 'agg', 'ttft': (vLLM, CuteAFD)}} (medians over replicates)."""
    rec = t_receipts(); cv, cc = t_cells(rec["V1"]), t_cells(rec["C1"])
    out = {}
    for k in cv:
        if k not in cc: continue
        g = lambda c, key: t_med(c, key, k)
        out[k] = {"dec": (g(cv, "decode_tok_s_per_stream_median"), g(cc, "decode_tok_s_per_stream_median")),
                  "agg": (g(cv, "aggregate_tok_s"), g(cc, "aggregate_tok_s")), "ttft": (g(cv, "ttft_median_s"), g(cc, "ttft_median_s"))}
    return out


def k4_cells(K):
    """K4 Block T from t-compare.json, the same layout plus the published per-cell readings and ratios."""
    import ast
    out = {}
    for k, c in K["tc"]["cells"].items():
        L, content, lv = ast.literal_eval(k)
        out[(L, content, lv)] = {"dec": (c["V"]["decode_med"], c["C"]["decode_med"]), "agg": (c["V"]["aggregate"], c["C"]["aggregate"]),
                                 "ttft": (c["V"]["ttft_med"], c["C"]["ttft_med"]),
                                 "read": {"dec": c["C"]["decode_med_reading"], "agg": c["C"]["aggregate_reading"]},
                                 "ratio": {"dec": c["C"]["decode_med_ratio_vs_V"], "agg": c["C"]["aggregate_ratio_vs_V"]}}
    return out


def f1_speed():
    """K3.25 F1 arms: (TTFT ratio median, min, max, decode ratio median) over the 8 cells, each arm ÷ F1-base."""
    sp = load(D / "f1/F1-RESULTS.json")["speed"]
    return {a: (statistics.median(v["ttft_median_s"] for v in sp[a].values()), min(v["ttft_median_s"] for v in sp[a].values()),
                max(v["ttft_median_s"] for v in sp[a].values()), statistics.median(v["decode_tok_s_per_stream_median"] for v in sp[a].values()),
                min(v["decode_tok_s_per_stream_median"] for v in sp[a].values()))
            for a in sp}


def k4_settings(K):
    """{arm: {'pa_c', 'pb8_c', 'pa_v', 'pb_v', 'pb8_v': (diff, lo, hi) or None}} from the published K4 follow-up summaries."""
    f = D4 / "f1k4"
    b = load(f / "score-b" / "f1b-summary.json"); c = load(f / "score-c" / "f1c2-summary.json"); d = load(f / "score-d" / "f1d2-summary.json")
    t = lambda x: (x["diff"], x["ci95"][0], x["ci95"][1]) if x else None
    p = lambda x: (x["B_minus_A"], x["ci95"][0], x["ci95"][1])
    F1 = K["f1"]; dd = F1["f1c-minus-c1"]
    out = {"shipped": {"pa_v": p(K["pa"]["paired"]["C-r1-Vmean"]["kl_e20"]), "pb_v": p(K["pb"]["paired"]["C-r1-Vmean"]["gen"]["kl_pb20"]),
                       "pb8_v": p(K["pb"]["paired"]["C-r1-Vmean"]["gen 8-16K"]["kl_pb20"])},
           "f1c": {"pa_c": t(dd["P-A kl_e20"]), "pb8_c": t(dd["P-B gen 8-16K kl_pb20"]), "pa_v": p(F1["pa20"]["paired"]["C-f1c-Vmean"]["kl_e20"]),
                   "pb_v": p(F1["pb20"]["paired"]["C-f1c-Vmean"]["gen"]["kl_pb20"]), "pb8_v": p(F1["pb20"]["paired"]["C-f1c-Vmean"]["gen 8-16K"]["kl_pb20"])}}
    for a in ("amax", "best", "head16", "kda16", "all16", "nospec"):
        s = b[f"C-{a}"]; out[a] = {k: t(s.get(k)) for k in ("pa_c", "pb8_c", "pa_v", "pb_v", "pb8_v")}
    s = c["C-w16amax"]; out["w16amax"] = {k: t(s.get(k)) for k in ("pa_c", "pb8_c", "pa_v", "pb_v", "pb8_v")}
    s = d["C-w16best"]; out["w16best"] = {k: t(s.get(k)) for k in ("pa_c", "pb8_c", "pa_v", "pb_v", "pb8_v")}
    return out


def t_request_cells(path):
    """{(input, streams, content): (median decode tok/s, median TTFT s, requests)} over every measured request of a receipt."""
    out = {}
    for bt in load(path)["batches"]:
        if bt["kind"] != "measured": continue
        for g in bt["groups"]:
            for r in g:
                c = out.setdefault((bt["length"], bt["level"], bt["content"]), {"d": [], "t": []})
                c["d"].append(r["decode_tok_s"]); c["t"].append(r["ttft_s"])
    return {k: (statistics.median(v["d"]), statistics.median(v["t"]), len(v["d"])) for k, v in out.items()}


def k4_setting_speed():
    """Per content cell: median per request; arm ÷ the mean of its two bracketing as-shipped launches (the method of the
    F1-K4 speed table). {arm: (ttft median, min, max, decode min, decode max, cells, {cell: (base ttft, arm ttft)})}."""
    res = {}
    for arm, f, b1, b2 in (("f1c", "C-f1c", "C-base1", "C-base2"), ("w16amax", "C-c-w16amax", "C-c-base1", "C-c-base2"),
                           ("w16best", "C-d-w16best", "C-d-base1", "C-d-base2")):
        A, X1, X2 = (t_request_cells(D4 / "f1k4" / "t" / f"{n}.json") for n in (f, b1, b2))
        tt = [A[k][1] / ((X1[k][1] + X2[k][1]) / 2) for k in sorted(A)]
        de = [A[k][0] / ((X1[k][0] + X2[k][0]) / 2) for k in sorted(A)]
        ab = {k: ((X1[k][1] + X2[k][1]) / 2, A[k][1]) for k in A}
        res[arm] = (statistics.median(tt), min(tt), max(tt), min(de), max(de), len(tt), ab)
    return res


def f1_abs_ttft(length, content):
    """K3.25 F1 speed subset, one cell (1 stream): median TTFT over replicates, F1-base and W8A16 (F1c)."""
    def med(n):
        xs = [b["summary"]["ttft_median_s"] for b in load(D / f"f1/speed-F1-{n}.json")["batches"]
              if b["kind"] == "measured" and b["level"] == 1 and b["length"] == length and b["content"] == content]
        return statistics.median(xs)
    return med("base"), med("f1c")


def needle_data():
    d = ROOT / "results" / NEEDLE_RUN
    if not (d / "V1-pilot.json").exists(): return None
    V, C = load(d / "V1-pilot.json")["requests"], load(d / "C1-pilot.json")["requests"]
    ok = lambda r: r["finish_reason"] == "stop" and (r["score"].get("found") or (r["score"].get("all_found") and r["score"].get("in_order")))
    return {"V": V, "C": C, "all_ok": all(ok(r) for r in V + C), "n": len(V),
            "t1m": ([r["ttft_s"] for r in V if r["content_tokens"] == 1000000], [r["ttft_s"] for r in C if r["content_tokens"] == 1000000])}


def k4e_data():
    """Follow-up K4e (W8A16 + amax under the full Block T grid and Block L), or None while it is not published."""
    f = D4 / "f1k4"
    need = [f / "t" / f"{n}.json" for n in ("C-e-base1", "C-w16amax-r1", "C-e-base2")] + \
           [f / "l" / f"C-w16amax-r1-{s}.json" for s in ("L1", "L2", "L3", "L3s")]
    if not all(p.exists() for p in need): return None
    E = {"T": {n: load(f / "t" / f"{n}.json") for n in ("C-e-base1", "C-w16amax-r1", "C-e-base2")},
         "L": {s: load(f / "l" / f"C-w16amax-r1-{s}.json") for s in ("L1", "L2", "L3", "L3s")}}
    a = f / "l" / "L-analysis-K4e.json"
    E["analysis"] = {(s["label"], s["stage"], s["content"]): s for s in load(a)["summary"]} if a.exists() else None
    return E


_CANON = {}


def canon():
    """Every number the front page uses, from the published files (computed once per process)."""
    if _CANON: return _CANON
    q = D / "q"; N = _CANON
    pa = load(q / "pa/pa-pair-V1-vs-C1.json")["overall"]["kl"]
    N["pa"] = {"v": pa["A"], "c": pa["B"], "d": pa["B_minus_A"], "ci": pa["ci95"]}
    gen = lambda a: load(q / f"pb/pb-{a}.json")["summary"]["gen"]
    vr = [gen(a) for a in ("V1", "V1r", "V2")]; c1 = gen("C1")
    m3 = load(q / "pb/pb-vs-vllm-mean3.json")
    f1 = load(D / "f1/F1-RESULTS.json")["precision"]
    N["pb"] = {"v": statistics.mean(r["overall"]["kl"]["value"] for r in vr), "c": c1["overall"]["kl"]["value"],
               "d": m3["all|kl|C1"][0], "ci": m3["all|kl|C1"][1:], "w16": f1["f1c"]["all"]["kl"], "d_w16": m3["all|kl|F1c"][0],
               "t1": m3["all|top1|C1"]}
    N["pb8"] = {"v": statistics.mean(r["by_bucket"]["8-16K"]["kl"]["value"] for r in vr), "c": c1["by_bucket"]["8-16K"]["kl"]["value"],
                "d": m3["8-16K|kl|C1"][0], "ci": m3["8-16K|kl|C1"][1:], "w16": f1["f1c"]["8-16K"]["kl"],
                "d_w16": m3["8-16K|kl|F1c"][0], "ci_w16": m3["8-16K|kl|F1c"][1:], "d_all3": m3["8-16K|kl|F1d"][0], "ci_all3": m3["8-16K|kl|F1d"][1:]}
    N["pb8"]["share_w16"] = (N["pb8"]["d"] - N["pb8"]["d_w16"]) / N["pb8"]["d"]
    if f"{FP8_PB:.4f}" not in (q / "RESULTS-Q.md").read_text(): raise SystemExit("FP8 baseline no longer quoted in q/RESULTS-Q.md")
    N["fp8"] = FP8_PB
    N["sp_f1"] = f1_speed(); N["f1_8k"] = f1_abs_ttft(8192, "prose")
    c3 = k325_cells(); N["c3"] = c3
    K = k4_data(); N["K"] = K; s = k4_facts_text(K); N["s4"] = s; c4 = k4_cells(K); N["c4"] = c4
    S4 = k4_settings(K); N["S4"] = S4; sp4 = k4_setting_speed(); N["sp4"] = sp4
    N["k4_pb8"] = {"v": s["d_816"]["A"], "c": s["d_816"]["B"], "d": s["d_816"]["B_minus_A"], "ci": s["d_816"]["ci95"],
                   "d_w16": S4["f1c"]["pb8_v"][0], "d_w16amax": S4["w16amax"]["pb8_v"][0], "ci_w16amax": S4["w16amax"]["pb8_v"][1:],
                   "d_w16best": S4["w16best"]["pb8_v"][0]}
    k = N["k4_pb8"]
    k["share_w16"] = -S4["f1c"]["pb8_c"][0] / k["d"]                 # F1-K4's direct pair, as RESULTS-F1K4.md reads it
    k["share_w16amax"] = -S4["w16amax"]["pb8_c"][0] / k["d"]; k["share_w16best"] = -S4["w16best"]["pb8_c"][0] / k["d"]
    N["k4_pb"] = {"v": s["d_pb"]["A"], "c": s["d_pb"]["B"], "d": s["d_pb"]["B_minus_A"], "ci": s["d_pb"]["ci95"],
                  "d_w16amax": S4["w16amax"]["pb_v"][0], "ci_w16amax": S4["w16amax"]["pb_v"][1:]}
    N["k4_pa"] = {"v": s["pa_v"], "c": s["pa_c"], "d": s["d_pa"]["B_minus_A"], "ci": s["d_pa"]["ci95"], "v25": s["pa25_v"], "c25": s["pa25_c"],
                  "d_w16amax": S4["w16amax"]["pa_v"]}
    N["k4_32k"] = sp4["w16amax"][6][(32768, 1, "code")]      # the 32K code cell (as shipped 7.38 s, as in the speed table)
    def rng(cells, sel, m, i):
        xs = [c[m][i] for kk, c in cells.items() if sel(kk)]; return (min(xs), max(xs))
    def tt(cells, L, i): return statistics.median(c["ttft"][i] for kk, c in cells.items() if kk[0] == L and kk[2] == 1)
    for key, cells in (("k325", c3), ("k4", c4)):
        N[key] = {"dec1": [rng(cells, lambda kk: kk[2] == 1, "dec", i) for i in (0, 1)],
                  "dec4": [rng(cells, lambda kk: kk[2] == 4 and kk[0] <= 8192, "dec", i) for i in (0, 1)],
                  "ttft": {L: (tt(cells, L, 0), tt(cells, L, 1)) for L in (1024, 8192, 32768, 131072)}}
    N["k325"]["agg8_1k"] = [rng(c3, lambda kk: kk[0] == 1024 and kk[2] == 8, "agg", i) for i in (0, 1)]
    N["k325"]["agg16_1k"] = [rng(c3, lambda kk: kk[0] == 1024 and kk[2] == 16, "agg", i) for i in (0, 1)]
    N["k325"]["agg16_32k"] = [rng(c3, lambda kk: kk[0] == 32768 and kk[2] == 16, "agg", i) for i in (0, 1)]
    for lv in (8, 16):
        N["k325"][f"ttft_1k{lv}"] = tuple(statistics.median(c["ttft"][i] for kk, c in c3.items() if kk[0] == 1024 and kk[2] == lv) for i in (0, 1))
    N["k325"]["ttft_32k16"] = (statistics.median(c["ttft"][0] for kk, c in c3.items() if kk[0] == 32768 and kk[2] == 16),
                               statistics.median(c["ttft"][1] for kk, c in c3.items() if kk[0] == 32768 and kk[2] == 16))
    r1 = [c["read"]["dec"] for kk, c in c4.items() if kk[2] == 1]
    N["k4"]["read1"] = (r1.count("faster"), r1.count("level"), len(r1))
    su = load(ROOT / "results/2026-10-27-vllm-startup-cache/startup.json")["runs"]
    N["startup"] = {"v_cold": su[0]["ready_s"], "v_warm": su[1]["ready_s"], "c": su[2]["ready_s"]}
    L4s = K["su"]["launches"]
    N["k4_startup"] = {n: L4s[n]["t_ready_s"] for n in ("V-cold", "V-warm", "C-cold", "C-warm")}
    N["k4_kv"] = (L4s["V-warm"]["capacity"]["pool_tokens"], L4s["C-warm"]["capacity"]["pool_tokens"])
    N["kv"] = KV_K325
    tr = t_receipts()
    def cached(d):
        b = [x for x in d["batches"] if x["kind"] == "cached"]; return b[0]["summary"]["ttft_median_s"]
    N["cached"] = (cached(tr["V1"]), cached(tr["C1"]))
    N["L"] = l_summaries(); N["L4"] = k4_l_summaries()
    N["needle"] = needle_data(); N["k4e"] = k4e_data()
    return N


def f4s(x): return f"{x:+.4f}".replace("-", "−")
def f2s(x): return f"{x:+.2f}".replace("-", "−")
def pct1(r): return f"{100 * (r - 1):+.1f}%".replace("-", "−")
def secs(x): return f"{x:.2f} s" if x < 10 else f"{x:.1f} s"
def tok_rng(r): return f"{r[0]:.0f}-{r[1]:.0f}"


def home_parts(site):
    """The front page, as markdown pieces. site=True: links to the site's pages; False: links into the repository."""
    N = canon(); K = N["K"]
    def lk(text, page, repo): return f"[{text}]({page if site else repo})"
    R3, R4 = f"results/{RUN}/", f"results/{K4}/"
    pa, pb, pb8, k8, kpa = N["pa"], N["pb"], N["pb8"], N["k4_pb8"], N["k4_pa"]
    a3, a4 = N["k325"], N["k4"]
    L, L4 = N["L"], N["L4"]
    vc, cc = L[("V1", "L3", "code")], L[("C1", "L3", "code")]; vm, cm = L[("V1", "L3", "reasoning")], L[("C1", "L3", "reasoning")]
    vc4, cc4 = L4[("V", "L3", "code")], L4[("C", "L3", "code")]; vm4, cm4 = L4[("V", "L3", "reasoning")], L4[("C", "L3", "reasoning")]
    nd = N["needle"]; su = N["startup"]
    w16_8k = N["f1_8k"]; k32 = N["k4_32k"]
    P = {}
    P["intro"] = f"""Two inference engines by the same author, **tpurtell** (`wrldsuksgo2mars` on Hugging Face), on the same model
and machine:

- **CuteAFD** ([tpurtell/cuteafd](https://github.com/tpurtell/cuteafd)), his own runtime, built for attention/FFN
  disaggregation (AFD): attention and the expert (feed-forward) layers run as separate workers, so experts can sit on
  other machines; here, on two GPUs, they stay local.
- **His vLLM fork** ([tpurtell/glm-5.3-flash-ext3-2x-rtx](https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx)), his
  vLLM-based engine for this model on two RTX GPUs.

The model is GLM-5.3-Flash on two RTX PRO 6000 Blackwell Max-Q GPUs at 300 W, in two quantized checkpoints: **K3.25**
(tpurtell's mixed 3.25-bit EXL3 experts) and **K4** (brandonmusic's 4-bit EXL3 experts, Local Inference Lab). The
questions: how close each engine stays to the original BF16 model, how fast it is, and how to set it up.

Results as of 2026-10-28; versions tested: CuteAFD v3.0.1, vLLM fork v0.9.2. Measured by Michael M (UrbanAstroLA)."""
    needle_txt = ""
    if nd:
        needle_txt = (f" Needles in prompts of 256K to 1M tokens (K3.25): {'all found' if nd['all_ok'] else 'not all found'} on both "
                      f"(exploratory); at 1M the first token took {min(nd['t1m'][0]):.0f} s on the vLLM fork and {min(nd['t1m'][1]):.0f} s on CuteAFD.")
    c2v, c2c = L[("V1", "L2", "code")], L[("C1", "L2", "code")]; c2v4, c2c4 = L4[("V", "L2", "code")], L4[("C", "L2", "code")]
    r3 = vc["completion_tokens_median"] and cc["completion_tokens_median"] / vc["completion_tokens_median"]
    r4 = cc4["completion_tokens_median"] / vc4["completion_tokens_median"]
    t8, t16 = N["k325"]["ttft_1k8"], N["k325"]["ttft_1k16"]
    P["findings"] = "\n".join([
        f"- **Precision: the quantization matters more than the engine.** On K3.25, KL from the BF16 model (teacher panel) "
        f"is {pa['v']:.4f} on the vLLM fork and {pa['c']:.4f} on CuteAFD. The largest engine difference is on long code "
        f"(8-16K-token prompts): CuteAFD {f4s(pb8['d'])} further on K3.25, {f4s(k8['d'])} on K4 (top-20 measure). " +
        lk("Precision", "precision.html", R3 + "q/RESULTS-Q.md"),
        f"- **Speed: CuteAFD generates faster; under concurrency the vLLM fork's first tokens come sooner.** One stream: "
        f"{tok_rng(a3['dec1'][0])} tokens/s on the vLLM fork, {tok_rng(a3['dec1'][1])} on CuteAFD (K3.25). First token, one "
        f"request: 1K prompt {secs(a3['ttft'][1024][0])} and {secs(a3['ttft'][1024][1])}, 128K prompt {secs(a3['ttft'][131072][0])} "
        f"and {secs(a3['ttft'][131072][1])}. With 4-16 requests at once the vLLM fork's first tokens come sooner in most cells, "
        f"while tokens per second are level or ahead on CuteAFD except at 1K × 8. " + lk("Speed", "speed.html", R3 + "t/T-SUMMARY.md"),
        f"- **A CuteAFD setting trades about 4% first-token time for precision.** W8A16 prefill closes about "
        f"{100 * pb8['share_w16']:.0f}% of the long-code difference on K3.25 (8K prose prompt {w16_8k[0]:.3f} → {w16_8k[1]:.3f} s); "
        f"W8A16 prefill with the amax scale rule closes about two thirds on K4 (32K code prompt {k32[0]:.2f} → {k32[1]:.2f} s), "
        f"decode level. " + lk("Settings", "settings.html", R4 + "f1k4/RESULTS-F1K4b.md"),
        f"- **Long tasks: the same at the longest cap; CuteAFD finished more code at 32K.** At the 128K cap code passed every "
        f"test in {vc['all_pass']}/{vc['n']} (K3.25) and {vc4['all_pass']}/{vc4['n']} (K4) on both engines, math {vm['correct']}/{vm['n']}. "
        f"At the 32K cap CuteAFD finished {c2c['stop']}/8 (K3.25) and {c2c4['stop']}/8 (K4) code tasks, the vLLM fork "
        f"{c2v['stop']}/8 and {c2v4['stop']}/8, consistent with CuteAFD's shorter code replies ({r3:.2f}x and {r4:.2f}x the vLLM "
        f"fork's median length at 128K); descriptive, n = 8." + needle_txt + " " + lk("Long tasks", "long-tasks.html", R3 + "l/SUMMARY.md"),
        f"- **Practical.** Ready to serve in {su['v_warm']} s on the vLLM fork (JIT caches kept) and {su['c']} s on CuteAFD. A "
        f"repeated 8K prompt: {N['cached'][0]:.2f} s on the vLLM fork, {N['cached'][1]:.3f} s from CuteAFD's prefix cache. Only "
        f"CuteAFD honours \"thinking off\". K4 KV cache: {N['k4_kv'][0]:,} tokens on the vLLM fork, {N['k4_kv'][1]:,} on CuteAFD. " +
        lk("Running it", "running.html", "#running-it-observations-in-detail")])
    P["bars"] = [   # (panel, [(label, value, kind)]); kind: v vLLM fork, c CuteAFD, cs CuteAFD setting, r reference
        ("K3.25 · BF16 teacher panel (P-A) · full-vocabulary KL",
         [("vLLM fork", pa["v"], "v"), ("CuteAFD", pa["c"], "c")]),
        ("K3.25 · tpurtell's fidelity set (P-B), all generated positions · coarse KL",
         [("Official FP8 model (tpurtell's baseline)", N["fp8"], "r"), ("vLLM fork", pb["v"], "v"), ("CuteAFD", pb["c"], "c"),
          ("CuteAFD, W8A16 prefill", pb["w16"], "cs")]),
        ("K3.25 · the same set, 8-16K long code · coarse KL",
         [("vLLM fork", pb8["v"], "v"), ("CuteAFD", pb8["c"], "c"), ("CuteAFD, W8A16 prefill", pb8["w16"], "cs")]),
        ("K3.25 and K4 · BF16 teacher panel (P-A) · top-20 KL (KL20)",
         [("K3.25, vLLM fork", kpa["v25"], "v"), ("K3.25, CuteAFD", kpa["c25"], "c"), ("K4, vLLM fork", kpa["v"], "v"),
          ("K4, CuteAFD", kpa["c"], "c")])]
    P["bars_table"] = table(["Panel and measure", "Row", "KL from BF16"],
                            [[p if i == 0 else "", lab, f"{v:.4f}"] for p, rows in P["bars"] for i, (lab, v, _) in enumerate(rows)])
    P["matters"] = f"""KL is how far an engine's next-token probabilities are from the BF16 model's on the same text (0 is
identical, lower is closer; units: nats).

- **The quantization's own distance dwarfs the engine difference.** On tpurtell's set his official FP8 model scores
  {N['fp8']:.4f}, the 3.25-bit checkpoint {pb['v']:.4f} (vLLM fork) and {pb['c']:.4f} (CuteAFD): the engine difference is
  {100 * pb['d'] / pb['v']:.0f}% of the vLLM fork's distance ({100 * pb8['d'] / pb8['v']:.0f}% on long code). K4 roughly halves the distance on both.
- **tpurtell's bar** counts a paired change below 0.005 KL or 0.5 top-1 points as within it (defined for changes to one
  engine; applied here by analogy). K3.25 overall is inside on KL ({f4s(pb['d'])}, interval to {f4s(pb['ci'][1])}), not on
  top-1 ({f2s(100 * pb['t1'][0])} points, to {f2s(100 * pb['t1'][1])}); long code is not shown inside on either checkpoint
  ({f4s(pb8['d'])}, {f4s(k8['d'])}); K4 with W8A16 prefill + amax reads {f4s(k8['d_w16amax'])} (to {f4s(k8['ci_w16amax'][1])}).
- **On tasks**, code and math checks at the 128K cap{' and the needle checks' if nd else ''} came out the same on both engines.
- **Not measured:** the distance from BF16 beyond 14.4K tokens (no reference exists there) and on the decode path
  (scoring runs prompts through prefill)."""
    sp3, sp4 = N["sp_f1"], N["sp4"]
    a16, a32 = N["k325"]["agg16_1k"], N["k325"]["agg16_32k"]
    P["pick"] = table(["Workload", "The data shows", "Key numbers (vLLM fork first, CuteAFD second)", "Evidence"], [
        ["Long code (8-16K), closest to BF16", "vLLM fork closer to BF16",
         f"KL at 8-16K: {pb8['v']:.4f} vs {pb8['c']:.4f} (K3.25); {k8['v']:.4f} vs {k8['c']:.4f} (K4, top-20)",
         lk("Precision", "precision.html#long-code", R3 + "q/RESULTS-Q.md")],
        ["CuteAFD on K3.25, closer to BF16", f"W8A16 prefill closes about {100 * pb8['share_w16']:.0f}% of the difference",
         f"difference {f4s(pb8['d'])} → {f4s(pb8['d_w16'])}; first token {pct1(sp3['f1c'][1])} to {pct1(sp3['f1c'][2])} per cell",
         lk("Settings", "settings.html", R3 + "f1/RESULTS-F1.md")],
        ["CuteAFD on K4, two RTX GPUs", "W8A16 prefill + amax scale rule closes about two thirds; the BF16 options do not fit",
         f"difference {f4s(k8['d'])} → {f4s(k8['d_w16amax'])}; first token {pct1(sp4['w16amax'][1])} to {pct1(sp4['w16amax'][2])} per cell",
         lk("Settings", "settings.html", R4 + "f1k4/RESULTS-F1K4b.md")],
        ["One request at a time", "CuteAFD generates faster", f"{tok_rng(a3['dec1'][0])} vs {tok_rng(a3['dec1'][1])} tok/s",
         lk("Speed", "speed.html", R3 + "t/T-SUMMARY.md")],
        ["Long prompts, one at a time", "CuteAFD's first token sooner", f"128K: {secs(a3['ttft'][131072][0])} vs {secs(a3['ttft'][131072][1])}",
         lk("Speed", "speed.html", R3 + "t/T-SUMMARY.md")],
        ["Short prompts, many at once", "vLLM fork's first token sooner; tokens/s higher on the vLLM fork at 1K × 8, level at 1K × 16",
         f"1K × 8: {secs(t8[0])} vs {secs(t8[1])}, {tok_rng(N['k325']['agg8_1k'][0])} vs {tok_rng(N['k325']['agg8_1k'][1])} tok/s; "
         f"1K × 16: {secs(t16[0])} vs {secs(t16[1])}, {tok_rng(a16[0])} vs {tok_rng(a16[1])} tok/s",
         lk("Speed", "speed.html", R3 + "t/T-SUMMARY.md")],
        ["Many long prompts at once", "vLLM fork's first tokens sooner; CuteAFD's tokens/s higher",
         f"32K × 16: {N['k325']['ttft_32k16'][0]:.0f} vs {N['k325']['ttft_32k16'][1]:.0f} s, {tok_rng(a32[0])} vs {tok_rng(a32[1])} tok/s",
         lk("Speed", "speed.html#caveats", R3 + "t/CAVEATS.md")],
        ["Repeated long prefix", "CuteAFD reuses it", f"8K repeated: {N['cached'][0]:.2f} vs {N['cached'][1]:.3f} s",
         lk("Running it", "running.html#prefix-cache", R3 + "f2/RESULTS-F2.md")],
        ["Long replies (to 128K)", "same code and math at the 128K cap; CuteAFD finished more code at 32K",
         f"128K code: {vc['all_pass']}/8 vs {cc['all_pass']}/8; 32K code finished: {c2v['stop']}/8 vs {c2c['stop']}/8 (K3.25)",
         lk("Long tasks", "long-tasks.html", R3 + "l/SUMMARY.md")],
        ["Switching models often", "CuteAFD starts faster", f"{su['v_warm']} vs {su['c']} s",
         lk("Running it", "running.html#startup", "results/2026-10-27-vllm-startup-cache/")],
        ["Many long contexts at once (K4)", "vLLM fork holds about 3x the KV cache", f"{N['k4_kv'][0]:,} vs {N['k4_kv'][1]:,} tokens",
         lk("Running it", "running.html#capacity", R4 + "startup/startup.json")],
        ["K4 on CuteAFD, two RTX GPUs", "context up to 262,144 tokens (MAX_CONTEXT_TOKENS); the 256K-1M needle checks ran on K3.25",
         "262,144 tokens", lk("Running it", "running.html#capacity", R4 + "METHOD.md")]])
    cfg = lambda rel: "\n".join(l for l in (ROOT / rel).read_text().splitlines() if l.strip() and not l.lstrip().startswith("#"))
    P["settings"] = f"""The configurations measured here, as files you can copy; with each, what it measured. **Measured, not a
recommendation.** The exact files are in {lk('repro/', 'reproduce.html', 'repro/')}; checkpoints download as in
{lk('Reproduce, step 1', 'reproduce.html#1-checkpoints-and-images', 'repro/REPRODUCE.md')}.

**vLLM fork v0.9.2, both checkpoints.** Startup {su['v_cold']} → {su['v_warm']} s with the JIT caches kept (K3.25).

```bash
# the launcher: tpurtell's vLLM fork repository at tag v0.9.0; its start.sh runs the v0.9.2 image pinned below
git clone https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx && cd glm-5.3-flash-ext3-2x-rtx && git checkout v0.9.0
export IMAGE=ghcr.io/tpurtell/glm-5.3-flash-exl3-4bpw-2x-rtx@sha256:ea0430aa772e8cedfef1cdf80c30f4962ba43bb0991ac329950067ba1375f3e2
export MODEL_PROFILE=k325                # k4 for the K4 checkpoint
export GPU_MEMORY_UTILIZATION=0.95       # the default 0.97 does not start beside a desktop session
export PORT=127.0.0.1:8001               # the default publishes port 8001 on every interface
# keep the JIT caches inside the cache directory the container already keeps between starts
export DEBUG_ENV="TILELANG_CACHE_DIR=/root/.cache/tilelang
  TRITON_CACHE_DIR=/root/.cache/triton
  TORCHINDUCTOR_CACHE_DIR=/root/.cache/torchinductor
  CUDA_CACHE_PATH=/root/.cache/nv/ComputeCache"
./start.sh
```

**CuteAFD v3.0.1: the launcher.** On a host without `/dev/infiniband`, apply the guard in
{lk('repro/cuteafd/patches/', 'reproduce.html#4-serve-cuteafd-arms-c1-and-c0', 'repro/cuteafd/patches/')} first.

```bash
git clone https://github.com/tpurtell/cuteafd && cd cuteafd && git checkout v3.0.1
mkdir -p local                           # save the config below as local/<name>.config, then:
./run.sh --config local/<name>.config --restart
```

**CuteAFD on K3.25, as shipped** (`glm53-flash-exl3-k3.25-core-fp8-2rtx.config`; `ADDR`, `MAX_OUTPUT_TOKENS` and `USAGE`
are the local settings: the launcher defaults are `0.0.0.0` under host networking, a 4,096-token output limit, and
request logging on).

```bash
{cfg('repro/cuteafd/configs/glm53-flash-exl3-k3.25-core-fp8-2rtx.config')}
```

**With the measured setting, W8A16 prefill:** append the line below. Measured: long-code difference from the vLLM fork
{f4s(pb8['d'])} → {f4s(pb8['d_w16'])}, first token {pct1(sp3['f1c'][1])} to {pct1(sp3['f1c'][2])} per cell, decode
{sp3['f1c'][3]:.2f}x (scoring launches, follow-up F1).

```bash
GLM5_FLASH_FP8_PREFILL=off
```

**CuteAFD on K4, as shipped** (`glm53-flash-exl3-k4-2rtx.config`; `MAX_CONTEXT_TOKENS=262144` is needed on two RTX GPUs,
where the planner refuses K4 at its default). Measured: KV pool {N['k4_kv'][1]:,} tokens, 16 requests at once.

```bash
{cfg('repro/k4/cuteafd/glm53-flash-exl3-k4-2rtx.config')}
```

**With the measured setting, W8A16 prefill + amax scale rule:** append the two lines below. Measured: long-code
difference {f4s(k8['d'])} → {f4s(k8['d_w16amax'])}, teacher panel no longer resolved, first token {pct1(sp4['w16amax'][1])} to
{pct1(sp4['w16amax'][2])} per cell, decode level, the same memory.

```bash
GLM5_FLASH_FP8_PREFILL=off
FP8_SCALES=amax
```"""
    P["speed"] = table(["", "K3.25: vLLM fork", "K3.25: CuteAFD", "K4: vLLM fork", "K4: CuteAFD"], [
        ["Decode, 1 stream, tok/s", tok_rng(a3["dec1"][0]), tok_rng(a3["dec1"][1]), tok_rng(a4["dec1"][0]), tok_rng(a4["dec1"][1])],
        ["Decode per stream, 4 streams (1K-8K), tok/s", tok_rng(a3["dec4"][0]), tok_rng(a3["dec4"][1]), tok_rng(a4["dec4"][0]), tok_rng(a4["dec4"][1])]] +
        [[f"First token, {L // 1024}K", secs(a3["ttft"][L][0]), secs(a3["ttft"][L][1]), secs(a4["ttft"][L][0]), secs(a4["ttft"][L][1])]
         for L in (1024, 8192, 32768, 131072)] +
        [["Startup to the ready line", f"{su['v_warm']} s ({su['v_cold']} s without JIT caches)", f"{su['c']} s",
          f"{N['k4_startup']['V-warm']:.0f} s warm, {N['k4_startup']['V-cold']:.0f} s cold",
          f"{N['k4_startup']['C-warm']:.0f} s warm, {N['k4_startup']['C-cold']:.0f} s cold"],
         ["KV cache, tokens", f"{N['kv'][0]:,}", f"{N['kv'][1]:,}", f"{N['k4_kv'][0]:,}", f"{N['k4_kv'][1]:,}"]])
    P["speed_note"] = ("Decode: range over content types and 1K-128K prompts; first token: median over content types, one "
                       "request at a time; 1,024 tokens per request. Startup and KV cache: " +
                       lk("Running it", "running.html#startup", "#startup") + ". Every speed cell: " + lk("Speed", "speed.html", R3 + "t/T-SUMMARY.md") + ".")
    P["sure"] = f"""- **K3.25:** frozen protocol. After the runs, a separate reviewer who did not run the measurements re-ran the
  scorers and checked the claims against the receipts; its corrections are applied ({lk('Review', 'audit.html', R3 + 'AUDIT-2026-10-27.md')}).
  It covered the precision and speed blocks and the vLLM fork's long output; it did **not** cover CuteAFD's long output,
  the follow-ups F1-F3 (it saw their designs and the F1 baseline speed run), the drift repeats, the startup measurement
  or the needle pilot. CuteAFD is paired with three vLLM runs from two launches. Thin: 8 long replies per content type,
  six long documents. {NOISE_K325}
- **K4:** frozen protocol; **no separate review** of any part of it, its settings follow-ups included. CuteAFD is
  paired with two vLLM launches. {NOISE_K4}
- **One machine:** two RTX PRO 6000 Blackwell Max-Q cards at 300 W, with a desktop session using about 2 GB on GPU 1;
  speed on other power limits or cards was not measured."""
    P["glossary"] = [
        ("AFD", "attention/FFN disaggregation: attention and the expert layers run as separate workers."),
        ("BF16 model", "the original, unquantized model; the precision reference."),
        ("K3.25, K4", "the two quantized checkpoints (3.25-bit and 4-bit EXL3 experts)."),
        ("FP8", "8-bit floating point, CuteAFD's format for the other weights."),
        ("KL", "distance between next-token distributions, in nats; 0 is identical."),
        ("Coarse KL, KL20, KL_pb20, KL20n", "KL over the reference's top 1,024 tokens plus the rest (tpurtell's rule); over each "
         "engine's top 20 (K4, teacher panel); the top-20 form of tpurtell's rule (K4, fidelity set); top 20 shared by two engines "
         "(K4, long texts)."),
        ("Top-1", "how often the most likely next token matches the reference's."),
        ("P-A, P-B, Q2", "the text sets: BF16 teacher texts (2K tokens), tpurtell's fidelity set (to 14.4K), six long documents."),
        ("Long code (8-16K)", "P-B's longest prompts, all code reading."),
        ("95% interval, resolved", "a difference's likely range; resolved if it excludes zero."),
        ("Level", "a speed ratio inside the noise band: not a difference."),
        ("Prefill, decode", "reading the prompt; generating tokens."),
        ("First token", "time until the first generated token."),
        ("Stream", "one request in flight."),
        ("W8A8, W8A16", "CuteAFD prefill with 8-bit or 16-bit activations."),
        ("Scale rule", "how CuteAFD makes FP8 scales from BF16 weights at load: pow2 (powers of two, the default), amax (from "
         "the largest value), best (the launcher's third rule)."),
        ("KDA, head", "linear-attention projections; the final vocabulary layer."),
        ("Drafter", "DFlash2, a small model that proposes tokens for the main model to check (speculative decoding)."),
        ("Serving, scoring launch", "the engine as users run it; the same engine with the endpoints that return per-position "
         "probabilities for precision scoring."),
        ("Block Q, T, L", "the measurement blocks: precision, speed (throughput), long output."),
        ("Run labels", "K3.25: V1 and V1r (vLLM fork, one launch), V2 (a second launch), C1 (CuteAFD), C0 (CuteAFD control on "
         "K3.25-v1); K4: V-r1 and V-r2 (two vLLM launches), C-r1 (CuteAFD)."),
        ("Prefix cache", "reuse of a repeated prompt's processed state."),
        ("JIT caches", "kernels compiled at startup, kept between starts."),
        ("Thinking", "the model's reasoning before its answer; always on here.")]
    return P


def home_readme():
    P = home_parts(site=False)
    gl = "\n".join(f"- **{k}**: {v}" for k, v in P["glossary"])
    return {"{{HOME_INTRO}}": P["intro"], "{{HOME_FINDINGS}}": P["findings"], "{{HOME_BARS}}": P["bars_table"],
            "{{HOME_MATTERS}}": P["matters"], "{{HOME_PICK}}": P["pick"], "{{HOME_SETTINGS}}": P["settings"],
            "{{HOME_SPEED}}": P["speed"] + "\n\n" + P["speed_note"], "{{HOME_SURE}}": P["sure"], "{{HOME_GLOSSARY}}": gl}


def needle_line():
    nd = ROOT / "results" / NEEDLE_RUN
    if not (nd / "V1-pilot.json").exists(): return ""
    return (f"- **{load(nd / 'V1-pilot.json')['started'][11:16]}-{load(nd / 'C1-pilot.json')['finished'][11:16]}.** Needle pilot "
            f"on both engines with K3.25, prompts of 256K, 512K and 1M tokens, one request each (exploratory; "
            f"[`results/{NEEDLE_RUN}`](results/{NEEDLE_RUN}/)).\n")


def timeline():
    """The K4 part of the dated timeline (README "Timeline", site method page). Times UTC−7, from the receipts."""
    def span(p):
        d = load(p); a, b = d["started"], d["finished"]
        return f"{a[11:16]}-{b[11:16]}"
    t4 = lambda n: span(D4 / "t" / f"{n}.json"); f4 = lambda n: span(D4 / "f1k4" / "t" / f"{n}.json")
    return f"""2026-10-27 (evening), K4 checkpoint ([`results/{K4}`](results/{K4}/); no separate review of this run):

- **17:34-17:51.** K4 startup and smoke checks on both engines (one cold and one warm start each, and CuteAFD's scoring
  launch).
- **17:58.** K4 protocol frozen, before any comparison request (`FROZEN.json` sha256 `368e1700…`;
  [`METHOD.md`](results/{K4}/METHOD.md)).
- **18:03-19:48.** K4 Block Q: vLLM launch 1, CuteAFD's scoring launch (every panel twice, byte-identical), vLLM launch 2.
- **{t4('V-r1')[:5]}-{t4('V-d2')[6:]}.** K4 Block T: vLLM {t4('V-r1')} and its drift subset {t4('V-d1')}; CuteAFD {t4('C-r1')} and
  its drift subset {t4('C-d1')}; a final vLLM drift subset {t4('V-d2')}. 264 measured requests per engine, 0 errors.
- **Before 23:31.** Follow-up F1-K4 (W8A16 prefill) declared, after the Block Q results.
- **23:31-00:32.** F1-K4: CuteAFD scoring launch with W8A16 prefill; speed on serving launches {f4('C-base1')} (as shipped),
  {f4('C-f1c')} (W8A16), {f4('C-base2')} (as shipped).

2026-10-28:

- **From 00:38.** K4 Block L on both engines, vLLM first; analysed afterwards with the frozen K3.25 analyser and the
  review's loop rule.
- **To 12:47.** Follow-up F1-K4b (CuteAFD's other FP8 switches) declared before any of its requests; planner dry runs
  (BF16 KDA projections do not fit a serving launch with K4); the amax and best scale rules captured.
- **13:05-13:10.** F1-K4b amendments B1 and B2: drafter-off scoring launches for the BF16 head and KDA arms, gated by a
  control whose rows were byte-identical to as shipped on all 157,671 scored rows.
- **{f4('C-c-base1')[:5]}-{f4('C-c-base2')[6:]}.** K4c (W8A16 + amax), declared before any of its requests: speed on serving
  launches {f4('C-c-base1')} (as shipped), {f4('C-c-w16amax')}, {f4('C-c-base2')} (as shipped).
- **{f4('C-d-base1')[:5]}-{f4('C-d-base2')[6:]}.** K4d (W8A16 + best), declared before any of its requests: speed
  {f4('C-d-base1')}, {f4('C-d-w16best')}, {f4('C-d-base2')}.
"""


def substitutions(prefix):
    intro, secs = summary_sections(prefix)
    return {"{{STATUS}}": status_lines(), "{{S_INTRO}}": intro, "{{S_PRECISION}}": sec(secs, "Precision"),
            "{{S_THROUGHPUT}}": sec(secs, "Throughput"), "{{S_LONG}}": sec(secs, "Long output to 128K"),
            "{{S_OBSERVATIONS}}": sec(secs, "Observations"), "{{S_LIMITS}}": sec(secs, "Limits"),
            "{{Q_BUCKETS}}": q_buckets(prefix), "{{T_TABLE}}": t_table(), "{{T_COUNTS}}": t_counts(), "{{T_LINK}}": t_link(),
            "{{L_TABLE}}": l_table(), "{{L_DETAIL}}": l_table(detail=True), "{{L_NOTE}}": L_NOTE,
            "{{OTHER_RUNS}}": other_runs(), "{{K4_RESULTS}}": k4_readme_section(), "{{K4_STATUS}}": k4_status(),
            "{{TIMELINE_K4}}": timeline(), "{{NEEDLE_LINE}}": needle_line(), "{{CAPACITY}}": capacity_table(), "{{K4_STARTUP}}": k4_startup_table(),
            **(home_readme() if prefix else {})}


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
