#!/usr/bin/env python3
"""Build the results site (GitHub Pages, served from main /docs) from the repository's own files.

    python3 tools/build_site.py

Reads README.md (built by tools/build_readme.py), the run's SUMMARY.md, result markdown and JSON, the protocol, the audit
and repro/REPRODUCE.md, and writes static HTML pages to docs/. No scripts, no external stylesheets, fonts or images:
plain HTML with one inline stylesheet, light and dark (prefers-color-scheme), readable at phone width.
Links between pages are relative; links to files in the repository point at REPO_URL, the one place the repository's
address is assumed. Charts are static SVG drawn by tools/site_charts.py (one chart grammar, described there); the
tails curves count the per-position files in results/<run>/q/rows/. Standard library only (Python 3.10+).
"""
import html, importlib.util, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO_URL = "https://github.com/UrbanAstroLA/cuteafd-eval"          # the only absolute address the site assumes
spec = importlib.util.spec_from_file_location("build_readme", ROOT / "tools" / "build_readme.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
RUN, D = B.RUN, B.D
RD = f"results/{RUN}"
R4D = B.D4
_cs = importlib.util.spec_from_file_location("site_charts", ROOT / "tools" / "site_charts.py")
C = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(C)

PAGES = [("index.html", "Results"), ("precision.html", "Precision"), ("throughput.html", "Throughput"),
         ("long-output.html", "Long output"), ("observations.html", "Observations"), ("method.html", "Method"),
         ("audit.html", "Audit"), ("ledger.html", "Ledger"), ("reproduce.html", "Reproduce")]
# repository files that have a page of their own
PAGE_OF = {f"{RD}/SUMMARY.md": "index.html", f"{RD}/AUDIT-2026-10-27.md": "audit.html", "repro/REPRODUCE.md": "reproduce.html",
           f"{RD}/q/RESULTS-Q.md": "precision.html#block-q", f"{RD}/f1/RESULTS-F1.md": "precision.html#follow-up-f1",
           f"{RD}/t/CAVEATS.md": "throughput.html#caveats", f"{RD}/drift/RESULTS-DRIFT.md": "throughput.html#drift",
           f"{RD}/f2/RESULTS-F2.md": "throughput.html#follow-up-f2", f"{RD}/t/T-SUMMARY.md": "throughput.html#full-grid"}
# README anchors -> pages
ANCHOR_OF = {"ledger": "ledger.html", "observations-in-detail": "observations.html#observations-in-detail",
             "setup": "method.html#setup", "confounds": "observations.html#confounds", "reproduce": "reproduce.html"}

CSS = """:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--g1:#5f5e5a;--g2:#8f8e88;--on-g1:#ffffff;--good:#0ca30c;--crit:#d03b3b}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;
--muted:#9d9b94;--grid:#2c2c2a;--axis:#4a4a46;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--g1:#959595;--g2:#686868;--on-g1:#0b0b0b}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}
nav{display:flex;flex-wrap:wrap;gap:4px 18px;padding:14px 16px;max-width:980px;margin:0 auto;border-bottom:1px solid var(--grid)}
nav a{color:var(--ink2);text-decoration:none}nav a.on{color:var(--ink);font-weight:600}nav .brand{color:var(--ink);font-weight:600;margin-right:12px}
h1{font-size:28px;line-height:1.2;margin:8px 0 6px}h2{font-size:19px;margin:36px 0 6px}h3{font-size:16px;margin:26px 0 4px}
h4{font-size:15px;margin:18px 0 4px}h5{font-size:14px;margin:14px 0 4px}p,li{color:var(--ink2)}li{margin:3px 0}
a{color:var(--s1)}.lede{font-size:16px;max-width:760px}b,strong{color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:22px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}
.tile .lab{color:var(--ink2);font-size:13px}.tile .val{font-size:clamp(22px,2.4vw,26px);font-weight:600;margin:2px 0}.tile .sub{color:var(--muted);font-size:13px}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13.5px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tbl{overflow-x:auto}.note{border-left:3px solid var(--axis);padding:6px 12px;margin:14px 0;color:var(--ink2);font-size:14px}
blockquote{border-left:3px solid var(--axis);margin:14px 0;padding:2px 12px}
code{font-size:12.5px;overflow-wrap:anywhere}pre{overflow-x:auto;background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:10px;font-size:12.5px}
pre code{overflow-wrap:normal}
details.more{border-left:3px solid var(--grid);padding:2px 0 2px 12px;margin:10px 0}details.more>summary{cursor:pointer;color:var(--ink2);font-size:14px}
details.more[open]>summary{margin-bottom:6px}.shows{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:4px 18px 8px;margin:16px 0}
.shows h2{margin:12px 0 4px}.toc{font-size:14px;color:var(--ink2)}
.answer{font-size:clamp(18px,4.6vw,22px);line-height:1.4;color:var(--ink);max-width:820px;margin:10px 0 18px;font-weight:500}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:18px 0}.card{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}.card .k{color:var(--ink2);font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}.card .big{font-size:clamp(24px,6vw,30px);font-weight:650;margin:2px 0 4px;color:var(--ink);font-variant-numeric:tabular-nums}.card p{margin:4px 0;color:var(--ink)}.card .ev{color:var(--muted);font-size:12.5px}figure{background:var(--surface);border:1px solid var(--ring);border-radius:10px;margin:16px 0;padding:14px 14px 10px}figcaption .t{font-weight:600;color:var(--ink)}figcaption .s{color:var(--ink2);font-size:13.5px;margin-top:4px}svg{display:block;width:100%;height:auto;max-width:560px;margin:8px 0;font:12px system-ui,-apple-system,"Segoe UI",sans-serif}svg text{fill:var(--ink2)}svg .lab{fill:var(--ink)}svg .grid{stroke:var(--grid);stroke-width:1}svg .axis{stroke:var(--axis);stroke-width:1}svg .c1{fill:var(--s1);stroke:var(--s1)}svg .c2{fill:var(--s2);stroke:var(--s2)}svg .c2o{fill:var(--surface);stroke:var(--s2);stroke-width:2}svg .ln1{stroke:var(--s1);stroke-width:1.5;fill:none}svg .ln2{stroke:var(--s2);stroke-width:1.5;fill:none}svg .ln2d{stroke:var(--s2);stroke-width:1.5;fill:none;stroke-dasharray:4 3}svg .rng{stroke:var(--ink2);stroke-width:1.5}svg .g1{fill:var(--g1)}svg .g2{fill:var(--g2)}svg .lvl{fill:var(--grid)}svg .band{fill:var(--grid);opacity:.55}svg .hit{fill:transparent;stroke:none}svg .whisk{stroke:var(--ink2);stroke-width:1.5}svg .conn{stroke:var(--axis);stroke-width:2}svg .wash2{fill:var(--s2);opacity:.12}svg .inbar{fill:#fff;font-size:11px}svg .inbar.on-g1{fill:var(--on-g1)}svg .inbar.on-g2{fill:var(--ink)}svg circle.c1,svg circle.c2{stroke:var(--surface);stroke-width:2}svg g:hover>circle,svg g:hover>path,svg g:hover>rect:not(.hit){opacity:.8}details.data{margin:6px 0 0}details.data>summary{cursor:pointer;color:var(--ink2);font-size:13px}figure.small svg{max-width:420px}svg path.c1,svg path.c2,svg rect.c1,svg rect.c2,svg rect.g1,svg rect.g2{stroke:none}.ci{color:var(--muted);font-size:12px;white-space:nowrap}td .ci{white-space:normal}.outcomes{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:14px 0}.outcomes .card h3{margin:2px 0 6px}.outcomes .row{display:flex;justify-content:space-between;gap:10px;margin:3px 0;color:var(--ink)}.outcomes .row span:first-child{color:var(--ink2)}.use li{margin:8px 0}.use b{color:var(--ink)}.sure{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.sure>div{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:6px 16px}.sure h3{margin:10px 0 2px}dl.gl dt{font-weight:600;margin-top:8px;color:var(--ink)}dl.gl dd{margin:2px 0 0 0;color:var(--ink2)}.links li{margin:6px 0}.plain{font-size:15.5px;color:var(--ink);max-width:820px}.sign{font-size:13px;color:var(--ink2)}footer{max-width:980px;margin:0 auto;padding:0 16px 40px;color:var(--muted);font-size:13px}footer nav{padding:10px 0;border:0;margin:0;max-width:none}"""
CSS += "\n" + C.CSS


# ------------------------------------------------------------------ markdown -> HTML (the subset these files use)

def slug(text):
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^\w\- ]", "", s, flags=re.U)
    return re.sub(r" +", "-", s.strip())


def href(url, base):
    """Rewrite a link found in the repository file at `base` (a directory, repository-relative)."""
    if re.match(r"(?i)[a-z][a-z0-9+.-]*:", url): return url
    if url.startswith("#"):
        frag = url[1:]
        return ANCHOR_OF.get(frag, url)
    path, _, frag = url.partition("#")
    parts = []
    for seg in (base.split("/") if base else []) + path.split("/"):
        if seg in ("", "."): continue
        if seg == "..":
            if parts: parts.pop()
        else: parts.append(seg)
    p = "/".join(parts)
    if p.rstrip("/") in PAGE_OF: return PAGE_OF[p.rstrip("/")]
    if p == "README.md": return "index.html" + (f"#{frag}" if frag else "")
    target = ROOT / p
    kind = "tree" if target.is_dir() or path.endswith("/") else "blob"
    return f"{REPO_URL}/{kind}/main/{p.rstrip('/')}" + (f"#{frag}" if frag else "")


def inline(text, base):
    codes = []
    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>"); return f"\x00{len(codes) - 1}\x00"
    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=False)
    def link(m):
        label, url = m.group(1), html.unescape(m.group(2))
        return f'<a href="{html.escape(href(url, base))}">{label}</a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w])_(?!\s)([^_]+?)(?<!\s)_(?![\w])", r"<i>\1</i>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


NUM = re.compile(r"^[−\-+~]?[\d.,]+(?:%| pts| s|x)?$")


def md(text, base="", shift=0):
    """Convert markdown to HTML. base: repository directory of the source file (for links); shift: heading levels to add."""
    lines, prev_tbl, fence = [], False, False
    for l in text.replace("\r\n", "\n").split("\n"):    # tables indented under a list item: lift them out of the list
        if l.lstrip().startswith("```"): fence = not fence
        is_tbl = not fence and bool(re.match(r"^\s+\|", l))
        if is_tbl and not prev_tbl: lines.append("")
        if prev_tbl and not is_tbl and l.strip(): lines.append("")
        lines.append(l.lstrip() if is_tbl else l); prev_tbl = is_tbl
    out, i = [], 0
    def para(buf):
        if buf: out.append("<p>" + inline(" ".join(x.strip() for x in buf), base) + "</p>")
    buf = []
    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            para(buf); buf = []; j = i + 1
            while j < len(lines) and not lines[j].startswith("```"): j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>"); i = j + 1; continue
        m = re.match(r"^(#{1,6}) (.*)$", l)
        if m:
            para(buf); buf = []
            lvl = min(6, len(m.group(1)) + shift); h = inline(m.group(2), base)
            out.append(f'<h{lvl} id="{slug(h)}">{h}</h{lvl}>'); i += 1; continue
        if l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1]):
            para(buf); buf = []
            cells = lambda s: [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s.strip()[1:-1] if s.strip().endswith("|") else s.strip()[1:])]
            head = cells(l); rows = []; j = i + 2
            while j < len(lines) and lines[j].startswith("|"): rows.append(cells(lines[j])); j += 1
            td = lambda c: f'<td class="n">{inline(c, base)}</td>' if NUM.match(c) else f"<td>{inline(c, base)}</td>"
            out.append('<div class="tbl"><table><thead><tr>' + "".join(f"<th>{inline(c, base)}</th>" for c in head) +
                       "</tr></thead><tbody>" + "".join("<tr>" + "".join(td(c) for c in r) + "</tr>" for r in rows) +
                       "</tbody></table></div>"); i = j; continue
        if re.match(r"^\s*(?:[-*]|\d+\.) ", l):
            para(buf); buf = []; j = i
            items = []                                   # (indent, ordered, text)
            while j < len(lines) and lines[j].strip():
                mm = re.match(r"^(\s*)([-*]|\d+\.) (.*)$", lines[j])
                if mm: items.append([len(mm.group(1)), mm.group(2)[0].isdigit(), mm.group(3)])
                elif items: items[-1][2] += " " + lines[j].strip()
                j += 1
            out.append(render_list(items, base)); i = j; continue
        if l.startswith(">"):
            para(buf); buf = []; j = i; q = []
            while j < len(lines) and lines[j].startswith(">"): q.append(lines[j][1:].lstrip()); j += 1
            out.append("<blockquote>" + md("\n".join(q), base) + "</blockquote>"); i = j; continue
        if not l.strip() or l.strip() == "---":
            para(buf); buf = []
            if l.strip() == "---": out.append("<hr>")
            i += 1; continue
        buf.append(l); i += 1
    para(buf)
    return "\n".join(out)


def render_list(items, base):
    out, stack = [], []
    for ind, ordered, text in items:
        while stack and ind < stack[-1][0]:
            out.append("</li></" + stack.pop()[1] + ">")
        if not stack or ind > stack[-1][0]:
            tag = "ol" if ordered else "ul"; stack.append((ind, tag)); out.append(f"<{tag}><li>")
        else:
            out.append("</li><li>")
        out.append(inline(text, base))
    while stack: out.append("</li></" + stack.pop()[1] + ">")
    return "".join(out)


# ------------------------------------------------------------------ sources

def sections(text, level=2):
    """{heading: body} of a markdown text at one heading level."""
    parts = re.split(rf"(?m)^{'#' * level} ", text)
    out = {}
    for s in parts[1:]:
        head, _, body = s.partition("\n")
        out[head.strip()] = body.strip()
    return out


def readme():
    return (ROOT / "README.md").read_text()


def read(rel):
    p = ROOT / rel
    return p.read_text() if p.exists() else ""


def strip_title(text):
    return re.sub(r"\A# [^\n]*\n", "", text.lstrip())


def summary():
    return B.summary_sections(f"{RD}/")




def summary_block(key):
    _, secs = summary()
    h, body = secs.get(key, (f"### {key}", ""))
    return md(body, "")


def page(name, title, lede, body, lede_cls="lede"):
    nav = "".join(f'<a href="{p}" class="{"on" if p == name else ""}">{t}</a>' for p, t in PAGES)
    foot = "".join(f'<a href="{REPO_URL}/blob/main/{f}">{t}</a>' for f, t in
                   [("README.md", "README"), (f"{RD}/SUMMARY.md", "Summary"), ("protocol/README.md", "Protocol"),
                    ("NOTICE.md", "Notice"), ("LICENSE", "Licence (code)"), ("LICENSE-DATA.md", "Licence (results)"),
                    ("CITATION.cff", "Citation")])
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
           f'initial-scale=1"><meta name="color-scheme" content="light dark"><title>{html.escape(title)} - cuteafd-eval</title>'
           f'<style>\n{CSS}\n</style></head><body><nav><span class="brand">cuteafd-eval</span>{nav}</nav><main>'
           f'<h1>{html.escape(title)}</h1><p class="{lede_cls}">{lede}</p>\n{body}\n</main><footer><nav aria-label="Repository documents">'
           f'{foot}</nav>Generated from the repository data by <code>tools/build_site.py</code>. Maintained by Michael M '
           f'(UrbanAstroLA on GitHub, @UrbanAstroFella on X). Results CC BY 4.0, code Apache-2.0.</footer></body></html>\n')
    (DOCS / name).write_text(doc)


def details(summary_text, inner):
    return f'<details class="more"><summary>{summary_text}</summary>{inner}</details>'


# ------------------------------------------------------------------ numbers used in the plain text (from the published JSON)

def facts():
    import statistics as st
    q = D / "q/pb"
    gen = lambda a: B.load(q / f"pb-{a}.json")["summary"]["gen"]
    v_runs = [gen(a) for a in ("V1", "V1r", "V2") if (q / f"pb-{a}.json").exists()]
    bk = ("0-2K", "2-8K", "8-16K")
    F = {"n_vruns": len(v_runs)}
    F["kl_v"] = {b: st.mean(r["by_bucket"][b]["kl"]["value"] for r in v_runs) for b in bk}
    F["kl_v"]["all"] = st.mean(r["overall"]["kl"]["value"] for r in v_runs)
    c = gen("C1"); F["kl_c"] = {**{b: c["by_bucket"][b]["kl"]["value"] for b in bk}, "all": c["overall"]["kl"]["value"]}
    f1 = B.load(D / "f1/F1-RESULTS.json")
    F["kl_f1c"] = {b: f1["precision"]["f1c"][b]["kl"] for b in ("all",) + bk}
    m = B.load(q / "pb-vs-vllm-mean3.json")
    F["d"] = {(b, met, arm): m[f"{b}|{met}|{arm}"] for b in ("all",) + bk for met in ("kl", "top1") for arm in ("C1", "F1c", "F1d")}
    F["pa"] = B.load(D / "q/pa/pa-pair-V1-vs-C1.json")["overall"]["kl"]
    sp = f1["speed"]
    F["f1c_ttft"] = st.median(v["ttft_median_s"] for v in sp["f1c"].values())
    F["f1c_dec"] = st.median(v["decode_tok_s_per_stream_median"] for v in sp["f1c"].values())
    F["f1d_dec"] = st.median(v["decode_tok_s_per_stream_median"] for v in sp["f1d"].values())
    rec = B.t_receipts(); cv, cc = B.t_cells(rec["V1"]), B.t_cells(rec["C1"])
    g = lambda cells, k, key: B.t_med(cells, key, k)
    F["dec1k"] = {k[1]: (g(cv, k, "decode_tok_s_per_stream_median"), g(cc, k, "decode_tok_s_per_stream_median"))
                  for k in sorted(cv) if k[0] == 1024 and k[2] == 1 and k in cc}
    rows = {}
    for L in (1024, 8192, 32768, 131072):
        ks = [k for k in cv if k[0] == L and k in cc]
        dec = [g(cc, k, "decode_tok_s_per_stream_median") / g(cv, k, "decode_tok_s_per_stream_median") for k in ks if k[2] == 1]
        agg = [g(cc, k, "aggregate_tok_s") / g(cv, k, "aggregate_tok_s") for k in ks]
        tt = [(g(cv, k, "ttft_median_s"), g(cc, k, "ttft_median_s")) for k in ks if k[2] == 1]
        hi = max(k[2] for k in ks)
        tth = [(g(cv, k, "ttft_median_s"), g(cc, k, "ttft_median_s")) for k in ks if k[2] == hi]
        rows[L] = {"dec": (min(dec), max(dec)), "n1": len(dec), "dec_all": dec, "agg_all": agg, "agg": (st.median(agg), min(agg), max(agg)), "tt1": tt, "tth": tth, "hi": hi,
                   "agg8": [g(cc, k, "aggregate_tok_s") / g(cv, k, "aggregate_tok_s") for k in ks if k[2] == 8]}
    F["len"] = rows
    alld = [x for r in rows.values() for x in r["dec"]]
    F["dec_range"] = (min(alld), max(alld))
    F["agg_long"] = (min(rows[32768]["agg"][1], rows[131072]["agg"][1]), max(rows[32768]["agg"][2], rows[131072]["agg"][2]))
    F["L"] = B.l_summaries()
    F["f1"] = f1
    F["f1_dec"] = {**{a: st.median(v["decode_tok_s_per_stream_median"] for v in sp[a].values()) for a in ("f1a", "f1b", "f1c", "f1d")}, "C1": 1.0}
    def cached(d):
        b = [x for x in d["batches"] if x["kind"] == "cached"]
        return b[0]["summary"]["ttft_median_s"] if b else None
    F["cached"] = (cached(rec["V1"]), cached(rec["C1"]))
    F["T"] = tails()
    return F


def startup():
    p = ROOT / "results/2026-10-27-vllm-startup-cache/startup.json"
    return B.load(p) if p.exists() else None


def pct(r): return f"{100 * (r - 1):+.0f}%"
def pp(r): return f"{abs(100 * (r - 1)):.0f}%"
def span(a, b): return f"{abs(100 * (a - 1)):.0f}-{abs(100 * (b - 1)):.0f}%"
def kl(x): return f"{x:.4f}"
def dkl(x): return f"{x:+.4f}"
def civ(v, nd=4, s=1.0): return f'<span class="ci">[{v[1] * s:+.{nd}f}, {v[2] * s:+.{nd}f}]</span>'


# ------------------------------------------------------------------ per-position tails (results/<run>/q/tails, from tools/kl_tails.py)

def tails():
    out = {}
    for k in ("pa", "pb", "q2"):
        p = D / "q" / "tails" / f"{k}-tails.json"
        if p.exists(): out[k] = B.load(p)
    return out


def num(x): return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"
def hist(c): return f"{num(c['min'])} / {num(c['median'])} / {num(c['max'])}"
def hist_short(c): return f"{num(c['min'])}-{num(c['max'])} tokens of history, median {num(c['median'])}"


def pb_band(T, b):
    return next(x for x in T["pb"]["by_position"] if x["band"] == b)


def vmean(arms, key, names=("V1", "V1r", "V2")):
    import statistics as st
    return st.mean(arms[a][key] for a in names if a in arms)


ARM = {"V1": "vLLM fork V1", "V1r": "vLLM fork V1r", "V2": "vLLM fork V2", "C1": "CuteAFD C1", "C0": "CuteAFD C0 (control)"}


def tails_table(T, key):
    P = T[key]; rows = []
    for a, s in P["arms"].items():
        rows.append([ARM[a], f"{s['kl_mean']:.4f}", f"{s['kl_p50']:.4f}", f"{s['kl_p90']:.3f}", f"{s['kl_p99']:.3f}",
                     f"{s['kl_p99.9']:.2f}", f"{s['kl_max']:.2f}", f"{100 * s['top1']:.2f}%",
                     f"{100 * s['confident_top1']:.2f}%" if "confident_top1" in s else "n/a"])
    return htable(["Arm", "Mean", "p50", "p90", "p99", "p99.9", "Max", "Top-1", "Confident top-1"], rows)


def band_table(T, key):
    P = T[key]; rows = []
    for b in P["by_position"]:
        for a, s in b["arms"].items():
            rows.append([E(b["band"]) if a == next(iter(b["arms"])) else "", hist(b["context"]) if a == next(iter(b["arms"])) else "",
                         ARM[a], f"{s['kl_mean']:.4f}", f"{s['kl_p99']:.3f}", f"{s['kl_p99.9']:.2f}", f"{100 * s['top1']:.2f}%"])
    return htable(["Positions", "History, tokens (min / median / max)", "Arm", "Mean KL", "p99", "p99.9", "Top-1"], rows)


def what_scored(T):
    pa = T["pa"]["scored"]["context"]
    return ('<h2 id="what-was-scored">What was scored</h2>' + scored_table(T) +
            f'<p class="plain">P-A scores every position of each 2,048-token window, so the history behind a scored token runs '
            f'from {num(pa["min"])} to {num(pa["max"])} tokens (median {num(pa["median"])}), as the teacher dataset defines its '
            '2,047 prediction positions per window. P-B and Q2 score the end of each window, so every primary scored position '
            f'there (P-B\'s generated positions, all of Q2\'s) has at least {num(T["pb"]["scored"]["context"]["min"])} tokens '
            'of history.</p>'
            '<p class="sign">KL values are not comparable across panels (different metric, text and reference), and NLL is '
            'per tokenizer and per text. Teacher dataset identity, the 25 windows and their hashes: '
            f'<a href="{REPO_URL}/blob/main/{RD}/q/pa/PROVENANCE.json"><code>q/pa/PROVENANCE.json</code></a>; rebuilding the '
            'P-A numbers: <a href="reproduce.html#5a-panel-p-a-from-the-teacher-dataset">Reproduce, step 5a</a>. Per-position '
            f'scores: <a href="{REPO_URL}/blob/main/{RD}/q/rows/README.md"><code>q/rows/</code></a>; tails: '
            '<a href="precision.html#tails">Precision</a>.</p>')


def scored_table(T):
    """'What was scored': one row per panel, numbers from the tails files."""
    pa, pb, q2 = T["pa"]["scored"], T["pb"]["scored"], T["q2"]["scored"]
    rows = [
        ["<b>P-A</b> BF16 teacher panel (brandonmusic)", f"{pa['windows']}", hist(pa["tokens_per_window"]),
         f"all {num(pa['scored_positions_per_window']['median'])} (rows 0-2046)", f"{pa['selected_positions_total']:,}",
         hist(pa["context"]),
         "the dataset's 25 qualification windows <code>final-0000</code> to <code>final-0024</code>; domains "
         "<code>axis1_general</code>, <code>axis2_legal</code>, <code>axis3_code_agentic</code>, "
         "<code>axis4_reasoning_termination</code>",
         "BF16 teacher: <code>zai-org/GLM-5.3-Flash-BF16</code> @ <code>a6c167b6</code>, full-vocabulary FP32 logits",
         "full-vocabulary KL(teacher ‖ engine), float64; NLL; top-1"],
        ["<b>P-B</b> tpurtell's fidelity panel (<code>cuteafd-fidelity</code>, glm5_flash v2)", f"{pb['windows']}",
         hist(pb["tokens_per_window"]),
         f"last 512; generated positions (primary) per window: {hist(pb['selected_positions_per_window'])} "
         f"(min / median / max), in {pb['windows_with_selected_positions']} windows",
         f"{pb['selected_positions_total']:,} generated ({pb['windows'] * 512:,} recorded)", hist(pb["context"]),
         "replies written by the official FP8 model after conditioning and repository-source context; blocks A-E "
         "(B: long code reading); buckets 0-2K, 2-8K, 8-16K",
         "BF16 reference run: <code>zai-org/GLM-5.3-Flash-BF16</code> @ <code>a5b45eb4</code>, stored as its top 1,024 ids "
         "plus a tail bin",
         "coarse KL (top-1,024 + tail; a lower bound on full-vocabulary KL); NLL; top-1"],
        ["<b>Q2</b> long human-written text", f"{q2['windows']}", hist(q2["tokens_per_window"]),
         f"last {num(q2['scored_positions_per_window']['median'])}", f"{q2['selected_positions_total']:,}", hist(q2["context"]),
         "3 PG-19 books and 3 Apache-2.0 vLLM source files, each at 32K, 64K and 128K tokens", "none",
         "NLL only; KL between the two engines as disagreement"]]
    return htable(["Panel", "Windows", "Tokens per window (min / median / max)", "Scored positions per window",
                   "Total scored", "History behind each scored token, tokens (min / median / max)", "Text",
                   "Reference", "Metric"], rows)


# ------------------------------------------------------------------ charts (tools/site_charts.py: one grammar, static SVG)
# Engine colour and shape follow the engine: vLLM fork = blue circle, CuteAFD = orange triangle; a hollow triangle is a
# CuteAFD setting that does not fit a serving launch on 2x RTX PRO 6000 with that checkpoint. Every number below is read
# from the published files; where a figure needs a value the files do not publish (an interval), it is drawn without
# one and the table view says so.

E = html.escape
sg, cit, rx = C.sg, C.ci_txt, C.rx

LG_ENGINE = [("v", "vLLM fork"), ("c", "CuteAFD"), ("ci", "95% interval excludes the reference (resolved)"),
             ("ciu", "95% interval includes it (not resolved)"), ("band", "the reference's own run-to-run spread")]
LG_SET = [("c", "CuteAFD setting that serves on 2x RTX"), ("ch", "does not fit a serving launch on 2x RTX (scoring launch only)"),
          ("ci", "95% interval excludes 0 (resolved)"), ("ciu", "includes 0 (not resolved)")]


def htable(head, rows, cls=""):
    return (f'<div class="tbl"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")


def vband(vals):
    """Band around 0: the largest difference between any two vLLM runs' published means on the same rows."""
    w = max(vals) - min(vals)
    return (-w, w)


def spec_strip(scored, panel, ref, metric, sel=None):
    s = scored
    tpw = s["tokens_per_window"]
    win = f'{s["windows"]} windows' + (f' ({s["windows_with_selected_positions"]} with scored positions)'
                                         if s["windows_with_selected_positions"] != s["windows"] else "")
    size = f'{num(tpw["min"])}' if tpw["min"] == tpw["max"] else f'{num(tpw["min"])}-{num(tpw["max"])}'
    return (f'<b>{E(panel)}</b> · {win} × {size} tokens · {E(sel or "scored positions")}: '
            f'{s["selected_positions_total"]:,} · history {hist(s["context"])} tokens (min / median / max) · '
            f'reference: {E(ref)} · metric: {E(metric)}')


def spec_band(panel, positions, windows, ctx, ref, metric):
    return (f'<b>{E(panel)}</b> · {windows} windows · {positions:,} scored positions · history {hist(ctx)} tokens '
            f'(min / median / max) · reference: {E(ref)} · metric: {E(metric)}')


REF = {"k325": {"pa": ("BF16 teacher, full vocabulary", "KL, nats"), "pb": ("BF16 run, top 1,024 ids + tail", "coarse KL, nats"),
                "q2": ("none (engine against engine)", "NLL, nats per token")},
       "k4": {"pa": ("BF16 teacher, top 20", "KL20, nats"), "pb": ("BF16 run, top 20", "KL_pb20, nats"),
              "q2": ("none (engine against engine)", "NLL, nats per token")}}
PANEL = {"pa": "P-A, BF16 teacher panel", "pb": "P-B, fidelity panel, generated positions", "q2": "Q2, long human-written text"}
SEL = {"pa": "every position", "pb": "generated positions", "q2": "last 4,096 positions per window"}


def strip(T, run, key):
    ref, metric = REF[run][key]
    return spec_strip(T[key]["scored"], PANEL[key], ref, metric, SEL[key])


def frow(label, est, lo, hi, band, title, sub=None, who="c", hollow=False, extra=""):
    return {"label": label, "sub": sub, "est": est, "lo": lo, "hi": hi, "band": band, "who": who, "hollow": hollow,
            "value": f"{sg(est)} {cit(lo, hi)}{extra}", "title": title}


# ---- precision: engine difference (K3.25)

def k325_runs():
    q = D / "q"
    pa = {a: B.load(q / ("pa-v2" if a == "V2" else "pa") / f"pa-{a}.json")["overall"]["kl"]["value"] for a in ("V1", "V1r", "V2")}
    pb = {}
    for a in ("V1", "V1r", "V2"):
        g = B.load(q / "pb" / f"pb-{a}.json")["summary"]["gen"]
        pb[a] = {"all": g["overall"]["kl"]["value"], **{b: g["by_bucket"][b]["kl"]["value"] for b in ("0-2K", "2-8K", "8-16K")}}
    q2 = B.load(q / "q2" / "q2-C1-vs-V1.json")["groups"]["overall"]
    return pa, pb, q2


PB_LAB = {"all": "All generated rows", "0-2K": "0-2K", "2-8K": "2-8K", "8-16K": "8-16K, long code"}


def k325_engine_rows(F):
    T, d = F["T"], F["d"]; pa_runs, pb_runs, q2 = k325_runs()
    p = F["pa"]
    rows_pa = [frow("All 2,047 positions", p["B_minus_A"], *p["ci95"], vband(list(pa_runs.values())),
                    f"P-A, CuteAFD − vLLM fork V1: {sg(p['B_minus_A'])} {cit(*p['ci95'])} KL; history {hist(T['pa']['scored']['context'])}",
                    sub="25 windows, vs vLLM V1")]
    rows_pb = []
    for b in ("all", "0-2K", "2-8K", "8-16K"):
        v = d[(b, "kl", "C1")]; ctx = T["pb"]["scored"]["context"] if b == "all" else pb_band(T, b)["context"]
        band = vband([pb_runs[a][b] for a in pb_runs])
        rows_pb.append(frow(PB_LAB[b], v[0], v[1], v[2], band,
                            f"P-B {PB_LAB[b]}, CuteAFD − mean of 3 vLLM runs: {sg(v[0])} {cit(v[1], v[2])} KL; vLLM runs differ by up "
                            f"to {band[1]:.4f}; history {hist(ctx)}", sub=f"history {hist(ctx)}"))
    n = q2["nll_paired"]; fl = q2["noise_floor_B"]["dnll_repeat"]["B_minus_A"]
    est, lo, hi = -n["B_minus_A"], -n["ci95"][1], -n["ci95"][0]          # file is V1 − C1; shown as CuteAFD − vLLM
    rows_q2 = [frow("6 documents, 32K-128K", est, lo, hi, (-abs(fl), abs(fl)),
                    f"Q2 NLL, CuteAFD − vLLM V1: {sg(est)} {cit(lo, hi)} nats per token; vLLM's repeat on 2 documents "
                    f"differs by {sg(fl)}", sub="18 windows, vs vLLM V1")]
    return rows_pa, rows_pb, rows_q2


def engine_table(rows_by_panel):
    out = []
    for panel, rows, bandnote in rows_by_panel:
        for r in rows:
            out.append([E(panel), E(r["label"]) + (f'<br><span class="ci">{E(r["sub"])}</span>' if r.get("sub") else ""),
                        f'{sg(r["est"])}', f'{cit(r["lo"], r["hi"])}', f'±{r["band"][1]:.4f}' if r.get("band") else "n/a",
                        "resolved" if (r["lo"] > 0 or r["hi"] < 0) else "not resolved", E(bandnote)])
    return htable(["Panel", "Rows", "CuteAFD − vLLM fork", "95% interval", "vLLM run-to-run band", "Interval", "Band from"], out)


def fig_engine_k325(F, fid="engine-k325"):
    pa, pb, q2 = k325_engine_rows(F); T = F["T"]
    kw = dict(ref="vLLM fork", ref_who="v", left="closer to BF16", right="further from BF16")
    s1 = C.forest([{"section": "P-A, full-vocabulary KL from the BF16 teacher"}] + pa, aria="Engine difference, P-A, K3.25", **kw)
    s2 = C.forest([{"section": "P-B, coarse KL (top 1,024 + tail), by context bucket"}] + pb, aria="Engine difference by context bucket, P-B, K3.25", **kw)
    s3 = C.forest([{"section": "Q2, NLL of human-written text (no BF16 reference here)"}] + q2, ref="vLLM fork", ref_who="v",
                  left="CuteAFD lower NLL", right="CuteAFD higher NLL", aria="NLL difference on long human-written text, Q2, K3.25")
    table = engine_table([("P-A KL", pa, "vLLM runs V1, V1r, V2"), ("P-B coarse KL", pb, "vLLM runs V1, V1r, V2"),
                          ("Q2 NLL", q2, "vLLM V1 against its repeat, 2 documents")])
    return C.figure(fid, "K3.25: CuteAFD against the vLLM fork, by panel and context (reference: vLLM fork)",
                    "Each row is CuteAFD's distance from the BF16 model minus the vLLM fork's, on the same scored positions; "
                    "right of the blue line means CuteAFD is further from BF16.",
                    [(s1, strip(T, "k325", "pa"), None), (s2, strip(T, "k325", "pb"), None), (s3, strip(T, "k325", "q2"), None)],
                    "If your prompts look like the 8-16K row (long code reading), that is where the engines differ; below 8K the "
                    "intervals include zero. The grey band is how far the vLLM fork's own runs differ on the same rows. Compare rows with the blue "
                    "line, not panels with each other: each panel has its own metric and text.",
                    table, LG_ENGINE)


# ---- precision: engine difference (K4, top-20 measures)

def k4_engine_rows(K):
    pa, pb, q2, T = K["pa"], K["pb"], K["q2"], K["T"]
    p = pa["paired"]["C-r1-Vmean"]["kl_e20"]; runs = [pa["per_arm"][a]["kl_e20"]["value"] for a in ("V-r1", "V-r2")]
    rows_pa = [frow("All 2,047 positions", p["B_minus_A"], *p["ci95"], vband(runs),
                    f"P-A KL20, CuteAFD − mean of 2 vLLM launches: {sg(p['B_minus_A'])} {cit(*p['ci95'])}; "
                    f"launch 2 − launch 1 {sg(runs[1] - runs[0])}", sub="25 windows")]
    band = {b["band"]: b for b in T["pb"]["by_position"]}
    rows_pb = []
    for g, lab, ctx in (("gen", "All generated rows", T["pb"]["scored"]["context"]), ("gen 0-2K", "0-2K", band["0-2K"]["context"]),
                        ("gen 2-8K", "2-8K", band["2-8K"]["context"]), ("gen 8-16K", "8-16K", band["8-16K"]["context"]),
                        ("gen block B", "Block B, long code", K["histB"])):
        p = pb["paired"]["C-r1-Vmean"][g]["kl_pb20"]
        runs = [pb["per_arm"][a][g]["kl_pb20"]["value"] for a in ("V-r1", "V-r1b", "V-r2")]
        fl = pb["floors"]["V-r2-V-r1"][g]["kl_pb20"]["B_minus_A"]
        reading = B.k4_reading(p["B_minus_A"], p["ci95"], fl)
        rows_pb.append(frow(lab, p["B_minus_A"], *p["ci95"], vband(runs),
                            f"P-B {lab} KL_pb20, CuteAFD − mean of 2 vLLM launches: {sg(p['B_minus_A'])} {cit(*p['ci95'])}; "
                            f"launch 2 − launch 1 {sg(fl)}; reading: {reading}; history {hist(ctx)}", sub=f"history {hist(ctx)}"))
        rows_pb[-1]["reading"] = reading
    rows_pa[0]["reading"] = B.k4_reading(rows_pa[0]["est"], [rows_pa[0]["lo"], rows_pa[0]["hi"]], pa["floors"]["V-r2-V-r1"]["kl_e20"]["B_minus_A"])
    v = q2["vs_vllm_mean"]["C-r1"]["dnll_x_minus_v_documents_t"]; fl = q2["pairs"]["V-r1|V-r2"]["dnll_yx_documents_t"]["mean"]
    rows_q2 = [frow("6 documents, 32K-128K", v["mean"], *v["ci95"], (-abs(fl), abs(fl)),
                    f"Q2 NLL, CuteAFD − mean of 2 vLLM launches: {sg(v['mean'])} {cit(*v['ci95'])} (t-interval over 6 documents); "
                    f"launch 2 − launch 1 {sg(fl)}", sub="18 windows, t-interval")]
    rows_q2[0]["reading"] = B.k4_reading(v["mean"], v["ci95"])
    return rows_pa, rows_pb, rows_q2


def fig_engine_k4(K, fid="engine-k4"):
    pa, pb, q2 = k4_engine_rows(K); T = K["T"]
    kw = dict(ref="vLLM fork", ref_who="v", left="closer to BF16", right="further from BF16")
    s1 = C.forest([{"section": "P-A, KL20 from the BF16 teacher (top-20 measure)"}] + pa, aria="Engine difference, P-A, K4, top-20", **kw)
    s2 = C.forest([{"section": "P-B, KL_pb20 (top-20 measure), by context bucket"}] + pb, aria="Engine difference by context bucket, P-B, K4, top-20", **kw)
    s3 = C.forest([{"section": "Q2, NLL of human-written text (no BF16 reference here)"}] + q2, ref="vLLM fork", ref_who="v",
                  left="CuteAFD lower NLL", right="CuteAFD higher NLL", aria="NLL difference on long human-written text, Q2, K4")
    rows = []
    for panel, rs in (("P-A KL20", pa), ("P-B KL_pb20", pb), ("Q2 NLL", q2)):
        for r in rs:
            rows.append([panel, E(r["label"]) + (f'<br><span class="ci">{E(r["sub"])}</span>' if r.get("sub") else ""), sg(r["est"]),
                         cit(r["lo"], r["hi"]), f'±{r["band"][1]:.4f}', r["reading"]])
    table = htable(["Panel", "Rows", "CuteAFD − vLLM fork", "95% interval", "vLLM run-to-run band", "Published reading"], rows)
    return C.figure(fid, "K4: CuteAFD against the vLLM fork, by panel and context (reference: vLLM fork; top-20 measures)",
                    "The same layout as K3.25 on K4, scored with top-20 measures (KL20, KL_pb20); not comparable in level with "
                    "K3.25's full-vocabulary KL, so read each row only against the blue line.",
                    [(s1, strip(T, "k4", "pa"), None), (s2, strip(T, "k4", "pb"), None), (s3, strip(T, "k4", "q2"), None)],
                    "If your prompts look like 8-16K long code, the vLLM fork stays closer to BF16 on K4; under the same top-20 "
                    "definition it reads larger than on K3.25, with overlapping intervals. On the teacher panel the difference is smaller, and on long human-written text no "
                    "NLL difference is resolved. The published reading also requires a difference larger than the band.",
                    table, LG_ENGINE)


# ---- precision: CuteAFD settings (reference: CuteAFD as shipped) and the settings map

F1_NAME = {"f1a": "KDA projections BF16", "f1b": "Output head BF16", "f1c": "W8A16 prefill", "f1d": "All three"}
F1_ENV = {"f1a": "GLM5_FLASH_KDA_FP8=off", "f1b": "GLM5_FLASH_FP8_HEAD=off", "f1c": "GLM5_FLASH_FP8_PREFILL=off", "f1d": "all three switches"}


def f1_speed(F):
    import statistics as st
    sp = F["f1"]["speed"]
    return {a: (st.median(v["ttft_median_s"] for v in sp[a].values()), min(v["ttft_median_s"] for v in sp[a].values()),
                max(v["ttft_median_s"] for v in sp[a].values()), st.median(v["decode_tok_s_per_stream_median"] for v in sp[a].values()))
            for a in sp}


def fig_settings_k325(F, fid="settings-k325"):
    P = F["f1"]["precision"]; T = F["T"]; spd = f1_speed(F)
    rows = []
    for b, sec in (("all", "P-B, all generated rows"), ("8-16K", "P-B 8-16K, long code reading (the most sensitive slice)")):
        rows.append({"section": sec})
        for a in ("f1a", "f1b", "f1c", "f1d"):
            v = P[a][b]["vs_C1"]["kl"]
            rows.append(frow(F1_NAME[a], v[0], v[1], v[2], None, f"{F1_NAME[a]} ({F1_ENV[a]}), {sec}: {sg(v[0])} {cit(v[1], v[2])} KL "
                             "against CuteAFD as shipped", sub=F1_ENV[a]))
    s = C.forest(rows, ref="CuteAFD as shipped", ref_who="c", left="closer to BF16", right="further from BF16",
                 aria="CuteAFD FP8 switches against CuteAFD as shipped, K3.25")
    tab = []
    for a in ("f1a", "f1b", "f1c", "f1d"):
        r = [F1_NAME[a] + f'<br><span class="ci">{F1_ENV[a]}</span>']
        for b in ("all", "8-16K"):
            v = P[a][b]["vs_C1"]["kl"]; r.append(f"{sg(v[0])} {cit(v[1], v[2])}")
        t = spd[a]; r += [f"{100 * (t[0] - 1):+.1f}% ({100 * (t[1] - 1):+.1f} to {100 * (t[2] - 1):+.1f}%)".replace("-", C.MINUS), rx(t[3])]
        tab.append(r)
    table = htable(["Setting", "P-B all rows − as shipped", "P-B 8-16K − as shipped", "Time to first token vs as shipped, median of 8 "
                    "cells (range)", "Decode vs as shipped, median of 8 cells"], tab) + \
        '<p class="sign">Band: none. CuteAFD repeats are byte-identical, so its own run-to-run spread is 0. Source: <code>f1/F1-RESULTS.json</code>.</p>'
    return C.figure(fid, "K3.25: CuteAFD's FP8 switches against CuteAFD as shipped (reference: CuteAFD as shipped)",
                    "How far each switch moves CuteAFD towards (left) or away from (right) the BF16 model, paired on the same "
                    "positions; the orange line is CuteAFD as shipped, which is bit-deterministic, so there is no noise band.",
                    [(s, spec_band("P-B, fidelity panel, generated positions", T["pb"]["scored"]["selected_positions_total"],
                                   T["pb"]["scored"]["windows_with_selected_positions"], T["pb"]["scored"]["context"],
                                   REF["k325"]["pb"][0], REF["k325"]["pb"][1]), None)],
                    "If you run CuteAFD on K3.25 and want it closer to BF16, look for long rows to the left with solid intervals: at "
                    f"8-16K W8A16 prefill ({sg(P['f1c']['8-16K']['vs_C1']['kl'][0])}) and all three ({sg(P['f1d']['8-16K']['vs_C1']['kl'][0])}) "
                    f"move it most; the head switch is resolved but small ({sg(P['f1b']['8-16K']['vs_C1']['kl'][0])}). Read their cost in the "
                    "settings map below.",
                    table, [("c", "CuteAFD setting (all serve on 2x RTX with K3.25)"), ("refc", "CuteAFD as shipped"),
                            ("ci", "95% interval excludes 0 (resolved)"), ("ciu", "includes 0 (not resolved)")])


def fig_map_k325(F, fid="map-k325"):
    P = F["f1"]["precision"]; spd = f1_speed(F)
    lab = {"C1": "as shipped", "f1a": "KDA BF16", "f1b": "head BF16", "f1c": "W8A16 prefill", "f1d": "all three"}
    pts, tab = [], []
    for a in ("C1", "f1a", "f1b", "f1c", "f1d"):
        v = P[a]["8-16K"]["vs_vllm_mean"]["kl"]
        t = spd.get(a, (1.0, 1.0, 1.0, 1.0))
        dec = f" · decode {rx(t[3])}" if a != "C1" else ""
        pts.append({"label": lab[a] + dec, "x": 100 * (t[0] - 1), "y": v[0], "lo": v[1], "hi": v[2],
                    "title": f"{lab[a]}: first token {100 * (t[0] - 1):+.1f}% vs as shipped, decode {rx(t[3])}; still {sg(v[0])} "
                             f"{cit(v[1], v[2])} KL from the vLLM fork at 8-16K"})
        tab.append([lab[a], f"{100 * (t[0] - 1):+.1f}%".replace("-", C.MINUS) if a != "C1" else "0 (reference)",
                    rx(t[3]) if a != "C1" else "1.00x (reference)", f"{sg(v[0])} {cit(v[1], v[2])}"])
    c1 = P["C1"]["8-16K"]["vs_vllm_mean"]["kl"][0]; c = P["f1c"]["8-16K"]["vs_vllm_mean"]["kl"][0]; dd = P["f1d"]["8-16K"]["vs_vllm_mean"]["kl"]
    s = C.settings_map(pts, aria="Settings map K3.25: first-token cost against the remaining difference from the vLLM fork",
                       shipped_y=c1, xlabel="time to first token, % change vs CuteAFD as shipped (median of 8 cells)",
                       ylabel="KL difference from the vLLM fork, P-B 8-16K (long code)")
    m3 = lambda a: F["d"][("8-16K", "kl", a)][0]
    cap = (f"W8A16 prefill: about {100 * (c1 - c) / c1:.0f}% of the long-code difference closed ({sg(c1)} → {sg(c)}; against "
           f"all three vLLM runs {sg(m3('C1'))} → {sg(m3('F1c'))}, about {100 * (m3('C1') - m3('F1c')) / m3('C1'):.0f}%) for about "
           f"{100 * (spd['f1c'][0] - 1):.0f}% longer time to first token, decode level ({rx(spd['f1c'][3])}). All three switches leave no "
           f"resolved difference ({sg(dd[0])} {cit(dd[1], dd[2])}) but cost decode speed ({rx(spd['f1d'][3])} median, worst cell "
           f"{rx(min(v['decode_tok_s_per_stream_median'] for v in F['f1']['speed']['f1d'].values()))}); the KDA and head switches cost "
           f"decode speed ({rx(spd['f1a'][3])}, {rx(spd['f1b'][3])}) for less. All five serve on 2x RTX with K3.25.")
    table = htable(["Setting", "Time to first token vs as shipped", "Decode vs as shipped", "Remaining KL difference from the vLLM fork, 8-16K"], tab) + \
        ('<p class="sign">Difference from the vLLM fork: against the mean of its first two runs, as follow-up F1 publishes it '
         '(<code>f1/F1-RESULTS.json</code>; the three-run mean gives as shipped +0.0054, W8A16 +0.0022, all three +0.0016). '
         'Speed: each arm ÷ the F1 base launch, Block T driver subset (1K/8K input, 1 and 8 streams, code and prose). No interval '
         'is published for the speed ratios.</p>')
    return C.figure(fid, "K3.25 settings map: what each CuteAFD setting costs and what it closes",
                    "Each triangle is one CuteAFD setting: across, its time-to-first-token cost against as shipped; up and down, how "
                    "far it still is from the vLLM fork on long code reading (8-16K), with its 95% interval.",
                    [(s, spec_band("P-B 8-16K, long code reading", pb_band(F["T"], "8-16K")["positions"], clusters_816("k325"),
                                   pb_band(F["T"], "8-16K")["context"], REF["k325"]["pb"][0], REF["k325"]["pb"][1]), None)],
                    "Points near the bottom-left close the most for the least: pick the lowest point whose cost you accept. "
                    "Decode cost is in each label because on K3.25 it is not level for every switch.",
                    table, [("c", "CuteAFD setting (serves on 2x RTX)"), ("refdv", "vLLM fork (0)"), ("refdc", "CuteAFD as shipped"),
                            ("ci", "interval excludes 0: still differs from the vLLM fork"), ("ciu", "includes 0: not resolved from it")],
                    caption=cap)


K4ARMS = [  # (key, label, env, source, hollow)
    ("f1c", "W8A16 prefill", "GLM5_FLASH_FP8_PREFILL=off", "F1-K4", False),
    ("amax", "Scale rule amax", "FP8_SCALES=amax", "F1-K4b", False),
    ("best", "Scale rule best", "FP8_SCALES=best", "F1-K4b", False),
    ("w16amax", "W8A16 + amax", "PREFILL=off + SCALES=amax", "K4c", False),
    ("w16best", "W8A16 + best", "PREFILL=off + SCALES=best", "K4d", False),
    ("head16", "Output head BF16", "GLM5_FLASH_FP8_HEAD=off", "F1-K4b", True),
    ("kda16", "KDA projections BF16", "GLM5_FLASH_KDA_FP8=off", "F1-K4b", True),
    ("all16", "Every switch", "best + KDA + head BF16 + W8A16", "F1-K4b", True)]


def k4_settings(K):
    """{arm: {'pa_c', 'pb8_c', 'pb8_v', 'pa_v', 'pb_v': (diff, lo, hi) or None}} from the published follow-up summaries."""
    f = R4D / "f1k4"
    b = B.load(f / "score-b" / "f1b-summary.json"); c = B.load(f / "score-c" / "f1c2-summary.json"); d = B.load(f / "score-d" / "f1d2-summary.json")
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


def clusters_816(run, K=None):
    """Windows behind the P-B 8-16K bucket (the paired comparison's clusters)."""
    if run == "k4": return K["pb"]["paired"]["C-r1-Vmean"]["gen 8-16K"]["clusters"]
    return B.load(D / "q/pb/pb-pair-V1-C1.json")["gen"]["by_bucket"]["8-16K"]["clusters"]


def k4_setting_speed():
    """Per content cell: median per request; arm ÷ the mean of its two bracketing as-shipped launches (the method of the
    F1-K4 speed table in results/<k4>/README.md). Returns {arm: (ttft median, min, max, decode min, decode max, cells)}."""
    import statistics as st
    def cells(n):
        out = {}
        for bt in B.load(R4D / "f1k4" / "t" / f"{n}.json")["batches"]:
            if bt["kind"] != "measured": continue
            for g in bt["groups"]:
                for r in g:
                    c = out.setdefault((bt["length"], bt["level"], bt["content"]), {"d": [], "t": []})
                    c["d"].append(r["decode_tok_s"]); c["t"].append(r["ttft_s"])
        return {k: (st.median(v["d"]), st.median(v["t"])) for k, v in out.items()}
    res = {}
    for arm, f, b1, b2 in (("f1c", "C-f1c", "C-base1", "C-base2"), ("w16amax", "C-c-w16amax", "C-c-base1", "C-c-base2"),
                           ("w16best", "C-d-w16best", "C-d-base1", "C-d-base2")):
        A, X1, X2 = cells(f), cells(b1), cells(b2)
        tt = [A[k][1] / ((X1[k][1] + X2[k][1]) / 2) for k in sorted(A)]
        de = [A[k][0] / ((X1[k][0] + X2[k][0]) / 2) for k in sorted(A)]
        res[arm] = (st.median(tt), min(tt), max(tt), min(de), max(de), len(tt))
    return res


def fig_settings_k4(K, fid="settings-k4"):
    S = k4_settings(K); T = K["T"]
    panels = []
    for key, sec in (("pa_c", "P-A, KL20 from the BF16 teacher"), ("pb8_c", "P-B 8-16K, KL_pb20 (long code reading, the most sensitive slice)")):
        rows = []; panels.append((sec, rows))
        for a, lab, env, src, hol in K4ARMS:
            v = S[a].get(key)
            if v is None:
                rows.append({"label": lab, "sub": env, "est": None, "value": "not published", "hollow": hol,
                             "title": f"{lab}: no {sec} difference against as shipped is published ({src})"}); continue
            rows.append(frow(lab, *v, None, f"{lab} ({env}), {sec}: {sg(v[0])} {cit(v[1], v[2])} against CuteAFD as shipped ({src})"
                             + ("; does not fit a serving launch on 2x RTX with K4" if hol else ""), sub=env, hollow=hol))
        v = S["nospec"][key]
        rows.append({"label": "Control: drafter removed", "sub": "validation row, identical rows", "est": v[0], "lo": v[1], "hi": v[2],
                     "who": "c", "hollow": False, "muted": True, "resolved": False, "value": f"{sg(v[0])} (validation)",
                     "title": "Control arm nospec (validation, not a setting): the as-shipped scoring launch without the drafter; raw-logit "
                              "row hashes identical to as shipped on every scored row, so drafter-off launches measure only their switch"})
    svgs = [C.forest(rows, ref="CuteAFD as shipped", ref_who="c", left="closer to BF16", right="further from BF16",
                     aria=f"CuteAFD settings against CuteAFD as shipped, K4: {sec}") for sec, rows in panels]
    tab = []
    for a, lab, env, src, hol in K4ARMS + [("nospec", "Control: drafter removed (validation)", "SPECULATOR=off", "F1-K4b", True)]:
        f = lambda k: f"{sg(S[a][k][0])} {cit(*S[a][k][1:])}" if S[a].get(k) else "not published"
        tab.append([f"{lab}<br><span class=\"ci\">{E(env)}</span>", f("pa_c"), f("pb8_c"), "no" if hol and a != "nospec" else ("scoring control" if a == "nospec" else "yes"), src])
    table = htable(["Setting", "P-A KL20 − as shipped", "P-B 8-16K − as shipped", "Serves on 2x RTX with K4", "Follow-up"], tab) + \
        ('<p class="sign">Sources: <code>f1k4/score/f1c-minus-c1.json</code> (W8A16), <code>f1k4/score-b/f1b-summary.json</code> '
         '(amax, best, head, KDA, every switch, control), <code>f1k4/score-c/f1c2-summary.json</code> (W8A16 + amax), '
         '<code>f1k4/score-d/f1d2-summary.json</code> (W8A16 + best; it publishes no P-A difference against as shipped). '
         'Band: none, CuteAFD repeats are byte-identical. Intervals: window-cluster bootstrap; each summary file draws its own.</p>')
    return C.figure(fid, "K4: CuteAFD settings against CuteAFD as shipped (reference: CuteAFD as shipped; top-20 measures)",
                    "How far each CuteAFD setting moves it towards (left) or away from (right) BF16 on K4, paired on the same "
                    "positions, one panel per measure; hollow triangles do not fit a serving launch on 2x RTX with K4 and were measured on scoring launches.",
                    [(svgs[0], strip(T, "k4", "pa"), panels[0][0]),
                     (svgs[1], spec_band("P-B 8-16K, long code reading", pb_band(T, "8-16K")["positions"], clusters_816("k4", K),
                                         pb_band(T, "8-16K")["context"], REF["k4"]["pb"][0], REF["k4"]["pb"][1]), panels[1][0])],
                    "If you serve K4 on 2x RTX, compare only the filled triangles: W8A16 + amax moves the long-code row the most "
                    "among them. The hollow ones show what more memory (larger GPUs) would buy.",
                    table, LG_SET + [("refc", "CuteAFD as shipped")])


def fig_map_k4(K, fid="map-k4"):
    S = k4_settings(K); spd = k4_setting_speed()
    lab = {"shipped": "as shipped", "f1c": "W8A16", "amax": "amax", "best": "best", "w16amax": "W8A16 + amax", "w16best": "W8A16 + best",
           "head16": "head BF16", "kda16": "KDA BF16", "all16": "every switch"}
    hol = {a: h for a, _, _, _, h in K4ARMS}
    pts, tab = [], []
    for a in ("shipped", "f1c", "w16amax", "w16best", "amax", "best", "head16", "kda16", "all16"):
        v = S[a]["pb8_v"]; x = 0.0 if a == "shipped" else (100 * (spd[a][0] - 1) if a in spd else None)
        pts.append({"label": lab[a], "x": x, "y": v[0], "lo": v[1], "hi": v[2], "hollow": hol.get(a, False),
                    "title": f"{lab[a]}: " + (f"first token {x:+.1f}% vs as shipped; " if x is not None else "speed not measured; ")
                             + f"still {sg(v[0])} {cit(v[1], v[2])} KL_pb20 from the vLLM fork at 8-16K"
                             + ("; does not fit a serving launch on 2x RTX" if hol.get(a) else "")})
        sp = spd.get(a)
        tab.append([lab[a], ("0 (reference)" if a == "shipped" else (f"{100 * (sp[0] - 1):+.1f}% ({100 * (sp[1] - 1):+.1f} to {100 * (sp[2] - 1):+.1f}%)"
                    if sp else "not measured")).replace("-", C.MINUS),
                    "1.00x (reference)" if a == "shipped" else (f"{sp[3]:.2f}-{sp[4]:.2f}x per cell" if sp else "not measured"),
                    f"{sg(v[0])} {cit(v[1], v[2])}", "no" if hol.get(a) else "yes"])
    sh = S["shipped"]["pb8_v"][0]; w = S["w16amax"]["pb8_v"][0]
    s = C.settings_map(pts, aria="Settings map K4: first-token cost against the remaining difference from the vLLM fork", shipped_y=sh,
                       xlabel="time to first token, % change vs CuteAFD as shipped (median of 8 cells)",
                       ylabel="KL_pb20 difference from the vLLM fork, P-B 8-16K (long code)", gutter="speed not measured")
    cap = (f"W8A16 + amax: about two thirds ({100 * (sh - w) / sh:.0f}%) of the long-code difference closed ({sg(sh)} → {sg(w)}) "
           f"for about {100 * (spd['w16amax'][0] - 1):.0f}% longer time to first token, with decode level; it still differs from the "
           f"vLLM fork. W8A16 + best closes less ({sg(S['w16best']['pb8_v'][0])}). The BF16 options close less than W8A16 + amax "
           f"on their own and do not fit a serving launch on 2x RTX; every switch together ({sg(S['all16']['pb8_v'][0])}) does not "
           "fit either. The scale rules alone change stored values only; their speed was not measured.")
    table = htable(["Setting", "Time to first token vs as shipped, median of cells (range)", "Decode vs as shipped", "Remaining KL_pb20 difference from the vLLM fork, 8-16K", "Serves on 2x RTX"], tab) + \
        ('<p class="sign">Speed: per content cell (1K and 32K input, 1 and 4 streams, code and prose; 8 requests each), the median '
         'per request, divided by the mean of the two as-shipped launches run before and after the setting: the method of the '
         'F1-K4 speed table. <code>f1k4/RESULTS-F1K4b.md</code> reports +4.1-4.3% (W8A16 + amax) and +4% (W8A16 + best) by its own '
         'aggregation. Decode stayed inside the base-to-base band for all three measured settings. No interval is published for '
         'the speed ratios.</p>')
    return C.figure(fid, "K4 settings map: what each CuteAFD setting costs and what it closes",
                    "Each triangle is one CuteAFD setting on K4: across, its time-to-first-token cost against as shipped; up and down, "
                    "how far it still is from the vLLM fork on long code reading (8-16K), with its 95% interval. Decode speed is level "
                    "for every setting whose speed was measured.",
                    [(s, spec_band("P-B 8-16K, long code reading", pb_band(K["T"], "8-16K")["positions"], clusters_816("k4", K),
                                   pb_band(K["T"], "8-16K")["context"], REF["k4"]["pb"][0], REF["k4"]["pb"][1]), None)],
                    "On 2x RTX, read the filled triangles: the lowest one is the closest-to-vLLM setting that serves, and its "
                    "position across is what it costs at the first token. Hollow ones need more GPU memory.",
                    table, [("c", "serves on 2x RTX"), ("ch", "does not fit a serving launch on 2x RTX"), ("gut", "speed not measured"),
                            ("refdv", "vLLM fork (0)"), ("refdc", "CuteAFD as shipped"), ("ci", "interval excludes 0"), ("ciu", "includes 0")],
                    caption=cap)


# ---- precision: tails and position

def rows_csv(path, select, cols):
    import csv
    with open(path, newline="") as f:
        out = {c: [] for c in cols}
        for r in csv.DictReader(f):
            if not select(r): continue
            for c in cols:
                if r[c] != "": out[c].append(float(r[c]))
    return {c: sorted(v) for c, v in out.items()}


QM = (("kl_p50", 0.5), ("kl_p90", 0.1), ("kl_p99", 0.01), ("kl_p99.9", 0.001))


def qmarks(s, name):
    return [(s[k], share, f"{name}: {100 * share:g}% of positions above KL {s[k]:.4g} ({k[3:]}, published)") for k, share in QM]


TAILS = {  # run -> panel -> (csv columns per arm, arm keys in the tails file, select)
    "k325": {"pa": ({"V1": "kl_V1", "V1r": "kl_V1r", "V2": "kl_V2", "C1": "kl_C1"}, lambda r: True),
             "pb": ({"V1": "kl_V1", "V1r": "kl_V1r", "V2": "kl_V2", "C1": "kl_C1"}, lambda r: r["role"] == "gen")},
    "k4": {"pa": ({"Vr1": "kl20_Vr1", "Vr2": "kl20_Vr2", "Cr1": "kl20_Cr1"}, lambda r: True),
           "pb": ({"Vr1": "klpb20_Vr1", "Vr1b": "klpb20_Vr1b", "Vr2": "klpb20_Vr2", "Cr1": "klpb20_Cr1"}, lambda r: r["role"] == "gen")}}
NAMES = {"V1": "vLLM V1", "V1r": "vLLM V1r", "V2": "vLLM V2", "C1": "CuteAFD", "Vr1": "vLLM launch 1", "Vr1b": "vLLM launch 1 repeat",
         "Vr2": "vLLM launch 2", "Cr1": "CuteAFD"}


def fig_tails(run, key, T, rows_dir, fid, metric, tables):
    cols, sel = TAILS[run][key]
    vals = rows_csv(rows_dir / ("pa-rows.csv" if key == "pa" else "pb-rows.csv"), sel, list(cols.values()))
    P = T[key]; arms = P["arms"]
    vs = [a for a in cols if a.startswith("V")]; ca = [a for a in cols if a.startswith("C")][0]
    series = [{"name": NAMES[a], "who": "v", "values": vals[cols[a]], "thin": i > 0, "label": f"vLLM fork ({len(vs)} runs)" if i == 0 else None,
               "marks": qmarks(arms[a], NAMES[a]) if i == 0 else []} for i, a in enumerate(vs)]
    series.append({"name": "CuteAFD", "who": "c", "values": vals[cols[ca]], "label": "CuteAFD", "marks": qmarks(arms[ca], "CuteAFD")})
    ex = C.exceedance(series, aria=f"Exceedance of per-position {metric}, panel {key.upper()}, {run}", xlabel=f"per-position {metric} (log scale)")
    bands = P["by_position"]
    cats = [(b["band"].replace("rows ", "rows "), f"history {num(b['context']['min'])}-{num(b['context']['max'])}") for b in bands]
    vmean_ = lambda b: sum(b["arms"][a]["kl_mean"] for a in vs) / len(vs)
    prof = C.profile(cats, [{"name": "vLLM", "who": "v", "values": [vmean_(b) for b in bands],
                             "titles": [f"vLLM fork (mean of {len(vs)} runs), {b['band']}, history {hist(b['context'])}: mean {metric} {vmean_(b):.4f}" for b in bands]},
                            {"name": "CuteAFD", "who": "c", "values": [b["arms"][ca]["kl_mean"] for b in bands],
                             "titles": [f"CuteAFD, {b['band']}, history {hist(b['context'])}: mean {metric} {b['arms'][ca]['kl_mean']:.4f}" for b in bands]}],
                     aria=f"Mean {metric} by history, panel {key.upper()}, {run}", ylabel=f"mean {metric} per position band")
    v0 = vs[0]
    conc = C.concentration([(f"Top {p}% of positions", [("v", arms[v0][f"kl_share_top{p}pct"], f"{NAMES[v0]}: the top {p}% of positions carry "
                                                         f"{100 * arms[v0][f'kl_share_top{p}pct']:.1f}% of its total {metric}"),
                                                        ("c", arms[ca][f"kl_share_top{p}pct"], f"CuteAFD: the top {p}% of positions carry "
                                                         f"{100 * arms[ca][f'kl_share_top{p}pct']:.1f}% of its total {metric}")]) for p in (1, 5, 10)],
                           aria=f"Concentration of {metric} in the highest positions, panel {key.upper()}, {run}")
    sp = strip(T, run, key)
    title = {"pa": "P-A", "pb": "P-B"}[key]
    return C.figure(fid, f"{title} tails and position ({'K3.25' if run == 'k325' else 'K4, top-20'}): {metric}",
                    f"Three views of the same {P['scored']['selected_positions_total']:,} per-position scores: how often a position's "
                    f"{metric} exceeds a value (curves; marks at the published p50, p90, p99 and p99.9), how the mean changes with the "
                    f"history behind a position, and how much of the total the highest positions carry.",
                    [(ex, sp, "Share of positions above a KL"), (prof, None, "Mean KL by history"), (conc, None, "Concentration: share of the total KL in the top positions")],
                    "If the curves run together, the engines differ in the bulk of positions, not in a few outliers; if CuteAFD's "
                    "curve sits right of the vLLM fork's in the tail, rare large disagreements drive its mean. A panel's mean depends "
                    "on which positions it scores, so compare engines within a panel.",
                    tables, [("lnv", "vLLM fork (each run; marks on the first)"), ("lnc", "CuteAFD"), ("v", "published quantile, vLLM"),
                             ("c", "published quantile, CuteAFD")])


def fig_q2_tails(run, T, rows_dir, fid, metric):
    P = T["q2"]
    if run == "k325":
        cols = {"between": ("kl_C1_V1", "KL(C1 || V1)"), "within": ("kl_V1_V1r", "KL(V1 || V1r)")}
        bt = [("KL(C1 || V1)", "kl_C1_V1", "CuteAFD vs vLLM")]; wt = ("KL(V1 || V1r)", "kl_V1_V1r", "vLLM vs its repeat")
    else:
        bt = [("KL20n(V-r1 || C-r1)", "kl20n_Vr1_Cr1", "CuteAFD vs vLLM launch 1"), ("KL20n(V-r2 || C-r1)", "kl20n_Vr2_Cr1", "CuteAFD vs vLLM launch 2")]
        wt = ("KL20n(V-r1 || V-r2)", "kl20n_Vr1_Vr2", "vLLM launch 1 vs 2")
    vals = rows_csv(rows_dir / "q2-rows.csv", lambda r: True, [c for _, c, _ in bt] + [wt[1]])
    series = [{"name": wt[2], "who": "v", "values": vals[wt[1]], "label": wt[2], "marks": qmarks(P["within_engine"][wt[0]], wt[2])}]
    for i, (k, c, nm) in enumerate(bt):
        series.append({"name": nm, "who": "c", "values": vals[c], "label": nm, "thin": i > 0, "marks": qmarks(P["between_engines"][k], nm) if i == 0 else []})
    ex = C.exceedance(series, aria=f"Exceedance of engine disagreement on Q2, {run}", xlabel=f"per-position {metric} between two runs (log scale)")
    b0, w0 = P["between_engines"][bt[0][0]], P["within_engine"][wt[0]]
    conc = C.concentration([(f"Top {p}% of positions", [("v", w0[f"kl_share_top{p}pct"], f"{wt[2]}: top {p}% carry {100 * w0[f'kl_share_top{p}pct']:.1f}%"),
                                                        ("c", b0[f"kl_share_top{p}pct"], f"{bt[0][2]}: top {p}% carry {100 * b0[f'kl_share_top{p}pct']:.1f}%")]) for p in (1, 5, 10)],
                           aria=f"Concentration of disagreement on Q2, {run}", names={"v": "vLLM vs itself", "c": "CuteAFD vs vLLM"})
    rows = [[nm, f"{s['n']:,}", f"{s['kl_mean']:.4f}", f"{s['kl_p50']:.4f}", f"{s['kl_p90']:.3f}", f"{s['kl_p99']:.3f}", f"{s['kl_p99.9']:.2f}",
             f"{s['kl_max']:.2f}", f"{100 * s['top1_agree']:.2f}%"] for nm, s in [(n, P["between_engines"][k]) for k, _, n in bt] + [(wt[2], w0)]]
    table = htable(["Pair", "Positions", "Mean", "p50", "p90", "p99", "p99.9", "Max", "Top-1 agreement"], rows)
    return C.figure(fid, f"Q2 disagreement ({'K3.25' if run == 'k325' else 'K4, top-20'}): CuteAFD against the vLLM fork, and the vLLM fork against itself",
                    "There is no BF16 reference beyond 14K tokens, so Q2 compares the engines with each other: the orange curve is "
                    "how far CuteAFD's next-token distribution is from the vLLM fork's, the blue curve how far the vLLM fork is from "
                    f"its own repeat (the noise to compare against; it covers {w0['n']:,} of the {b0['n']:,} positions).",
                    [(ex, spec_strip(T["q2"]["scored"], PANEL["q2"], "none (engine against engine)", f"{metric} between two runs (disagreement), nats",
                                   SEL["q2"]), "Share of positions above a disagreement"), (conc, None, "Concentration of the disagreement")],
                    "The gap between the two curves is the engine difference that is not run-to-run noise; it says nothing about "
                    "which engine is closer to BF16 at these lengths.",
                    table, [("lnv", "vLLM fork against its own repeat"), ("lnc", "CuteAFD against the vLLM fork"), ("v", "published quantile"), ("c", "published quantile")])


# ---- throughput: speed-ratio forests (CuteAFD ÷ vLLM fork, log scale)

def k325_cells():
    rec = B.t_receipts(); cv, cc = B.t_cells(rec["V1"]), B.t_cells(rec["C1"])
    out = {}
    for k in cv:
        if k not in cc: continue
        g = lambda c, key: B.t_med(c, key, k)
        out[k] = {"dec": (g(cv, "decode_tok_s_per_stream_median"), g(cc, "decode_tok_s_per_stream_median")),
                  "agg": (g(cv, "aggregate_tok_s"), g(cc, "aggregate_tok_s")), "ttft": (g(cv, "ttft_median_s"), g(cc, "ttft_median_s"))}
    return out


def k4_cells(K):
    import ast
    out = {}
    for k, c in K["tc"]["cells"].items():
        L, content, lv = ast.literal_eval(k)
        out[(L, content, lv)] = {"dec": (c["V"]["decode_med"], c["C"]["decode_med"]), "agg": (c["V"]["aggregate"], c["C"]["aggregate"]),
                                 "ttft": (c["V"]["ttft_med"], c["C"]["ttft_med"]), "read": {"dec": c["C"]["decode_med_reading"], "agg": c["C"]["aggregate_reading"]},
                                 "ratio": {"dec": c["C"]["decode_med_ratio_vs_V"], "agg": c["C"]["aggregate_ratio_vs_V"]}}
    return out


UNIT = {"dec": "tok/s per stream", "agg": "tok/s", "ttft": "s"}
CN = {"json": "JSON"}


def speed_row(label, cells, m, band, run, sub=None):
    """One forest row: a small mark per content cell, a larger mark at the median over them."""
    import statistics as st
    dots, rs = [], []
    for (L, content, lv), c in cells:
        v, cu = c[m]; r = c["ratio"][m] if run == "k4" and m in ("dec", "agg") else cu / v
        if m == "ttft": res = True
        elif run == "k4": res = c["read"][m] != "level"
        else: res = not (band[0] <= r <= band[1])
        rs.append(r)
        dots.append((r, f"{L // 1024}K, {CN.get(content, content)}, {lv} stream{'s' if lv > 1 else ''}: CuteAFD {cu:.2f} vs vLLM fork {v:.2f} "
                        f"{UNIT[m]} = {r:.2f}x" + (f" ({c['read'][m]})" if run == "k4" and m in ("dec", "agg") else ""), res))
    med = st.median(rs)
    rng = f"{min(rs):.2f}-{max(rs):.2f}x" if len(rs) > 1 else ""
    return {"label": label, "sub": sub, "est": med, "band": band, "who": "c", "dots": dots, "value": f"{rx(med)}" + (f" ({rng})" if rng else ""),
            "title": f"{label}: median over {len(rs)} content cells {med:.2f}x" + (f", cells {rng}" if rng else "")}, rs


def speed_groups(cells):
    G = {}
    for k, c in cells.items(): G.setdefault((k[0], k[2]), []).append((k, c))
    order = {"prose": 0, "code": 1, "reasoning": 2, "json": 3}
    return {g: sorted(v, key=lambda kc: order.get(kc[0][1], 9)) for g, v in sorted(G.items())}


SPEED = {"dec": ("Decode speed per stream", "slower", "faster", "decode"), "agg": ("Aggregate throughput", "fewer tokens per second", "more", "aggregate"),
         "ttft": ("Time to first token", "sooner", "later", "first token")}


def fig_speed(run, m, cells, fid, band, bandnote, extra_table=""):
    G = speed_groups(cells); rows, tab = [], []
    for L in sorted({g[0] for g in G}):
        rows.append({"section": f"{L // 1024}K input"})
        for (LL, lv), cs in G.items():
            if LL != L: continue
            r, rs = speed_row(f"{lv} stream{'s' if lv > 1 else ''}", cs, m, band, run)
            rows.append(r)
            for (L_, content, lv_), c in cs:
                v, cu = c[m]; rr = c["ratio"][m] if run == "k4" and m in ("dec", "agg") else cu / v
                tab.append([f"{L_ // 1024}K", CN.get(content, content), str(lv_), f"{v:.2f}", f"{cu:.2f}", f"{rr:.2f}x",
                            (c["read"][m] if run == "k4" and m in ("dec", "agg") else ("level" if band[0] <= rr <= band[1] else ("outside the band")))])
    name, left, right, short = SPEED[m]
    s = C.forest(rows, ref="vLLM fork", ref_who="v", scale="log", left=left if m != "agg" else "fewer tokens/s", right=right if m != "agg" else "more tokens/s",
                 aria=f"{name}, CuteAFD ÷ vLLM fork, per cell, {run}", label_w=120, value_w=150)
    ck = "K3.25" if run == "k325" else "K4"
    what = {"dec": f"Per-stream generation speed of CuteAFD divided by the vLLM fork's, per input length and number of streams ({ck}); "
                   "small triangles are the content types, the large one their median, log scale.",
            "agg": f"All completion tokens of a batch per second of wall time, CuteAFD ÷ vLLM fork ({ck}); small triangles are the content "
                   "types, the large one their median.",
            "ttft": f"Time from sending a request to its first token, CuteAFD ÷ vLLM fork ({ck}); left of the blue line CuteAFD answers sooner."}[m]
    how = {"dec": "Find the row that matches how many requests you run at once and how long the prompts are: to the right of the band, "
                  "CuteAFD generates faster there. At long inputs with several streams the ratio mostly reflects scheduling (Caveats).",
           "agg": "If you care about total tokens per second for a batch, this is the row to read; at long inputs CuteAFD's faster "
                  "prefill is what moves it.",
           "ttft": "If first-token latency matters (interactive use), read the row for your prompt length and concurrency: short "
                   "prompts favour the vLLM fork, long single prompts CuteAFD; many long prompts at once favour the vLLM fork."}[m]
    head = ["Input", "Content", "Streams", f"vLLM fork, {UNIT[m]}", f"CuteAFD, {UNIT[m]}", "CuteAFD ÷ vLLM", "Reading"]
    table = htable(head, tab) + f'<p class="sign">{bandnote}</p>' + extra_table
    lg = [("dotc", "content type, outside the band"), ("dotcu", "content type, inside the band (not a difference)"), ("c", "median of the content types"),
          ("refv", "vLLM fork (1.0)"), ("band", bandnote.split(":")[0])] if m != "ttft" else \
         [("dotc", "content type"), ("c", "median of the content types"), ("refv", "vLLM fork (1.0)"), ("band", "throughput noise band, for scale")]
    return C.figure(fid, f"{ck}: {name.lower()}, CuteAFD ÷ vLLM fork (reference: vLLM fork)", what, [(s, None, None)], how, table, lg)


# ---- index headline: one figure per checkpoint, precision and speed rows

def headline_speed_rows(cells, run, band, spec_rows):
    rows = []
    for m, label, sub, sel in spec_rows:
        cs = [(k, c) for k, c in sorted(cells.items()) if sel(k)]
        r, _ = speed_row(label, cs, m, band, run, sub=(f"{sub}, " if sub else "") + f"{len(cs)} cells")
        rows.append(r)
    return rows


MEASURE = {"k325": {"pa": "P-A: full-vocabulary KL from the BF16 teacher", "pb": "P-B: coarse KL (top 1,024 + tail)",
                    "q2": "Q2: NLL of human-written text, 32K-128K (no BF16 reference)"},
           "k4": {"pa": "P-A: KL20 from the BF16 teacher (top-20 measure)", "pb": "P-B: KL_pb20 (top-20 measure)",
                  "q2": "Q2: NLL of human-written text, 32K-128K (no BF16 reference)"}}


def measure_panels(run, groups, aria):
    """Small multiples, one panel per measure in the fixed order P-A, P-B, Q2; each with its own axis and reference line.
    groups: {panel key: rows}."""
    out = []
    for key in ("pa", "pb", "q2"):
        rows = groups.get(key)
        if not rows: continue
        kw = (dict(left="CuteAFD lower NLL", right="CuteAFD higher NLL") if key == "q2" else dict(left="closer to BF16", right="further from BF16"))
        svg = C.forest(rows, ref="vLLM fork", ref_who="v", aria=f"{aria}: {MEASURE[run][key]}", **kw)
        out.append((svg, None, MEASURE[run][key]))
    return out


def headline_table(groups, run):
    out = []
    for key in ("pa", "pb", "q2"):
        sec = ""
        for r in groups.get(key, []):
            if "section" in r: sec = r["section"]; continue
            out.append([E(MEASURE[run][key]), E(sec), E(r["label"]) + (f'<br><span class="ci">{E(r["sub"])}</span>' if r.get("sub") else ""),
                        sg(r["est"]), cit(r["lo"], r["hi"]), f'±{r["band"][1]:.4f}' if r.get("band") else "n/a"])
    return htable(["Measure", "CuteAFD", "Rows", "CuteAFD − vLLM fork", "95% interval", "vLLM run-to-run band"], out)


def fig_headline_k325(F, fid="headline-k325"):
    pa, pb, q2 = k325_engine_rows(F); d = F["d"]; T = F["T"]
    wrows = []
    for i, (b, lab) in enumerate((("all", "All generated rows"), ("8-16K", "8-16K, long code"))):
        v = d[(b, "kl", "F1c")]
        wrows.append(frow(lab, v[0], v[1], v[2], (pb[0] if b == "all" else pb[3])["band"],
                          f"CuteAFD with W8A16 prefill, P-B {lab}: {sg(v[0])} {cit(v[1], v[2])} coarse KL against the mean of 3 vLLM runs"))
    groups = {"pa": [{"section": "CuteAFD as shipped"}, dict(pa[0], label="All positions", sub="25 windows, vs vLLM V1")],
              "pb": [{"section": "CuteAFD as shipped"}, dict(pb[0], sub=None), dict(pb[3], sub=None),
                     {"section": "CuteAFD with W8A16 prefill"}] + wrows,
              "q2": [{"section": "CuteAFD as shipped"}, dict(q2[0])]}
    prec = measure_panels("k325", groups, "Headline precision, K3.25")
    cells = k325_cells(); band = (0.9, 1.1)
    sp = C.forest(headline_speed_rows(cells, "k325", band, [
        ("dec", "Decode, 1 stream", "1K-128K", lambda k: k[2] == 1),
        ("agg", "Throughput, 32K-128K", "1-16 streams", lambda k: k[0] >= 32768),
        ("agg", "Throughput, 1K × 8 streams", "", lambda k: k[0] == 1024 and k[2] == 8)]),
        ref="vLLM fork", ref_who="v", scale="log", left="CuteAFD slower", right="faster", aria="Headline speed, K3.25")
    tt = C.forest(headline_speed_rows(cells, "k325", band, [
        ("ttft", "1K prompt, 1 stream", "", lambda k: k[0] == 1024 and k[2] == 1),
        ("ttft", "8K-128K, 1 stream", "", lambda k: k[0] >= 8192 and k[2] == 1),
        ("ttft", "32K-128K, 4-16 streams", "", lambda k: k[0] >= 32768 and k[2] > 1)]),
        ref="vLLM fork", ref_who="v", scale="log", left="CuteAFD sooner", right="later", aria="Headline time to first token, K3.25")
    table = headline_table(groups, "k325") + \
        '<p class="sign">W8A16 prefill (follow-up F1) was scored on P-B only. Q2 band: vLLM\'s repeat on 2 documents.</p>' + \
        htable(["Speed row", "CuteAFD ÷ vLLM fork, median (range of cells)"], [[E(r["label"] + ", " + r["sub"]), r["value"]] for r in
               headline_speed_rows(cells, "k325", band, [("dec", "Decode, 1 stream", "1K-128K", lambda k: k[2] == 1),
                                                         ("agg", "Throughput", "32K-128K", lambda k: k[0] >= 32768),
                                                         ("agg", "Throughput", "1K × 8 streams", lambda k: k[0] == 1024 and k[2] == 8),
                                                         ("ttft", "First token", "1K, 1 stream", lambda k: k[0] == 1024 and k[2] == 1),
                                                         ("ttft", "First token", "8K-128K, 1 stream", lambda k: k[0] >= 8192 and k[2] == 1),
                                                         ("ttft", "First token", "32K-128K, 4-16 streams", lambda k: k[0] >= 32768 and k[2] > 1)])]) + \
        '<p class="sign">Speed band: ±10%, the drift check\'s reading ("ratios within about ±10% are not differences").</p>'
    charts = [(prec[0][0], strip(T, "k325", "pa"), "Precision, CuteAFD − vLLM fork \u00b7 " + prec[0][2])] + \
             [(sv, strip(T, "k325", k), h) for (sv, _, h), k in zip(prec[1:], ("pb", "q2"))] + \
             [(sp, None, "Speed, CuteAFD ÷ vLLM fork"), (tt, None, "Time to first token, CuteAFD ÷ vLLM fork")]
    return C.figure(fid, "K3.25 in one view: precision (one panel per measure) and speed",
                    "Precision panels, one per measure, each on its own axis: CuteAFD's distance from BF16 minus the vLLM fork's "
                    "(right = CuteAFD further; Q2 compares NLL, as it has no BF16 reference). Then CuteAFD's speed and first-token "
                    "time divided by the vLLM fork's, log scale. Every row is read against the blue line of its own panel.",
                    charts,
                    "Rows to the right in the precision panels favour the vLLM fork; rows to the right in the speed panel favour "
                    "CuteAFD; in the first-token panel left favours CuteAFD. Compare rows within a panel, not across panels. "
                    "Choose by the rows that match your workload (below).",
                    table, LG_ENGINE + [("dotc", "one throughput cell")])


def fig_headline_k4(K, fid="headline-k4"):
    pa, pb, q2 = k4_engine_rows(K); S = k4_settings(K); T = K["T"]
    w = lambda key, lab, band, sub=None: frow(lab, *S["w16amax"][key], band, f"CuteAFD with W8A16 + amax, {lab}: {sg(S['w16amax'][key][0])} "
                                               f"{cit(*S['w16amax'][key][1:])} against the mean of 2 vLLM launches (K4c)", sub=sub)
    groups = {"pa": [{"section": "CuteAFD as shipped"}, dict(pa[0], label="All positions"),
                     {"section": "CuteAFD with W8A16 + amax (serves on 2x RTX)"}, w("pa_v", "All positions", pa[0]["band"], "25 windows")],
              "pb": [{"section": "CuteAFD as shipped"}, dict(pb[0], sub=None), dict(pb[3], label="8-16K, long code", sub=None),
                     {"section": "CuteAFD with W8A16 + amax (serves on 2x RTX)"}, w("pb_v", "All generated rows", pb[0]["band"]),
                     w("pb8_v", "8-16K, long code", pb[3]["band"])],
              "q2": [{"section": "CuteAFD as shipped"}, dict(q2[0])]}
    prec = measure_panels("k4", groups, "Headline precision, K4")
    cells = k4_cells(K); band = (0.92, 1.08)
    spec = [("dec", "Decode, 1 stream", "1K-128K", lambda k: k[2] == 1), ("dec", "Decode, 4 streams", "1K-32K", lambda k: k[2] == 4),
            ("agg", "Throughput, all cells", "1 and 4 streams", lambda k: True)]
    sp = C.forest(headline_speed_rows(cells, "k4", band, spec), ref="vLLM fork", ref_who="v", scale="log", left="CuteAFD slower", right="faster",
                  aria="Headline speed, K4")
    spec_t = [("ttft", "1K prompt, 1 stream", "", lambda k: k[0] == 1024 and k[2] == 1), ("ttft", "8K-128K, 1 stream", "", lambda k: k[0] >= 8192 and k[2] == 1),
              ("ttft", "32K, 4 streams", "", lambda k: k[0] == 32768 and k[2] == 4)]
    tt = C.forest(headline_speed_rows(cells, "k4", band, spec_t), ref="vLLM fork", ref_who="v", scale="log", left="CuteAFD sooner", right="later",
                  aria="Headline time to first token, K4")
    table = headline_table(groups, "k4") + \
        '<p class="sign">The K4c summary publishes no Q2 difference for W8A16 + amax as JSON (its markdown reports +0.0002 [−0.0009, +0.0012]), so Q2 shows as shipped only.</p>' + \
        htable(["Speed row", "CuteAFD ÷ vLLM fork, median (range of cells)"], [[E(r["label"] + ", " + r["sub"]), r["value"]]
                                                                               for r in headline_speed_rows(cells, "k4", band, spec + spec_t)]) + \
        '<p class="sign">Speed band: ±8%, declared before the K4 run; readings per cell in <code>t/t-compare.json</code>. W8A16 + amax: follow-up K4c, outside the frozen protocol.</p>'
    charts = [(sv, strip(T, "k4", k), ("Precision, CuteAFD − vLLM fork \u00b7 " + h) if i == 0 else h)
              for i, ((sv, _, h), k) in enumerate(zip(prec, ("pa", "pb", "q2")))] + \
             [(sp, None, "Speed, CuteAFD ÷ vLLM fork"), (tt, None, "Time to first token, CuteAFD ÷ vLLM fork")]
    return C.figure(fid, "K4 in one view: precision (top-20 measures, one panel per measure) and speed",
                    "The same panels for K4. Precision here is top-20 KL (KL20, KL_pb20), so its numbers are not on the same "
                    "scale as K3.25's; each measure has its own panel and axis, read each row only against its panel's blue line.",
                    charts,
                    "The pattern matches K3.25: the vLLM fork closer to BF16 on long code, CuteAFD faster in decode. With W8A16 + "
                    f"amax, CuteAFD's long-code row drops from {sg(pb[3]['est'])} to {sg(S['w16amax']['pb8_v'][0])} (still resolved) and its P-A "
                    "row is no longer resolved, for about 4% longer time to first token (settings map on the Precision page).",
                    table, LG_ENGINE + [("dotc", "one throughput cell")])


# ---- long output: passes out of n, and reply length

GOOD = {"code": "all tests pass", "reasoning": "correct", "prose": "finished", "json": "valid"}


def passes(s):
    return {"code": s.get("all_pass", 0), "reasoning": s.get("correct", 0), "json": s.get("valid", 0), "prose": s["stop"]}[s["content"]]


def fig_long(L, run, va, ca, fid):
    caps = {"k325": {"L1": "8K cap", "L2": "32K cap", "L3": "128K cap", "L3s": "128K cap, 1 request at a time"},
            "k4": {"L1": "8,192 cap", "L2": "32,768 cap", "L3": "130,048 cap", "L3s": "130,048 cap, 1 request at a time"}}[run]
    rows, lrows, tab = [], [], []
    for st_ in ("L1", "L2", "L3", "L3s"):
        rows.append({"section": f"{st_}, {caps[st_]}"}); lrows.append({"section": f"{st_}, {caps[st_]}"})
        for c in ("code", "reasoning", "prose", "json"):
            v, u = L.get((va, st_, c)), L.get((ca, st_, c))
            if not v or not u: continue
            pv, pc = passes(v), passes(u)
            name = CN.get(c, c)
            rows.append({"label": f"{name}: {GOOD[c]}", "v": (pv, v["n"]), "c": (pc, u["n"]),
                         "title": f"{st_} {name}, {GOOD[c]}: vLLM fork {pv}/{v['n']}, CuteAFD {pc}/{u['n']} (descriptive, n={v['n']})"})
            mv, mc = v["completion_tokens_median"], u["completion_tokens_median"]
            capped = v["cap"] == v["n"] and u["cap"] == u["n"]
            r = mc / mv
            lrows.append({"label": name, "est": r, "who": "c", "resolved": not capped, "muted": capped,
                          "value": f"{rx(r)}" + (" (both at cap)" if capped else f" ({mc / 1000:.1f}K vs {mv / 1000:.1f}K)"),
                          "title": f"{st_} {name}: median reply CuteAFD {mc:,.0f} vs vLLM fork {mv:,.0f} tokens = {r:.2f}x"
                                   + ("; every reply on both engines reached the cap" if capped else "")})
            tab.append([st_, name, f"{v['n']}", f"{pv}/{v['n']}", f"{pc}/{u['n']}", f"{v['stop']} / {v['cap']}", f"{u['stop']} / {u['cap']}",
                        f"{mv:,.0f}", f"{mc:,.0f}", f"{r:.2f}x"])
    s1 = C.paired_share(rows, aria=f"Long-output checks passed, both engines, {run}")
    s2 = C.forest(lrows, ref="vLLM fork", ref_who="v", scale="log", left="CuteAFD shorter", right="longer",
                  aria=f"Median reply length, CuteAFD ÷ vLLM fork, {run}", label_w=120, value_w=170)
    ck = "K3.25" if run == "k325" else "K4"
    table = htable(["Stage", "Content", "n per engine", "vLLM: passed", "CuteAFD: passed", "vLLM: finished / at cap", "CuteAFD: finished / at cap",
                    "vLLM median tokens", "CuteAFD median tokens", "Length ratio"], tab) + \
        ('<p class="sign">Passed: code, every hidden test passes; reasoning, correct MATH-500 answer; prose, the reply finished on '
         'its own; JSON, schema, count and ids valid. Descriptive: 2 seeds per prompt, 4 prompts per content type (n = 8; 1 at '
         'L3s). No interval is published for these counts or for the length ratio.</p>' + f'<p class="sign">{E(B.L_NOTE)}</p>')
    return C.figure(fid, f"{ck}: long-output checks and reply length, both engines (descriptive, small n)",
                    f"Top: for each stage and content type, how many of the n replies passed their check on each engine ({ck}; "
                    "n = 8 per engine, 1 at L3s). Bottom: CuteAFD's median reply length divided by the vLLM fork's.",
                    [(s1, None, "Passed, out of n"), (s2, None, "Median reply length, CuteAFD ÷ vLLM fork")],
                    "If your replies are long, read the 128K rows: where the two marks sit together the engines did the same on "
                    "this small sample. With n = 8, a difference of one or two replies is not evidence of a difference.",
                    table, [("v", "vLLM fork"), ("c", "CuteAFD"), ("refv", "vLLM fork (length 1.0)")])


# ---- startup (observations): stacked phases per launch

def chart_startup(S):
    if not S: return None
    runs = S["runs"]; W, l, r, bh = 640, 4, 70, 16
    tmax = max(x["ready_s"] for x in runs)
    H = 20 + len(runs) * (bh + 30) + 22
    X = lambda s: l + (W - l - r) * s / tmax
    o = [C.svg_open(W, H, "Startup to ready, by phase, per launch")]
    for v in range(0, int(tmax) + 1, 120):
        o.append(f'<line class="grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="14" y2="{H - 20}"/>'
                 + C.tx(X(v), H - 6, f"{v // 60} min", "tick", "start" if v == 0 else "middle"))
    y = 22; tab = []
    for run in runs:
        cu = "cuteafd" in run["label"].lower(); cls = "c2" if cu else "c1"
        o.append(C.marker(l + 5, y + 4, "c" if cu else "v", size=4) + C.tx(l + 14, y + 8, run["label"], "lab"))
        yb = y + 12; x = X(0)
        for i, ph in enumerate(run["phases"]):
            w = X(ph["s"]) - X(0); op = [1.0, 0.72, 0.5, 0.34, 0.22][min(i, 4)]
            o.append(C.tip(f"{run['label']}: {ph['name']} {ph['s']} s",
                           f'<rect class="{cls}" style="opacity:{op}" x="{x:.1f}" y="{yb}" width="{max(w - 2, 1):.1f}" height="{bh}" rx="2"/>'))
            if w > 60 and len(run["phases"]) > 1 and op >= 0.7:
                o.append(C.tx(x + 4, yb + bh - 4, ph["name"].split(" (")[0].replace("process start + ", "")[:int(w / 6.5)], "inbar"))
            x += w; tab.append([run["label"], ph["name"], f"{ph['s']} s"])
        o.append(C.tx(x + 4, yb + bh - 3, f"{run['ready_s']} s", "val")); y += bh + 30
    o.append("</svg>")
    return C.figure("startup", "Startup to ready, per launch (K3.25)",
                    "Seconds from container start to ready for each launch, split into phases (one shade per phase, strongest first).",
                    [("".join(o), None, None)],
                    "If you switch models often, the total at the right is the wait per switch; on this setup persisting the vLLM "
                    "fork's JIT caches removes the TileLang compiles and most of the graph-capture time, and CuteAFD ships its kernels "
                    "compiled.", htable(["Launch", "Phase", "Time"], tab) + f'<p class="sign">{E(S.get("note", ""))}</p>',
                    [("v", "vLLM fork"), ("c", "CuteAFD")])


# ------------------------------------------------------------------ shared blocks

def cards(F):
    d, L = F["d"], F["L"]
    lo, hi = F["dec_range"]; al, ah = F["agg_long"]
    tt1 = F["len"][1024]["tt1"]
    vc, cc = L[("V1", "L3", "code")], L[("C1", "L3", "code")]
    vm, cm = L[("V1", "L3", "reasoning")], L[("C1", "L3", "reasoning")]
    items = [
        ("Precision", f"{F['kl_v']['all']:.3f} vs {F['kl_c']['all']:.3f}",
         "Both engines stay close to the original BF16 model; the 3.25-bit quantization matters more than the engine. "
         "The vLLM fork is slightly closer, mainly when reading long code (8-16K tokens).",
         f"KL from BF16, vLLM fork vs CuteAFD, tpurtell's fidelity set: {F['T']['pb']['scored']['selected_positions_total']:,} "
         f"generated positions with {hist_short(F['T']['pb']['scored']['context'])}. His official FP8 model scores 0.0216 on "
         f"the same set. At 8-16K ({hist_short(pb_band(F['T'], '8-16K')['context'])}): {kl(F['kl_v']['8-16K'])} vs "
         f"{kl(F['kl_c']['8-16K'])}."),
        ("Speed", f"{pct(lo)} to {pct(hi)}",
         f"CuteAFD generates faster for a single user and finishes long-prompt work {span(al, ah)} faster. "
         f"The vLLM fork answers short prompts sooner ({tt1[0][0]:.2f} vs {tt1[0][1]:.2f} s to first token at 1K).",
         f"Single-stream decode, CuteAFD vs vLLM fork, {sum(r['n1'] for r in F['len'].values())} cells from 1K to 128K input; "
         "single cells vary by up to ±13% between runs."),
        ("Long outputs", f"{vc['all_pass']}/{vc['n']} and {cc['all_pass']}/{cc['n']}",
         f"Both ran 100 long-output requests with 0 errors. At the 128K cap, code passed every hidden test in "
         f"{vc['all_pass']} of {vc['n']} replies on both engines, and math was {vm['correct']}/{vm['n']} on both.",
         "Two seeds per prompt, four prompts per content type: small samples."),
        ("Tunable trade-off", f"{dkl(d[('all', 'kl', 'C1')][0])} → {dkl(d[('all', 'kl', 'F1c')][0])}",
         f"CuteAFD's W8A16 prefill halves its overall precision difference for about {pp(F['f1c_ttft'])} longer time to first "
         f"token and no decode cost; with all three FP8 switches off no difference is resolved, at about {pp(F['f1d_dec'])} "
         "slower median decode.",
         f"KL difference from the vLLM fork, all generated rows. At 8-16K: {dkl(d[('8-16K', 'kl', 'C1')][0])} → "
         f"{dkl(d[('8-16K', 'kl', 'F1c')][0])}. Prefill-shaped scoring only."),
        ("Practical differences", "0.017 s",
         "CuteAFD restores a repeated 8K prompt from its prefix cache in 0.017 s; the vLLM fork reuses only whole "
         "4,352-token blocks and none below about 13K tokens. Only CuteAFD honours \"thinking off\". "
         + startup_sentence(),
         "Block T cached cell and follow-up F2; thinking-off check with one request; startup times from the server logs."),
    ]
    return '<div class="cards">' + "".join(
        f'<div class="card"><div class="k">{k}</div><div class="big">{html.escape(big)}</div><p>{html.escape(txt)}</p>'
        f'<div class="ev">{html.escape(ev)}</div></div>' for k, big, txt, ev in items) + "</div>"


def startup_sentence(short=False):
    S = startup()
    if not S: return "Startup times: pending." if not short else "startup times are pending"
    vl = [r for r in S["runs"] if "cuteafd" not in r["label"].lower()]
    cu = [r for r in S["runs"] if "cuteafd" in r["label"].lower()]
    m = lambda s: f"{s / 60:.1f} min"
    c, warm, cold = cu[0]["ready_s"], vl[-1]["ready_s"], vl[0]["ready_s"]
    if short:
        return (f"CuteAFD is ready in about {m(c)} and the vLLM fork in about {m(warm)} with its JIT caches persisted on this "
                f"setup ({m(cold)} without), which matters when switching models")
    return (f"Switching models: CuteAFD about {m(c)}, the vLLM fork about {m(warm)} with its JIT caches persisted "
            f"({m(cold)} without).")


def choosing_items(F, K):
    """'Choosing a setup': (condition, what the data shows, [(link text, href)]). Every number is read from the published
    files; the wording is conditional on the reader's workload, never a recommendation."""
    import statistics as st
    d, rows, L = F["d"], F["len"], F["L"]
    lo, hi = F["dec_range"]; al, ah = F["agg_long"]
    a8 = rows[1024]["agg8"]; t32 = rows[32768]["tth"]
    c3 = k325_cells()
    tt_long = [c["ttft"][1] / c["ttft"][0] for k, c in c3.items() if k[0] >= 8192 and k[2] == 1]
    vc, cc = L[("V1", "L3", "code")], L[("C1", "L3", "code")]; vm, cm = L[("V1", "L3", "reasoning")], L[("C1", "L3", "reasoning")]
    f1c = d[("8-16K", "kl", "F1c")][0]; c816 = d[("8-16K", "kl", "C1")][0]; f1d = d[("8-16K", "kl", "F1d")]
    spd = f1_speed(F)
    items = []
    if K:
        s4 = B.k4_facts_text(K); S4 = k4_settings(K); sp4 = k4_setting_speed(); c4 = k4_cells(K)
        tt4 = [c["ttft"][1] / c["ttft"][0] for k, c in c4.items() if k[0] >= 8192 and k[2] == 1]
        k816 = s4["d_816"]["B_minus_A"]; w = S4["w16amax"]["pb8_v"][0]
        r1 = [c["read"]["dec"] for k, c in c4.items() if k[2] == 1]
    items.append(("If closeness to the BF16 model on long code reading matters most (prompts of 8-16K tokens of source code)",
                  f"the vLLM fork is closer on both checkpoints: CuteAFD as shipped is {dkl(c816)} KL further at 8-16K on K3.25"
                  + (f" and {dkl(k816)} KL_pb20 further on K4 (a top-20 measure, not the same scale)" if K else "") +
                  ". Below 8K on K3.25 no difference is resolved.",
                  [("K3.25", "precision.html#engine-k325")] + ([("K4", "precision.html#engine-k4")] if K else [])))
    items.append(("If you run CuteAFD on K3.25 and want that difference smaller",
                  f"W8A16 prefill (<code>GLM5_FLASH_FP8_PREFILL=off</code>) takes the 8-16K difference from {dkl(c816)} to {dkl(f1c)} "
                  f"for about {pp(spd['f1c'][0])} longer time to first token and level decode ({rx(spd['f1c'][3])}); all three FP8 switches leave "
                  f"no resolved difference ({dkl(f1d[0])}) at about {pp(spd['f1d'][3])} slower median decode. Follow-up F1, outside the frozen protocol.",
                  [("settings map", "precision.html#map-k325")]))
    if K:
        items.append(("If you run CuteAFD on K4 on two RTX PRO 6000s",
                      f"W8A16 prefill with the amax scale rule (<code>GLM5_FLASH_FP8_PREFILL=off</code>, <code>FP8_SCALES=amax</code>) "
                      f"closes about two thirds of the 8-16K difference ({dkl(k816)} → {dkl(w)} KL_pb20) for about {pp(sp4['w16amax'][0])} "
                      "longer time to first token, with decode level. The BF16 KDA and BF16 head options close less on their own and "
                      "do not fit a serving launch there. Follow-ups K4b-K4d, outside the frozen protocol.",
                      [("settings map", "precision.html#map-k4")]))
    items.append(("If you serve one request at a time (a single user, agent loops)",
                  f"CuteAFD's per-stream decode is {lo:.2f}-{hi:.2f}x the vLLM fork's on K3.25 (cells within about ±10% are run-to-run noise)"
                  + (f" and {s4['dec1'][0]:.2f}-{s4['dec1'][1]:.2f}x on K4 (faster in {r1.count('faster')} of {len(r1)} one-stream cells, level in "
                     f"{r1.count('level')})" if K else "") + ".",
                  [("K3.25", "throughput.html#dec-k325")] + ([("K4", "throughput.html#dec-k4")] if K else [])))
    items.append(("If prompts are long (8K-128K tokens) and arrive one at a time",
                  f"CuteAFD's first token comes sooner ({min(tt_long):.2f}-{max(tt_long):.2f}x the vLLM fork's time on K3.25"
                  + (f", {min(tt4):.2f}-{max(tt4):.2f}x on K4" if K else "") + "): its prefill runs at about 4,400-4,500 against "
                  f"3,700-3,900 tokens per second, and at 32K-128K it completes {span(al, ah)} more tokens per second end to end (K3.25). "
                  f"With many long prompts at once its first tokens come later (32K input, {rows[32768]['hi']} streams: "
                  f"{max(b for _, b in t32):.0f} vs {max(a for a, _ in t32):.0f} s), because it schedules prefills ahead of decode.",
                  [("first token", "throughput.html#ttft-k325"), ("throughput", "throughput.html#agg-k325")]))
    items.append(("If prompts are short (about 1K tokens) and many arrive at once",
                  f"the vLLM fork answers sooner ({rows[1024]['tt1'][0][0]:.2f} vs {rows[1024]['tt1'][0][1]:.2f} s to first token at one stream on K3.25) "
                  f"and at 8 streams completes {span(1 / max(a8), 1 / min(a8))} more tokens per second.",
                  [("first token", "throughput.html#ttft-k325"), ("throughput", "throughput.html#agg-k325")]))
    items.append(("If prompts repeat (a long shared prefix)",
                  "CuteAFD restored a repeated 8K prompt from its prefix cache in 0.017 s; the vLLM fork reuses only whole "
                  "4,352-token blocks and none below about 13K tokens.",
                  [("observations", "observations.html#observations-in-detail")]))
    lk = ""
    if K and B.k4_l_summaries():
        L4 = B.k4_l_summaries(); v4, u4 = L4[("V", "L3", "code")], L4[("C", "L3", "code")]; v4m, u4m = L4[("V", "L3", "reasoning")], L4[("C", "L3", "reasoning")]
        lk = (f" On K4 at the 130,048 cap: code {v4['all_pass']}/{v4['n']} and {u4['all_pass']}/{u4['n']}, math {v4m['correct']}/{v4m['n']} "
              f"and {u4m['correct']}/{u4m['n']}.")
    items.append(("If replies are long (up to 128K tokens)",
                  f"both engines did the same on code and math at the 128K cap on K3.25: code passed every hidden test in "
                  f"{vc['all_pass']} of {vc['n']} replies (vLLM fork) and {cc['all_pass']} of {cc['n']} (CuteAFD), math {vm['correct']}/{vm['n']} "
                  f"and {cm['correct']}/{cm['n']}.{lk} Descriptive: 8 replies per content type.",
                  [("K3.25", "long-output.html#long-k325")] + ([("K4", "long-output.html#long-k4")] if lk else [])))
    items.append(("If you switch models often", startup_sentence().replace("Switching models: ", "startup to ready takes "),
                  [("startup", "observations.html#startup")]))
    items.append(("If you need thinking off", "only CuteAFD honours it (one-request check).",
                  [("observations", "observations.html#observations-in-detail")]))
    if K:
        items.append(("If GPU memory is the limit (two RTX PRO 6000s)",
                      "both engines serve K3.25 and K4; CuteAFD needs <code>MAX_CONTEXT_TOKENS=262144</code> to serve K4 there, and its "
                      "BF16 KDA and BF16 head options do not fit a K4 serving launch.",
                      [("K4 observations", "observations.html#k4"), ("K4 settings", "precision.html#settings-k4")]))
        items.append(("If you can choose between the two checkpoints",
                      f"under the same top-20 measure K4 sits roughly half as far from the BF16 teacher as K3.25 on both engines "
                      f"(P-A KL20: vLLM fork {s4['pa25_v']:.4f} → {s4['pa_v']:.4f}, CuteAFD {s4['pa25_c']:.4f} → {s4['pa_c']:.4f}).",
                      [("K4 against K3.25", "precision.html#k4-vs-k325")]))
    return items


def choosing(F, K):
    li = "".join(f'<li><b>{c}:</b> the data shows {t} <span class="ev">Evidence: '
                 + ", ".join(f'<a href="{h}">{E(n)}</a>' for n, h in links) + "</span></li>" for c, t, links in choosing_items(F, K))
    return ('<h2 id="choosing-a-setup">Choosing a setup</h2><p class="plain">What the published results show for common '
            'workloads, each with a link to its evidence. They describe this machine and these checkpoints; they are not a '
            'general ranking.</p><ul class="choose">' + li + '</ul>'
            '<p class="note">One machine: two RTX PRO 6000 Blackwell Max-Q GPUs at their 300 W power cap, one model '
            '(GLM-5.3-Flash, EXL3 K3.25 and K4 experts), thinking on. Other GPUs, quantizations or settings can change the picture.</p>')


def how_sure():
    return ('<h2 id="how-sure">How sure are we</h2><div class="sure"><div><h3>Solid</h3><ul>'
            '<li>The precision difference is paired against three vLLM runs from two launches, and survives a leave-one-window-out '
            'check and a multiple-comparison correction (independent audit).</li>'
            '<li>CuteAFD is bit-deterministic: every repeat was byte-identical.</li>'
            '<li>Speed did not drift: repeats hours later were within ±2% at the median on both engines.</li>'
            '<li>Both engines ran every request with 0 errors.</li></ul></div><div><h3>Thin</h3><ul>'
            '<li>Long output: two seeds per prompt, four prompts per content type.</li>'
            '<li>Long-document NLL (32K-128K): six documents.</li>'
            '<li>The BF16 reference stops at 14.4K tokens; beyond it the engines are compared only with each other.</li>'
            '<li>Precision was scored in prefill shape; the decode path that generates tokens was not scored.</li>'
            '<li>Single speed cells vary by up to ±13% between runs.</li></ul></div></div>')


def glossary():
    terms = [("KL (Kullback-Leibler divergence)", "How far an engine's next-token probabilities are from the original BF16 model. "
              "0 means identical; lower is better. Measured in nats. tpurtell's fidelity set treats a paired change below 0.005 "
              "as within its bar."),
             ("Top-1", "How often the engine's most likely next token is the reference's most likely one."),
             ("History", "The number of tokens before a scored position: what the model had read when it made that "
              "prediction. Each headline KL states the range (minimum, median, maximum) of its scored positions."),
             ("Tail (p99, p99.9)", "The per-position KL that 1% (0.1%) of scored positions exceed. A mean can hide a few "
              "positions where the distributions differ a lot; the tail shows them."),
             ("NLL", "Negative log-likelihood of the actual text: lower means the engine found the text less surprising."),
             ("TTFT", "Time to first token: from sending a request to the first generated token; mostly prompt processing."),
             ("Prefill", "Processing the prompt before generation starts. Decode: generating tokens one step at a time."),
             ("Stream", "One request in flight. Aggregate: all completion tokens of a batch divided by its wall time."),
             ("W8A8 / W8A16", "FP8 weights with FP8 or 16-bit activations in CuteAFD's prefill matrix multiplies.")]
    return ('<h2 id="terms">Terms</h2><dl class="gl">' + "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in terms)
            + "</dl>")


def sign_note():
    return '<p class="sign">Sign convention: a positive KL difference means CuteAFD is further from the BF16 model than the vLLM fork.</p>'


# ------------------------------------------------------------------ K4 run (results/2026-10-27-k4-vllm-cuteafd)
# Numbers from the run's published files via tools/build_readme.py (B.k4_*). Its precision numbers are top-20 measures;
# every K4 table says so, and none shares a column with the K3.25 run's full-vocabulary KL.

R4 = f"results/{B.K4}"
ARM4 = {"Vr1": "vLLM launch 1", "Vr1b": "vLLM launch 1, repeat", "Vr2": "vLLM launch 2", "Cr1": "CuteAFD"}
K4_ATTR = ('<p class="sign">K4 is GLM-5.3-Flash-tr3-4bpw by <b>Local Inference Lab, Inc.</b> '
           '(<a href="https://huggingface.co/brandonmusic/GLM-5.3-Flash-tr3-4bpw">huggingface.co/brandonmusic/GLM-5.3-Flash-tr3-4bpw</a>; '
           'project home <a href="https://local-inference-lab.ai/">local-inference-lab.ai</a>), evaluated at revision '
           '<code>a5fee929</code>. Attribution does not imply endorsement, sponsorship, certification or verification of this '
           f'evaluation or its results by the author or the licensor (<a href="{REPO_URL}/blob/main/NOTICE.md">NOTICE.md</a>).</p>')
K4_TOP20 = ('<p class="note"><b>Top-20 measures.</b> K4 was scored from the engines\' own 20 most likely ids plus the actual '
            'token (KL20 on P-A, KL_pb20 on P-B, KL20n between engines on Q2), identically on both arms. They are not '
            'full-vocabulary KL: on P-A KL20 reads about 0.8 of it, on P-B generated rows KL_pb20 keeps about 98-99% of the '
            'published coarse KL, and every K3.25 difference kept its sign and significance under the truncation. K4 numbers '
            'are compared with K3.25 only under the same top-20 definition.</p>')


def k4_cards(K):
    s = B.k4_facts_text(K); T = K["T"]
    share = -s["f1_816"]["diff"] / s["d_816"]["B_minus_A"]
    m25 = B.load(D / "q/pb/pb-vs-vllm-mean3.json")
    share25 = (m25["8-16K|kl|C1"][0] - m25["8-16K|kl|F1c"][0]) / m25["8-16K|kl|C1"][0]
    b816 = pb_band(T, "8-16K")["context"]
    items = [
        ("K4 against K3.25", f"{s['pa25_v']:.4f} → {s['pa_v']:.4f}",
         "A quantization comparison: K4's 4-bit experts sit roughly half as far from the BF16 teacher as K3.25's, on both "
         "engines.", f"P-A teacher KL20 (top-20, same definition on both checkpoints), vLLM; CuteAFD {s['pa25_c']:.4f} → "
         f"{s['pa_c']:.4f}. Every position of 25 windows: {hist_short(T['pa']['scored']['context'])}."),
        ("Precision on K4", f"{dkl(s['d_816']['B_minus_A'])}",
         "vLLM stays closer to BF16. The difference sits in long code reading (8-16K), as on K3.25, and reads larger "
         f"({dkl(s['d25_816']['diff'])} on K3.25; intervals overlap).",
         f"P-B KL_pb20 at 8-16K, CuteAFD − vLLM [{s['d_816']['ci95'][0]:+.4f}, {s['d_816']['ci95'][1]:+.4f}], "
         f"{hist_short(b816)}. All generated rows {dkl(s['d_pb']['B_minus_A'])}; P-A {dkl(s['d_pa']['B_minus_A'])}."),
        ("Speed on K4", f"{s['dec1'][0]:.2f}-{s['dec1'][1]:.2f}x",
         f"CuteAFD decodes faster in {s['dec_read'][0]} of {s['dec_read'][3]} cells and level in the other "
         f"{s['dec_read'][1] + s['dec_read'][2]}. Its first token comes sooner at one stream from 8K up; vLLM's comes sooner "
         "at 1K and at 32K with four streams.",
         f"Single-stream decode, CuteAFD ÷ vLLM; at four streams {s['dec4'][0]:.2f}-{s['dec4'][1]:.2f}x. 1 and 4 streams "
         "at 1K-32K, 1 stream at 128K."),
        ("W8A16 prefill on K4", f"{100 * share:.0f}%",
         f"Of the 8-16K difference, W8A16 prefill moves about {100 * share:.0f}% on K4 (about {100 * share25:.0f}% on "
         "K3.25), for 3-4% longer time to first token.",
         f"Follow-up F1-K4, outside the frozen protocol: {dkl(s['f1_816']['diff'])} [{s['f1_816']['ci95'][0]:+.4f}, "
         f"{s['f1_816']['ci95'][1]:+.4f}]. On P-A, CuteAFD with W8A16 is not resolved from vLLM."),
        ("Long output on K4", "pending", "Block L was still running when these pages were built.", "Filled in once both "
         "engines' stages have finished and the frozen analysis has run.") if not B.k4_l_summaries() else
        ("Long output on K4", "see Long output", "Both engines' Block L stages, analysed by the frozen K3.25 analyser.",
         "Descriptive: 2 seeds per prompt, 4 prompts per content type.")]
    return '<div class="cards">' + "".join(
        f'<div class="card"><div class="k">{html.escape(k)}</div><div class="big">{html.escape(big)}</div><p>{html.escape(txt)}</p>'
        f'<div class="ev">{html.escape(ev)}</div></div>' for k, big, txt, ev in items) + "</div>"


def k4_index(K):
    if not K: return ""
    return ('<h2 id="k4">Second checkpoint: K4 (2026-10-27)</h2>'
            '<p class="plain">The same two engines, machine, panels and prompts, on brandonmusic\'s GLM-5.3-Flash-tr3-4bpw '
            '("K4", 4-bit EXL3 experts), under a second protocol frozen before its first request. <b>K4 against K3.25 is a '
            'quantization comparison; the engine comparison on K4 repeats the K3.25 pattern:</b> vLLM closer to BF16, '
            'CuteAFD faster.</p>' + k4_cards(K) + K4_ATTR +
            f'<p class="sign">Detail: <a href="precision.html#k4">precision</a>, <a href="throughput.html#k4">throughput</a>, '
            f'<a href="observations.html#k4">observations</a>, <a href="method.html#k4">method</a>; receipts in '
            f'<a href="{REPO_URL}/tree/main/{R4}"><code>{R4}</code></a>.</p>')


def k4_tails_table(P):
    rows = []
    for a, s in P["arms"].items():
        rows.append([ARM4[a], f"{s['kl_mean']:.4f}", f"{s['kl_p50']:.4f}", f"{s['kl_p90']:.3f}", f"{s['kl_p99']:.3f}",
                     f"{s['kl_p99.9']:.2f}", f"{s['kl_max']:.2f}", f"{100 * s['top1']:.2f}%",
                     f"{100 * s['confident_top1']:.2f}%" if "confident_top1" in s else "n/a"])
    return htable(["Run", "Mean", "p50", "p90", "p99", "p99.9", "Max", "Top-1", "Confident top-1"], rows)


def k4_precision(K):
    if not K: return ""
    T = K["T"]; rows4 = R4D / "q" / "rows"
    return ('<h2 id="k4">K4 (2026-10-27): top-20 measures</h2>' + K4_TOP20 +
            '<p class="plain">On K4, CuteAFD is further from BF16 than the vLLM fork on both panels, most in long code '
            'reading (8-16K); on human-written text at 32K-128K no NLL difference is resolved. Against K3.25 under the same '
            'definition, K4 sits roughly half as far from the teacher on both engines.</p>' + fig_engine_k4(K) +
            '<p class="sign">vLLM = per-row mean of two launches. Reading: "differs" needs the 95% interval to exclude 0 and '
            'the difference to exceed vLLM\'s launch-to-launch difference on the same rows. History: tokens before each '
            'scored position (min / median / max).</p>' + md(B.k4_precision_table(K)) +
            md(B.k4_q2_note(K), R4) +
            '<h3 id="k4-vs-k325">K4 against K3.25, same top-20 definition</h3>'
            '<p class="sign">The K3.25 values are its full-vocabulary captures truncated to each engine\'s own top 20 '
            '(computed before the K4 freeze); same panels and rows, so the same scored history as above. CuteAFD ran K3.25\'s '
            'Core-FP8 checkpoint (official FP8 projections) and converts K4\'s BF16 projections at load.</p>' +
            md(B.k4_quant_table(K)) +
            '<h3 id="k4-settings">CuteAFD settings on K4 (follow-ups outside the frozen protocol)</h3>' + fig_settings_k4(K) + fig_map_k4(K) +
            '<h3 id="k4-f1">Follow-up F1-K4: W8A16 prefill on K4 (outside the frozen protocol)</h3>' + md(B.k4_f1_tables(K)) +
            '<h3 id="k4-f1b">Follow-ups F1-K4b and K4c: CuteAFD\'s FP8 switches on K4 (outside the frozen protocol)</h3>' +
            md(strip_title(read(f"{R4}/f1k4/RESULTS-F1K4b.md")), R4) +
            f'<h3 id="k4-tails">K4 tails (top-20 measures)</h3>' +
            fig_tails("k4", "pa", T, rows4, "tails-k4-pa", "KL20", k4_tails_table(T["pa"])) +
            f'<p class="sign">P-A, every position of 25 windows ({hist_short(T["pa"]["scored"]["context"])}):</p>' + k4_tails_table(T["pa"]) +
            fig_tails("k4", "pb", T, rows4, "tails-k4-pb", "KL_pb20", k4_tails_table(T["pb"])) +
            f'<p class="sign">P-B, {T["pb"]["scored"]["selected_positions_total"]:,} generated positions '
            f'({hist_short(T["pb"]["scored"]["context"])}):</p>' + k4_tails_table(T["pb"]) +
            fig_q2_tails("k4", T, rows4, "tails-k4-q2", "KL20n") +
            f'<p class="sign">Computed by <code>tools/kl_tails.py --run k4</code> from '
            f'<a href="{REPO_URL}/tree/main/{R4}/q/rows"><code>q/rows/</code></a>; the curves count the same per-position files.</p>')


def k4_throughput(K):
    if not K: return ""
    s = B.k4_facts_text(K)
    return ('<h2 id="k4">K4 (2026-10-27)</h2><p class="plain">On K4, CuteAFD decodes faster than the vLLM fork in '
            f'{s["dec_read"][0]} of {s["dec_read"][3]} cells, at one and at four streams, and level in the other '
            f'{s["dec_read"][1] + s["dec_read"][2]} (8K and 128K prose, one stream). Its first token comes sooner at one stream from 8K up and at 8K with four '
            'streams; the vLLM fork\'s comes sooner at 1K and at 32K with four streams.</p>'
            '<p class="sign">Grid common to the protocol\'s arms (<a href="method.html#k4">Method</a>): 1 and 4 streams at '
            '1K-32K, 1 stream at 128K, 1,024 output tokens, thinking on. Ratios are CuteAFD ÷ vLLM per content cell; readings '
            'use the declared ±8% band.</p>' + k4_speed_figs(K) + md(B.k4_t_table(K)) + f'<p class="sign">{inline(B.k4_t_counts(K), R4)}</p>' +
            '<h3 id="k4-startup">Startup on K4 (descriptive)</h3>' +
            md(B.table(["Launch", "To /v1/models", "To ready", "Capacity at startup"], B.k4_startup_rows(K))))


K4_BAND = "±8% band: declared before the K4 run (both engines' drift repeats stayed inside it); readings per cell from t/t-compare.json"
K325_BAND = ("±10% band: the drift check's reading (single cells vary by up to about ±13% between runs; ratios within about ±10% "
             "are not differences)")


def k4_speed_figs(K):
    cells = k4_cells(K)
    return "".join(fig_speed("k4", m, cells, f"{m}-k4", (0.92, 1.08), K4_BAND) for m in ("dec", "agg", "ttft"))


def k4_long(K):
    if not K: return ""
    if not B.k4_l_summaries():
        return ('<h2 id="k4">K4 (2026-10-27): pending</h2><p class="plain">Block L on K4 (2 requests in flight; caps 8,192, '
                '32,768 and 130,048 tokens; one-at-a-time subset at the last cap) was still running when these pages were '
                'built. It appears here once both engines have finished and the frozen analysis has run on them.</p>')
    return '<h2 id="k4">K4 (2026-10-27)</h2>' + fig_long(B.k4_l_summaries(), "k4", "V", "C", "long-k4") + md(B.k4_l_text(), R4)


def k4_observations(K):
    if not K: return ""
    c2 = strip_title(read(f"{R4}/c2/README.md"))
    items = [
        "**CuteAFD needs one local setting to serve K4 on two RTX GPUs** (its planner's dry run and startup line): at its defaults the planner "
        "refuses K4 (pool 260,608 tokens, below its 1,048,576-token context floor); `MAX_CONTEXT_TOKENS=262144` gives a "
        "447,488-token pool beside the desktop's context on GPU 1.",
        "**CuteAFD converts K4's BF16 projections to FP8 at load** (declared difference, read in source before the freeze): attention, dense "
        "and shared projections in 128×128 blocks with pow2 scales, head and KDA projections per row. On K3.25 those "
        "projections came from the official FP8 checkpoint. The vLLM fork serves them in BF16.",
        "**W8A16 prefill moves less of the long-code difference on K4 than on K3.25** (follow-up F1-K4): about 21% of the "
        "8-16K difference, against about 59% on K3.25. **Follow-ups F1-K4b and K4c tested the other FP8 choices:** no single "
        "switch accounts for most of it (BF16 KDA projections about 39%, the amax scale rule about 25% not resolved, BF16 "
        "head about 3%); W8A16 prefill together with the amax scale rule moves about 68%, leaving +0.0030 at 8-16K and no "
        "resolved difference on P-A or Q2, at about 4% longer time to first token. BF16 KDA projections and head do not "
        "fit a serving launch on two RTX cards with K4.",
        "**Literal `<think>` text in a prompt** (smoke check S2 and Block T): the vLLM stack parses it as a special token, "
        "CuteAFD keeps it as text, so the 128K code prompts are longer on CuteAFD (as on K3.25).",
        "**Same seed, same prompt** (smoke, 3 prompts): CuteAFD returned identical text 3 of 3 times, the vLLM fork 1 of 3; "
        "the cause was not examined. Repeats in this run always use distinct seeds.",
        "**CuteAFD's scoring launch turns its prefix cache off** (`PREFIX_CACHE_ENTRIES=0`): the full prefill-logits buffer "
        "did not fit beside the desktop's context otherwise, and scoring probes never read the prefix cache, so no scored "
        "value changes."]
    return ('<h2 id="k4">K4 (2026-10-27)</h2>' + md("\n".join(f"- {x}" for x in items)) +
            f'<h3 id="k4-c2">{html.escape(read(f"{R4}/c2/README.md").splitlines()[0][2:])}</h3>' + md(c2, f"{R4}/c2"))


def k4_scored_table(K):
    T = K["T"]; pa, pb, q2 = T["pa"]["scored"], T["pb"]["scored"], T["q2"]["scored"]
    rows = [["<b>P-A</b> BF16 teacher panel (brandonmusic)", f"{pa['windows']}", hist(pa["tokens_per_window"]),
             f"all {num(pa['scored_positions_per_window']['median'])}", f"{pa['selected_positions_total']:,}", hist(pa["context"]),
             "KL20 (top-20 KL from the teacher); NLL; top-1"],
            ["<b>P-B</b> tpurtell's fidelity panel", f"{pb['windows']}", hist(pb["tokens_per_window"]),
             f"last 512; generated (primary) {hist(pb['selected_positions_per_window'])}",
             f"{pb['selected_positions_total']:,} generated", hist(pb["context"]), "KL_pb20 (top-20 truncation of his rule); NLL; top-1"],
            ["<b>Q2</b> long human-written text", f"{q2['windows']}", hist(q2["tokens_per_window"]),
             f"last {num(q2['scored_positions_per_window']['median'])}", f"{q2['selected_positions_total']:,}", hist(q2["context"]),
             "NLL; KL20n between runs as disagreement"]]
    return htable(["Panel", "Windows", "Tokens per window (min / median / max)", "Scored positions per window", "Total scored",
                   "History behind each scored token, tokens (min / median / max)", "Metric (top-20)"], rows)


def k4_method(K):
    if not K: return ""
    m = strip_title(read(f"{R4}/METHOD.md"))
    return ('<h2 id="k4">K4 (2026-10-27)</h2><p class="plain">The K4 measurement reused the K3.25 run\'s panels, prompts and '
            'drivers, scored Block Q with top-20 measures, ran two vLLM launches around the CuteAFD captures, and was frozen '
            'at 2026-10-27T17:58:09-07:00 before its first comparison request.</p>'
            '<h3 id="k4-what-was-scored">What was scored (K4)</h3>' + k4_scored_table(K) +
            f'<details class="more" id="k4-method"><summary>The K4 method in full</summary>{k4_method_md(m)}</details>')


def k4_method_md(m):
    """The K4 METHOD.md on the method page: its heading ids get a "k4-method-" prefix, so they cannot collide with the
    K3.25 protocol's headings on the same page (both have an "Arms" section); in-document links follow."""
    h = md(m, R4, 1)
    ids = set(re.findall(r'<h[1-6] id="([^"]+)"', h))
    h = re.sub(r'(<h[1-6] id=")([^"]+)"', r'\1k4-method-\2"', h)
    return re.sub(r'href="#([^"]+)"', lambda x: f'href="#k4-method-{x.group(1)}"' if x.group(1) in ids else x.group(0), h)


def k4_reproduce(K):
    if not K: return ""
    return ('<h2 id="k4">K4 launch files</h2>' + md(strip_title(read("repro/k4/README.md")), "repro/k4", 1) +
            '<pre><code>source repro/k4/vllm/env.sh   # then the v0.9.0 repository\'s start script\n'
            './run.sh --config glm53-flash-exl3-k4-2rtx.config          # CuteAFD v3.0.1, serving\n'
            './run.sh --config glm53-flash-exl3-k4-2rtx-score.config    # CuteAFD v3.0.1, Block Q scoring\n'
            'python3 tools/kl_tails.py --run k4 --check                  # K4 tails from q/rows/</code></pre>')


# ------------------------------------------------------------------ pages

LINKS = [("precision.html", "Precision", "how close each engine stays to the BF16 model, by context length, with the W8A16 option"),
         ("throughput.html", "Throughput", "speed by input length, content and number of streams"),
         ("long-output.html", "Long output", "replies up to 128K tokens, checked against tests and schemas"),
         ("observations.html", "Observations", "behaviour differences between the stacks, with evidence, and the confounds"),
         ("method.html", "Method", "setup, the frozen protocol, follow-ups and limits"),
         ("audit.html", "Audit", "the independent review of the measurements"),
         ("ledger.html", "Ledger", "what was run and established, and when"),
         ("reproduce.html", "Reproduce", "how to repeat every step")]


def main():
    DOCS.mkdir(exist_ok=True)
    for p in DOCS.glob("*.html"): p.unlink()
    R = sections(readme())
    F = facts(); d = F["d"]; rows = F["len"]
    K = B.k4_data() if B.k4_ok() else None
    run = f'<a href="{REPO_URL}/tree/main/{RD}">receipts</a>'
    lo, hi = F["dec_range"]

    S = startup()
    rows3 = D / "q" / "rows"
    cells3 = k325_cells()
    fig_su = chart_startup(S) or '<p class="note">Startup timeline: pending.</p>'
    head = '<h2 id="at-a-glance">At a glance</h2>' + fig_headline_k325(F) + (fig_headline_k4(K) if K else "")

    answer = ("On two RTX PRO 6000s, CuteAFD is the faster engine and tpurtell's vLLM fork is the slightly more precise one; "
              f"one CuteAFD setting (W8A16 prefill) halves the precision difference for about {pp(F['f1c_ttft'])} slower "
              "first token." + (" On a second checkpoint, K4, both engines sit roughly half as far from BF16, and the engine "
                                "pattern holds." if K else ""))
    page("index.html", "CuteAFD and tpurtell's vLLM fork on two RTX PRO 6000s", html.escape(answer),
         '<p class="lede">Both engines are tpurtell\'s. Same model (GLM-5.3-Flash with his 3.25-bit EXL3 experts), same '
         f'machine, measured under a frozen protocol with an independent audit. Every number comes from the {run} in the '
         'repository.</p>' + head + choosing(F, K) + '<h2 id="k325">First checkpoint: K3.25 (2026-10-26)</h2>' + cards(F) +
         k4_index(K) + how_sure() + glossary() +
         '<h2 id="detail">In detail</h2><ul class="links">' +
         "".join(f'<li><a href="{p}">{t}</a>: {html.escape(s)}</li>' for p, t, s in LINKS) + "</ul>", lede_cls="answer")

    # precision
    bk = [("all", "All"), ("0-2K", "0-2K"), ("2-8K", "2-8K"), ("8-16K", "8-16K, long code")]
    T = F["T"]; ctx_of = lambda b: T["pb"]["scored"]["context"] if b == "all" else pb_band(T, b)["context"]
    key = [[lab, hist(ctx_of(b)), kl(F["kl_v"][b]), kl(F["kl_c"][b]), f'<b>{dkl(d[(b, "kl", "C1")][0])}</b> {civ(d[(b, "kl", "C1")])}'
            f'<br>W8A16: {dkl(d[(b, "kl", "F1c")][0])} {civ(d[(b, "kl", "F1c")])}'] for b, lab in bk]
    pa_s, pb_s = T["pa"]["arms"], T["pb"]["arms"]; pab = T["pa"]["by_position"]
    pbv = [pb_s[a]["kl_p99"] for a in ("V1", "V1r", "V2")]
    tails_sec = (
        '<h2 id="tails">Tails and position</h2>'
        f'<p class="plain">Most positions sit far below the mean: the median position\'s KL is {pa_s["V1"]["kl_p50"]:.4f} '
        f'(vLLM fork) and {pa_s["C1"]["kl_p50"]:.4f} (CuteAFD) on P-A, against means of {pa_s["V1"]["kl_mean"]:.4f} and {pa_s["C1"]["kl_mean"]:.4f}: '
        f'the highest-KL 5% of positions carry {100*pa_s["V1"]["kl_share_top5pct"]:.0f}% of the vLLM fork\'s mean and {100*pa_s["C1"]["kl_share_top5pct"]:.0f}% of CuteAFD\'s '
        f'(top 10%: {100*pa_s["V1"]["kl_share_top10pct"]:.0f}% and {100*pa_s["C1"]["kl_share_top10pct"]:.0f}%). '
        f'p99 on P-A: vLLM fork {pa_s["V1"]["kl_p99"]:.3f}, CuteAFD {pa_s["C1"]["kl_p99"]:.3f}; on P-B generated positions: '
        f'vLLM fork {min(pbv):.3f}-{max(pbv):.3f} over its three runs, CuteAFD {pb_s["C1"]["kl_p99"]:.3f}. On P-A, positions with '
        f'a short history carry more KL on both engines (history {num(pab[0]["context"]["min"])}-{num(pab[0]["context"]["max"])} '
        f'tokens: {vmean(pab[0]["arms"], "kl_mean"):.3f} and {pab[0]["arms"]["C1"]["kl_mean"]:.3f}; '
        f'{num(pab[-1]["context"]["min"])}-{num(pab[-1]["context"]["max"])} tokens: {vmean(pab[-1]["arms"], "kl_mean"):.3f} and '
        f'{pab[-1]["arms"]["C1"]["kl_mean"]:.3f}), so a panel\'s mean depends on which positions it scores.</p>'
        + '<h3 id="tails-pa">P-A, all 2,047 positions of 25 windows (full-vocabulary KL)</h3>'
        + fig_tails("k325", "pa", T, rows3, "tails-k325-pa", "KL", tails_table(T, "pa") + band_table(T, "pa")) + tails_table(T, "pa")
        + f'<h3 id="tails-pb">P-B, {T["pb"]["scored"]["selected_positions_total"]:,} generated positions (coarse KL)</h3>'
        + fig_tails("k325", "pb", T, rows3, "tails-k325-pb", "coarse KL", tails_table(T, "pb") + band_table(T, "pb"))
        + tails_table(T, "pb") + details("P-B by length bucket: mean, p99, p99.9 and top-1 per arm", band_table(T, "pb"))
        + '<h3 id="tails-q2">Q2, the last 4,096 positions of 18 long windows (disagreement between engines)</h3>'
        + fig_q2_tails("k325", T, rows3, "tails-k325-q2", "KL")
        + '<p class="sign">Per-position KL in nats; p99 is the value 1% of positions exceed. Confident top-1: top-1 over '
        'positions where the reference\'s top probability is at least 0.5. P-A and P-B KL are different metrics (full '
        'vocabulary vs top-1,024 plus tail) on different texts: compare engines within a panel, not panels with each other. '
        f'Computed by <a href="{REPO_URL}/blob/main/tools/kl_tails.py"><code>tools/kl_tails.py</code></a> from the per-position '
        f'files in <a href="{REPO_URL}/tree/main/{RD}/q/rows"><code>q/rows/</code></a> (P-A, P-B, Q2) into <a href="{REPO_URL}/tree/main/{RD}/q/tails"><code>q/tails/</code></a>.</p>')
    top = [[lab, f'{100 * d[(b, "top1", "C1")][0]:+.2f} pts<br>{civ(d[(b, "top1", "C1")], 2, 100)}'] for b, lab in bk]
    rq = strip_title(read(f"{RD}/q/RESULTS-Q.md")); f1 = strip_title(read(f"{RD}/f1/RESULTS-F1.md"))
    page("precision.html", "Precision", "How close each engine's next-token probabilities stay to the original BF16 model.",
         f'<p class="plain">Both engines are close to BF16; CuteAFD is slightly further, by {dkl(d[("all", "kl", "C1")][0])} KL '
         f'overall on the fidelity panel\'s generated positions ({hist_short(ctx_of("all"))}) and '
         f'{dkl(d[("8-16K", "kl", "C1")][0])} at 8-16K ({hist_short(ctx_of("8-16K"))}), where the panel is long code reading. '
         'Below 8K the intervals include zero. W8A16 prefill removes about half of the overall difference. On human-written text at '
         '32K-128K the engines\' NLL differs by no more than about ±0.005 nat (six documents, no BF16 reference there).</p>' +
         fig_engine_k325(F) + '<h3 id="settings-k325-h">CuteAFD settings on K3.25 (follow-up F1, outside the frozen protocol)</h3>' +
         fig_settings_k325(F) + fig_map_k325(F) + f'<p class="sign">KL from BF16 on generated rows; vLLM = mean of {F["n_vruns"]} runs. Difference = CuteAFD '
         'minus vLLM: positive means CuteAFD is further from BF16; the second line is CuteAFD with W8A16 prefill. In grey: 95% '
         'interval. History: tokens before each scored position (min / median / max).</p>' +
         htable(["Context", "History, tokens", "vLLM", "CuteAFD", "Difference"], key) +
         details("Top-1 agreement, CuteAFD minus vLLM fork", htable(["Context", "Difference"], top)) +
         f'<p class="sign">The 2K full-vocabulary panel (P-A) gives {dkl(F["pa"]["B_minus_A"])} '
         f'<span class="ci">[{F["pa"]["ci95"][0]:+.4f}, {F["pa"]["ci95"][1]:+.4f}]</span>, over every position of 25 '
         f'2,048-token windows ({hist_short(T["pa"]["scored"]["context"])}). Intervals: 95%, paired bootstrap over windows.</p>' +
         tails_sec + k4_precision(K) +
         f'<details class="more" id="block-q"><summary>Block Q in full: panels P-A, P-B and Q2, controls, the audit\'s items</summary>{md(rq, f"{RD}/q", 1)}</details>' +
         f'<details class="more" id="follow-up-f1"><summary>Follow-up F1 in full: every CuteAFD FP8 switch, precision and speed</summary>{md(f1, f"{RD}/f1", 1)}</details>' +
         details("All bucket tables", md(B.q_buckets())))

    # throughput
    lrows = []
    for L, r in rows.items():
        tv = max(a for a, _ in r["tt1"]); tc = max(b for _, b in r["tt1"])
        lrows.append([f"{L // 1024}K", f"{pct(r['dec'][0])} to {pct(r['dec'][1])}",
                      f"{r['agg'][0]:.2f}x<br><span class=\"ci\">({r['agg'][1]:.2f}-{r['agg'][2]:.2f})</span>",
                      f"{tv:.2f} s vs {tc:.2f} s"])
    cav = strip_title(read(f"{RD}/t/CAVEATS.md")); dr = strip_title(read(f"{RD}/drift/RESULTS-DRIFT.md"))
    f2 = strip_title(read(f"{RD}/f2/RESULTS-F2.md")); ts = strip_title(read(f"{RD}/t/T-SUMMARY.md"))
    page("throughput.html", "Throughput", "Speed with 1K to 128K-token prompts, 1 to 16 requests at once, thinking on, 1,024 "
         "tokens generated per request.",
         f'<p class="plain">CuteAFD generates {span(lo, hi)} faster for one request at a time, and its faster prefill '
         'gives it the lead on long prompts. The vLLM fork starts short prompts sooner and handles many short prompts at once '
         'a little better. Differences within about ±10% in a single cell are run-to-run noise.</p>' +
         fig_speed("k325", "dec", cells3, "dec-k325", (0.9, 1.1), K325_BAND) + fig_speed("k325", "agg", cells3, "agg-k325", (0.9, 1.1), K325_BAND) +
         fig_speed("k325", "ttft", cells3, "ttft-k325", (0.9, 1.1), K325_BAND) +
         '<p class="sign">Decode: CuteAFD vs vLLM, one request at a time. Throughput: CuteAFD ÷ vLLM, median over '
         'content types and 1-16 streams (range). First token: one request, vLLM vs CuteAFD.</p>' +
         htable(["Input", "Decode", "Throughput", "First token"], lrows) +
         f'<details class="more" id="caveats"><summary>Caveats: inputs, labels, draft policies, noise</summary>{md(cav, f"{RD}/t", 1)}</details>' +
         details("The headline cells", md(B.t_table()) + md(B.t_counts())) +
         f'<details class="more" id="drift"><summary>Drift check: the same cells hours later</summary>{md(dr, f"{RD}/drift", 1)}</details>' +
         f'<details class="more" id="follow-up-f2"><summary>Follow-up F2: the vLLM fork\'s prefix-cache reuse</summary>{md(f2, f"{RD}/f2", 1)}</details>' +
         f'<details class="more" id="full-grid"><summary>Full grid: every cell, decode, aggregate, first token, prefill</summary>{md(ts, f"{RD}/t", 1)}</details>'
         + k4_throughput(K))

    # long output
    L = F["L"]
    def lo_card(c, task, plain):
        v, u = L[("V1", "L3", c)], L[("C1", "L3", c)]
        row = lambda name, s: (f'<div class="row"><span>{name}</span><span>{B.l_check(s)} '
                               f'<span class="ci">· median {s["completion_tokens_median"] / 1000:.0f}K tokens</span></span></div>')
        return (f'<div class="card"><h3>{c if c != "json" else "JSON"}</h3><div class="ev">{task}</div>'
                f'{row("vLLM fork", v)}{row("CuteAFD", u)}<p>{plain}</p></div>')
    cards_l = "".join([
        lo_card("code", "4 multi-file Python projects with hidden tests",
                f"Same pass rate; {L[('V1', 'L3', 'code')]['tests_passed_total']} vs {L[('C1', 'L3', 'code')]['tests_passed_total']} "
                "of 218 tests. CuteAFD's replies are shorter."),
        lo_card("reasoning", "MATH-500 level-5 problems", "Both solve all of them; the task does not separate the engines."),
        lo_card("prose", "10,000-12,000-word essays", "Both finish every essay; CuteAFD writes slightly more words per required word."),
        lo_card("json", "product catalogues of 50-1,030 records", "vLLM's two misses are the 1,030-record task at the cap; "
                "CuteAFD's four are field-pattern slips in otherwise complete outputs. Two seeds per prompt.")])
    page("long-output.html", "Long output", "Replies of up to 128K tokens, eight requests at a time, each checked against tests, "
         "a schema or the reference answer.",
         '<p class="plain">Both engines ran all 100 long-output requests with 0 errors. At the 128K cap they pass the same share '
         'of code and math; they differ in JSON validity on a small sample, and CuteAFD\'s replies run about 15-25% shorter, '
         'a difference not separated from sampling.</p>' +
         fig_long(L, "k325", "V1", "C1", "long-k325") + f'<div class="outcomes">{cards_l}</div>' +
         '<p class="sign">At the 128K cap; 8 replies per content type (4 prompts, 2 seeds).</p>' +
         details("Every stage, 8K, 32K, 128K and one at a time", md(B.L_NOTE) + md(B.l_table(detail=True))) +
         k4_long(K))

    page("observations.html", "Observations and confounds", "Behaviour differences between the two stacks, each with how it "
         "is known, and what else differs and how each block handles it.",
         '<p class="plain">The differences a user notices first: CuteAFD honours "thinking off" and the vLLM fork does not; '
         'CuteAFD reuses repeated prompts from its cache and the vLLM fork only in whole 4,352-token blocks; '
         + E(startup_sentence(short=True)) + '; the vLLM fork\'s '
         'long prefill is not bit-reproducible run to run, CuteAFD\'s is.</p>' +
         '<h2 id="observations-in-detail">Observations in detail</h2>' + md(R.get("Observations in detail", "")) + fig_su +
         f'<details class="more" id="confounds"><summary>Confounds: what else differs, and how it is handled</summary>{md(R.get("Confounds", ""))}</details>'
         + k4_observations(K))

    proto = strip_title(read("protocol/PROTOCOL.md")); fol = strip_title(read("protocol/FOLLOWUPS.md"))
    page("method.html", "Method", "How the comparison was set up and measured.",
         '<p class="plain">Each engine ran as its author ships it, with a short list of local changes, on one machine. Precision '
         'was scored teacher-forced against a BF16 reference; speed and long output with one client, unique prompts and a '
         'distinct seed per request. The protocol was frozen before the speed and long-output runs; three follow-ups and a drift '
         'check were declared later and are labelled as such.</p>' + what_scored(F["T"]) +
         '<h2 id="limits">Limits</h2>' + summary_block("Limits") +
         '<h2 id="status">Status</h2>' + md(B.status_lines()) +
         f'<details class="more" id="setup"><summary>Setup: hardware, engines, checkpoints, settings</summary>{md(R.get("Setup", ""))}</details>' +
         f'<details class="more" id="protocol"><summary>The protocol, v2 with amendments A1-A2</summary>'
         f'{md(strip_title(read("protocol/README.md")).split(chr(10) + "## ")[0], "protocol")}{md(proto, "protocol", 2)}</details>' +
         f'<details class="more" id="follow-ups"><summary>Follow-ups F1-F3 and the drift check</summary>{md(fol, "protocol", 1)}</details>' +
         f'<details class="more" id="other-runs"><summary>Other runs: checks and an exploratory test</summary>{md(R.get("Other runs", ""))}</details>'
         + k4_method(K))

    au = strip_title(read(f"{RD}/AUDIT-2026-10-27.md"))
    page("audit.html", "Independent audit (2026-10-27)", "A read-only, CPU-only review of the precision and speed blocks and "
         "of vLLM's long-output block, made before CuteAFD's long-output block and the later follow-ups ran.",
         '<p class="plain">The audit found the instruments sound and the precision difference robust. It traced the vLLM '
         'fork\'s run-to-run variation to multi-chunk prefill, which led to pairing CuteAFD against several vLLM runs; showed '
         'that the 8-16K bucket is long code reading, so length and content are not separated; and confirmed the speed '
         'explanation (prefill-first scheduling).</p>' + md(au, RD, 1))

    page("ledger.html", "Ledger", "What was run and established, and when (times UTC−7).", md(R.get("Ledger", "")))

    page("reproduce.html", "Reproduce", "From the frozen protocol to the published summaries, step by step.",
         md(strip_title(read("repro/REPRODUCE.md")), "repro", 1) + k4_reproduce(K) + '<h2 id="verify">Verify and rebuild</h2>' + md(R.get("Reproduce", "")))
    print(f"wrote {len(PAGES)} pages to docs/")


if __name__ == "__main__":
    main()
