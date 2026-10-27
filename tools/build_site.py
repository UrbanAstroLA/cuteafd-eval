#!/usr/bin/env python3
"""Build the results site (GitHub Pages, served from main /docs) from the repository's own files.

    python3 tools/build_site.py

Reads README.md (built by tools/build_readme.py), the run's SUMMARY.md, result markdown and JSON, the protocol, the audit
and repro/REPRODUCE.md, and writes static HTML pages to docs/. No scripts, no external stylesheets, fonts or images:
plain HTML with one inline stylesheet, light and dark (prefers-color-scheme), readable at phone width.
Links between pages are relative; links to files in the repository point at REPO_URL, the one place the repository's
address is assumed. Standard library only (Python 3.10+).
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


# ------------------------------------------------------------------ charts (inline SVG, no scripts; colours from CSS variables)
# Engine colour follows the engine: vLLM fork = slot 1 blue, CuteAFD = slot 2 orange, CuteAFD variants hollow orange.
# Text always uses text colours; marks carry the series colour. Hover detail is a native <title> on each mark group.
# Every chart has a table twin (figure(..., table=...)).

E = html.escape
def svg(W, H, label): return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{E(label)}">'
def tx(x, y, s, cls="", anchor="start"): return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{E(str(s))}</text>'
def tip(title, inner): return f"<g><title>{E(title)}</title>{inner}</g>"
def hbar(x0, x1, y, h, cls, r=4):
    """Horizontal bar from baseline x0 to data end x1: square at the baseline, rounded at the data end."""
    if abs(x1 - x0) < 0.5: return ""
    r = min(r, abs(x1 - x0), h / 2); s = 1 if x1 > x0 else -1
    xe = x1 - s * r
    sweep = 1 if s > 0 else 0
    return (f'<path class="{cls}" d="M{x0:.1f},{y:.1f} H{xe:.1f} A{r},{r} 0 0 {sweep} {x1:.1f},{y + r:.1f} V{y + h - r:.1f} '
            f'A{r},{r} 0 0 {sweep} {xe:.1f},{y + h:.1f} H{x0:.1f} Z"/>')
def key(x, y, cls, label, hollow=False):
    dot = f'<circle class="{"c2o" if hollow else cls}" cx="{x + 4:.1f}" cy="{y - 4:.1f}" r="4"/>'
    return dot + tx(x + 12, y, label)


def hero_rows(F, S):
    """'Where each engine leads': (label, side, ratio, value text, resolved, tooltip). side 'v' = vLLM leads, 'c' = CuteAFD."""
    import statistics as st
    d, rows = F["d"], F["len"]
    out = []
    k = d[("all", "kl", "C1")]
    out.append(("Precision (KL from BF16)", "v" if k[1] > 0 else "c", F["kl_c"]["all"] / F["kl_v"]["all"],
                f"{dkl(k[0])} KL", k[1] > 0 or k[2] < 0,
                f"CuteAFD {kl(F['kl_c']['all'])} vs vLLM fork {kl(F['kl_v']['all'])} (mean of {F['n_vruns']} runs); "
                f"difference {dkl(k[0])} [{k[1]:+.4f}, {k[2]:+.4f}]"))
    dec = [x for r in rows.values() for x in r["dec_all"]]
    out.append(("Single-stream decode", "c", st.median(dec), f"{min(dec):.2f}-{max(dec):.2f}x", min(dec) > 1,
                f"CuteAFD ÷ vLLM fork, one request at a time, {len(dec)} cells; median {st.median(dec):.2f}x"))
    ag = [x for L in (32768, 131072) for x in rows[L]["agg_all"]]
    out.append(("Long-prompt throughput (32K-128K)", "c", st.median(ag), f"{min(ag):.2f}-{max(ag):.2f}x", min(ag) > 1,
                f"CuteAFD ÷ vLLM fork, tokens per second end to end, {len(ag)} cells; median {st.median(ag):.2f}x"))
    tv, tc = st.median(a for a, _ in rows[1024]["tt1"]), st.median(b for _, b in rows[1024]["tt1"])
    out.append(("First token, 1K prompt", "v" if tv < tc else "c", max(tv, tc) / min(tv, tc), f"{tv:.2f} vs {tc:.2f} s", True,
                f"Time to first token at one request: vLLM fork {tv:.2f} s, CuteAFD {tc:.2f} s"))
    cv, cc = F["cached"]
    if cv and cc:
        out.append(("Repeated 8K prompt", "c" if cc < cv else "v", max(cv, cc) / min(cv, cc), f"{cc:.3f} vs {cv:.2f} s", True,
                    f"Time to first token for a repeated prompt: CuteAFD {cc:.3f} s (restored from its cache), vLLM fork {cv:.2f} s"))
    if S:
        vl = [r for r in S["runs"] if "cuteafd" not in r["label"].lower()]
        cu = [r for r in S["runs"] if "cuteafd" in r["label"].lower()]
        if vl and cu:
            v, c = vl[-1]["ready_s"], cu[0]["ready_s"]
            out.append(("Startup to ready", "c" if c < v else "v", max(v, c) / min(v, c), f"{c} vs {v} s", True,
                        f"CuteAFD {c} s; vLLM fork {v} s ({vl[-1]['label']}); {vl[0]['ready_s']} s without persisted caches"))
    else:
        out.append(("Startup to ready", "-", 1, "pending", False, "pending"))
    L = F["L"]
    vc, cc_ = L[("V1", "L3", "code")], L[("C1", "L3", "code")]
    vm, cm = L[("V1", "L3", "reasoning")], L[("C1", "L3", "reasoning")]
    out.append(("Long-output checks (code, math)", "-", 1,
                f"code {vc['all_pass']}/{vc['n']} vs {cc_['all_pass']}/{cc_['n']}, math {vm['correct']}/{vm['n']} vs {cm['correct']}/{cm['n']}",
                False, f"At the 128K cap: code all tests pass, vLLM fork {vc['all_pass']}/{vc['n']} ({vc['tests_passed_total']} tests), "
                f"CuteAFD {cc_['all_pass']}/{cc_['n']} ({cc_['tests_passed_total']} tests); math {vm['correct']}/{vm['n']} vs {cm['correct']}/{cm['n']}"))
    return out


def chart_hero(F, S):
    import math
    rows = hero_rows(F, S)
    W, cx, half, rh, bh = 340, 170, 150, 42, 12
    H = 40 + len(rows) * rh + 28
    o = [svg(W, H, "Where each engine leads"),
         key(cx - 150, 14, "c1", "vLLM fork leads"), f'<circle class="c2" cx="{cx + 66:.1f}" cy="10" r="4"/>',
         tx(cx + 74, 14, "CuteAFD leads"),
         ]
    y = 30
    for lab, side, r, val, ok, title in rows:
        o.append(tx(cx, y + 9, lab, "lab", "middle"))
        yb = y + 15
        o.append(f'<line class="axis" x1="{cx}" x2="{cx}" y1="{yb - 3}" y2="{yb + bh + 3}"/>')
        if side == "-" or not ok:
            w = 44
            o.append(tip(title, f'<rect class="lvl" x="{cx - w / 2:.1f}" y="{yb:.1f}" width="{w}" height="{bh}" rx="6"/>'
                         + tx(cx, yb + bh - 2, "level" if val != "pending" else "pending", "", "middle")))
            o.append(tx(cx, yb + bh + 15, val, "", "middle") if val != "pending" else "")
        else:
            frac = min(math.log(r) / math.log(2), 1.0)
            ln = max(frac * half, 3)
            x1 = cx - ln if side == "v" else cx + ln
            mark = hbar(cx, x1, yb, bh, "c1" if side == "v" else "c2")
            capped = r >= 2
            hit = f'<rect class="hit" x="{min(cx, x1):.1f}" y="{yb - 6:.1f}" width="{abs(x1 - cx):.1f}" height="{bh + 12}"/>'
            lx = x1 - 5 if side == "v" else x1 + 5
            anchor = "end" if side == "v" else "start"
            lab_txt = val + (" (capped)" if capped else "")
            if (side == "v" and lx - 6 * len(lab_txt) < 2) or (side == "c" and lx + 6 * len(lab_txt) > W - 2):
                lx, anchor = (cx + 6, "start") if side == "v" else (cx - 6, "end")   # no room outside: label on the other side
            o.append(tip(title, hit + mark) + tx(lx, yb + bh - 2, lab_txt, "", anchor))
        y += rh
    o.append(tx(cx, H - 6, "length: size of the lead, log scale, capped at 2x", "", "middle"))
    o.append("</svg>")
    table = htable(["Dimension", "Leads", "Values"], [[E(l), {"v": "vLLM fork", "c": "CuteAFD", "-": "level"}[s] if ok or s == "-" else "level", E(t)]
                                                     for l, s, r, v, ok, t in rows])
    return "".join(o), table


def chart_context(F):
    """Precision difference by context bucket: dot and 95% whisker, zero line, tpurtell's ±0.005 bar as a band."""
    d = F["d"]
    bk = [("all", "all rows"), ("0-2K", "0-2K"), ("2-8K", "2-8K"), ("8-16K", "8-16K, code")]
    W, l, r, rh = 340, 84, 24, 34
    H = 44 + len(bk) * rh + 22
    x0, x1 = -0.004, 0.008
    X = lambda v: l + (W - l - r) * (v - x0) / (x1 - x0)
    o = [svg(W, H, "Precision difference by context length"),
         key(2, 12, "c2", "CuteAFD") + key(80, 12, "c2", "CuteAFD with W8A16 prefill", hollow=True),
         f'<rect class="band" x="{X(x0):.1f}" y="36" width="{X(0.005) - X(x0):.1f}" height="{H - 58}"/>']
    for v in (-0.004, 0.0, 0.004, 0.008):
        o.append(f'<line class="{"axis" if v == 0 else "grid"}" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="36" y2="{H - 22}"/>'
                 + tx(X(v), H - 8, f"{v:+.3f}" if v else "0", "", "middle"))
    o.append(tx(X(0) - 4, 31, "vLLM fork", "", "end") + tx(X(0.005) - 3, 31, "±0.005 bar", "", "end"))
    y = 48
    for b, lab in bk:
        o.append(tx(l - 8, y + 6, lab, "lab", "end"))
        for arm, dy, cls in (("C1", -4, "c2"), ("F1c", 8, "c2o")):
            v = d[(b, "kl", arm)]
            name = "CuteAFD" if arm == "C1" else "CuteAFD with W8A16 prefill"
            o.append(tip(f"{name}, {lab}: {dkl(v[0])} [{v[1]:+.4f}, {v[2]:+.4f}] KL vs vLLM fork",
                         f'<rect class="hit" x="{X(v[1]):.1f}" y="{y + dy - 8:.1f}" width="{X(v[2]) - X(v[1]):.1f}" height="16"/>'
                         f'<line class="whisk" x1="{X(v[1]):.1f}" x2="{X(v[2]):.1f}" y1="{y + dy:.1f}" y2="{y + dy:.1f}"/>'
                         f'<circle class="{cls}" cx="{X(v[0]):.1f}" cy="{y + dy:.1f}" r="4"/>'))
        y += rh
    o.append("</svg>")
    table = htable(["Context", "CuteAFD − vLLM fork", "W8A16 prefill − vLLM fork"],
                   [[lab, f"{dkl(d[(b, 'kl', 'C1')][0])} [{d[(b, 'kl', 'C1')][1]:+.4f}, {d[(b, 'kl', 'C1')][2]:+.4f}]",
                     f"{dkl(d[(b, 'kl', 'F1c')][0])} [{d[(b, 'kl', 'F1c')][1]:+.4f}, {d[(b, 'kl', 'F1c')][2]:+.4f}]"] for b, lab in bk])
    return "".join(o), table


def chart_tradeoff(F):
    """F1: decode-speed cost (x) against the 8-16K KL difference from the vLLM fork (y), with 95% whiskers."""
    W, H, l, r, t, b = 340, 248, 50, 18, 28, 34
    x0, x1, y0, y1 = 0.88, 1.02, -0.002, 0.008
    X = lambda v: l + (W - l - r) * (v - x0) / (x1 - x0)
    Y = lambda v: t + (H - t - b) * (y1 - v) / (y1 - y0)
    # label position: above the whisker's top ("up") or below its bottom ("down"), so no label crosses a whisker
    names = {"C1": ("as shipped", "c2", "up", "end"), "f1a": ("KDA BF16", "c2o", "up", "middle"),
             "f1b": ("head BF16", "c2o", "up", "middle"), "f1c": ("W8A16 prefill", "c2o", "up", "end"),
             "f1d": ("all three off", "c2o", "down", "middle")}
    o = [svg(W, H, "Precision against speed for CuteAFD's FP8 switches"),
         f'<rect class="band" x="{l}" y="{Y(0.005):.1f}" width="{W - l - r}" height="{Y(y0) - Y(0.005):.1f}"/>']
    for v in (0.0, 0.004, 0.008):
        o.append(f'<line class="{"axis" if v == 0 else "grid"}" x1="{l}" x2="{W - r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 + tx(l - 5, Y(v) + 4, f"{v:+.3f}" if v else "0", "", "end"))
    for v in (0.90, 0.95, 1.00):
        o.append(f'<line class="grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{t}" y2="{H - b}"/>' + tx(X(v), H - b + 14, f"{v:.2f}x", "", "middle"))
    o.append(tx(l + 4, Y(0) - 4, "vLLM fork") + tx(l + 4, Y(0.005) + 12, "±0.005 bar"))
    o.append(tx(W - r, H - 4, "decode speed vs as shipped →", "", "end") + tx(2, 11, "KL difference from the vLLM fork, 8-16K"))
    rows = []
    for arm, (lab, cls, pos, anc) in names.items():
        p = F["f1"]["precision"][arm]["8-16K"]["vs_vllm_mean"]["kl"]
        s = F["f1_dec"].get(arm, 1.0)
        rows.append([lab, f"{s:.2f}x", f"{dkl(p[0])} [{p[1]:+.4f}, {p[2]:+.4f}]"])
        o.append(tip(f"{lab}: decode {s:.2f}x of as shipped; KL difference at 8-16K {dkl(p[0])} [{p[1]:+.4f}, {p[2]:+.4f}]",
                     f'<rect class="hit" x="{X(s) - 10:.1f}" y="{Y(p[2]):.1f}" width="20" height="{Y(p[1]) - Y(p[2]):.1f}"/>'
                     f'<line class="whisk" x1="{X(s):.1f}" x2="{X(s):.1f}" y1="{Y(p[1]):.1f}" y2="{Y(p[2]):.1f}"/>'
                     f'<circle class="{cls}" cx="{X(s):.1f}" cy="{Y(p[0]):.1f}" r="4.5"/>')
                 + tx(X(s) + (6 if anc == "end" else 0), Y(p[2]) - 5 if pos == "up" else Y(p[1]) + 13, lab, "", anc))
    o.append("</svg>")
    return "".join(o), htable(["CuteAFD setting", "Decode speed vs as shipped", "KL difference at 8-16K"], rows)


def chart_dumbbell(F):
    """Single-stream decode at 1K input: vLLM fork dot to CuteAFD dot, ratio at the right."""
    order = [c for c in ("prose", "code", "reasoning", "json") if c in F["dec1k"]]
    W, l, r, rh = 340, 70, 52, 30
    H = 30 + len(order) * rh + 18
    x0, x1 = 100, 250
    X = lambda v: l + (W - l - r) * (v - x0) / (x1 - x0)
    o = [svg(W, H, "Single-stream decode speed at 1K input"), tx(2, 11, "tokens per second, one request at a time")]
    for v in (100, 150, 200, 250):
        o.append(f'<line class="grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="20" y2="{H - 18}"/>' + tx(X(v), H - 4, v, "", "middle"))
    y = 36
    rows = []
    for n, c in enumerate(order):
        v, cu = F["dec1k"][c]
        name = c if c != "json" else "JSON"
        rows.append([name, f"{v:.1f}", f"{cu:.1f}", f"{cu / v:.2f}x"])
        o.append(tx(l - 8, y + 4, name, "lab", "end"))
        o.append(tip(f"{name}: vLLM fork {v:.1f}, CuteAFD {cu:.1f} tok/s ({cu / v:.2f}x)",
                     f'<rect class="hit" x="{X(v) - 8:.1f}" y="{y - 12}" width="{X(cu) - X(v) + 16:.1f}" height="24"/>'
                     f'<line class="conn" x1="{X(v):.1f}" x2="{X(cu):.1f}" y1="{y}" y2="{y}"/>'
                     f'<circle class="c1" cx="{X(v):.1f}" cy="{y}" r="5"/><circle class="c2" cx="{X(cu):.1f}" cy="{y}" r="5"/>'))
        o.append(tx(W - 2, y + 4, f"{cu / v:.2f}x", "lab", "end"))
        if c == max(order, key=lambda k: F["dec1k"][k][1] - F["dec1k"][k][0]):
            o.append(tx(X(v), y - 10, "vLLM fork", "", "middle") + tx(X(cu), y - 10, "CuteAFD", "", "middle"))
        y += rh
    o.append("</svg>")
    return "".join(o), htable(["Content", "vLLM fork tok/s", "CuteAFD tok/s", "Ratio"], rows)


def chart_length(F):
    """Aggregate throughput ratio by input length: median line, min-max band, 1.0 reference labelled 'level'."""
    rows = F["len"]
    Ls = list(rows)
    W, H, l, r, t, b = 340, 200, 40, 52, 22, 28
    y0, y1 = 0.8, 1.4
    X = lambda i: l + 14 + i * (W - l - r - 28) / (len(Ls) - 1)
    Y = lambda v: t + (H - t - b) * (y1 - v) / (y1 - y0)
    o = [svg(W, H, "Throughput ratio by input length"), tx(2, 11, "CuteAFD ÷ vLLM fork, tokens per second end to end")]
    for v in (0.8, 1.0, 1.2, 1.4):
        o.append(f'<line class="{"axis" if v == 1.0 else "grid"}" x1="{l}" x2="{W - r + 10}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 + tx(l - 5, Y(v) + 4, f"{v:.1f}", "", "end"))
    o.append(tx(W - r + 14, Y(1.0) + 4, "level"))
    band = [(X(i), Y(rows[L]["agg"][2])) for i, L in enumerate(Ls)] + [(X(i), Y(rows[L]["agg"][1])) for i, L in reversed(list(enumerate(Ls)))]
    o.append(f'<polygon class="wash2" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in band)}"/>')
    pts = [(X(i), Y(rows[L]["agg"][0])) for i, L in enumerate(Ls)]
    o.append(f'<polyline class="ln2" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>')
    tab = []
    for i, L in enumerate(Ls):
        m, lo, hi = rows[L]["agg"]
        tab.append([f"{L // 1024}K", f"{m:.2f}x", f"{lo:.2f}-{hi:.2f}x"])
        o.append(tip(f"{L // 1024}K input: median {m:.2f}x, cells {lo:.2f}-{hi:.2f}x",
                     f'<rect class="hit" x="{pts[i][0] - 12:.1f}" y="{Y(hi) - 4:.1f}" width="24" height="{Y(lo) - Y(hi) + 8:.1f}"/>'
                     f'<circle class="c2" cx="{pts[i][0]:.1f}" cy="{pts[i][1]:.1f}" r="4"/>') + tx(X(i), H - 8, f"{L // 1024}K", "", "middle"))
    m = rows[Ls[-1]]["agg"][0]
    o.append(tx(pts[-1][0] + 8, pts[-1][1] + 4, f"{m:.2f}x"))
    o.append("</svg>")
    return "".join(o), htable(["Input", "Median ratio", "Range of cells"], tab)


def chart_outcomes(F):
    """Long output at the 128K cap: 100% stacked bars per content type and engine (passed / partial or invalid / hit the cap)."""
    L = F["L"]
    order = ["code", "reasoning", "prose", "json"]
    good = {"code": "all tests pass", "reasoning": "correct", "prose": "finished", "json": "valid"}
    W, l, r, bh, gap = 340, 70, 34, 14, 6
    H = 30 + len(order) * (16 + 2 * (bh + gap) + 16) + 4
    X = lambda f: l + (W - l - r) * f
    o = [svg(W, H, "Long-output outcomes at the 128K cap"),
         '<rect class="c1" x="2" y="4" width="10" height="10" rx="2"/><rect class="c2" x="13" y="4" width="10" height="10" rx="2"/>',
         tx(27, 13, "passed"), '<rect class="g1" x="82" y="4" width="10" height="10" rx="2"/>', tx(96, 13, "partial or invalid"),
         '<rect class="g2" x="200" y="4" width="10" height="10" rx="2"/>', tx(214, 13, "hit the cap")]
    y = 30
    tab = []
    for c in order:
        o.append(tx(2, y + 10, c if c != "json" else "JSON", "lab"))
        y += 16
        for arm, cls, name in (("V1", "c1", "vLLM fork"), ("C1", "c2", "CuteAFD")):
            s = L[(arm, "L3", c)]
            n = s["n"]
            passed = {"code": s.get("all_pass", 0), "reasoning": s.get("correct", 0), "json": s.get("valid", 0), "prose": s["stop"]}[c]
            cap = s["cap"]; part = max(n - passed - cap, 0)
            tab.append([c, name, f"{passed}/{n}", f"{part}/{n}", f"{cap}/{n}"])
            o.append(tx(l - 6, y + bh - 3, name, "", "end"))
            xx = l
            for cnt, kcls, what in ((passed, cls, good[c]), (part, "g1", "partial or invalid"), (cap, "g2", "hit the cap")):
                if not cnt: continue
                w = (W - l - r) * cnt / n
                o.append(tip(f"{name}, {c}: {what} {cnt} of {n}",
                             f'<rect class="{kcls}" x="{xx:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="{bh}" rx="2"/>')
                         + (tx(xx + (w - 2) / 2, y + bh - 3, cnt, {"g1": "inbar on-g1", "g2": "inbar on-g2"}.get(kcls, "inbar"), "middle")
                            if w >= 18 else ""))
                xx += w
            o.append(tx(W - 2, y + bh - 3, f"n={n}", "", "end"))
            y += bh + gap
        y += 16
    o.append("</svg>")
    return "".join(o), htable(["Content", "Engine", "Passed", "Partial or invalid", "Hit the cap"], tab)


def chart_startup(S):
    """Startup timeline: stacked phase bars per run (ordered phases as steps of the engine hue), total at the right."""
    if not S: return None, None
    runs = S["runs"]
    W, l, r, bh = 340, 4, 40, 16
    tmax = max(x["ready_s"] for x in runs)
    H = 20 + len(runs) * (bh + 30) + 22
    X = lambda s: l + (W - l - r) * s / tmax
    o = [svg(W, H, "Startup timeline")]
    for v in range(0, int(tmax) + 1, 120):
        o.append(f'<line class="grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="14" y2="{H - 20}"/>'
                 + tx(X(v), H - 6, f"{v // 60} min", "", "start" if v == 0 else "middle"))
    y = 22
    tab = []
    for run in runs:
        cls = "c2" if "cuteafd" in run["label"].lower() else "c1"
        o.append(tx(l, y + 8, run["label"], "lab"))
        yb = y + 12; x = X(0)
        for i, ph in enumerate(run["phases"]):
            w = X(ph["s"]) - X(0)
            op = [1.0, 0.72, 0.5, 0.34, 0.22][min(i, 4)]
            o.append(tip(f"{run['label']}: {ph['name']} {ph['s']} s",
                         f'<rect class="{cls}" style="opacity:{op}" x="{x:.1f}" y="{yb}" width="{max(w - 2, 1):.1f}" height="{bh}" rx="2"/>'))
            if w > 46 and len(run["phases"]) > 1 and op >= 0.7:     # white on the two strongest steps only
                o.append(tx(x + 4, yb + bh - 4, ph["name"].split(" (")[0].replace("process start + ", "")[:int(w / 6)], "inbar"))
            x += w
            tab.append([run["label"], ph["name"], f"{ph['s']} s"])
        o.append(tx(x + 4, yb + bh - 3, f"{run['ready_s']} s"))
        y += bh + 30
    o.append("</svg>")
    return "".join(o), htable(["Run", "Phase", "Time"], tab)


def chart_precision(F):
    """Absolute KL by context bucket (precision page): three series, direct labels in text colour beside key marks."""
    W, H, l, r, t, b = 340, 230, 40, 138, 24, 30
    y0, y1 = 0.030, 0.060
    xs = {"0-2K": 0, "2-8K": 1, "8-16K": 2}
    X = lambda i: l + 18 + i * ((W - l - r - 30) / 2)
    Y = lambda v: t + (H - t - b) * (y1 - v) / (y1 - y0)
    o = [svg(W, H, "KL from the BF16 model by context length"), tx(2, 11, "KL from BF16 (lower is closer)")]
    for v in (0.030, 0.040, 0.050, 0.060):
        o.append(f'<line class="grid" x1="{l}" x2="{W - r + 14}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>' + tx(l - 5, Y(v) + 4, f"{v:.3f}", "", "end"))
    for bkt, i in xs.items(): o.append(tx(X(i), H - 12, bkt, "", "middle"))
    series = [("kl_v", "ln1", "c1", "vLLM fork", False), ("kl_c", "ln2", "c2", "CuteAFD", False), ("kl_f1c", "ln2d", "c2o", "CuteAFD W8A16", True)]
    ends, tab = [], []
    for key_, ln, dot, name, hollow in series:
        pts = [(X(i), Y(F[key_][bkt])) for bkt, i in xs.items()]
        o.append(f'<polyline class="{ln}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>')
        o += [tip(f"{name}, {bkt}: KL {F[key_][bkt]:.4f}", f'<circle class="hit" cx="{x:.1f}" cy="{y:.1f}" r="12"/><circle class="{dot}" cx="{x:.1f}" cy="{y:.1f}" r="4"/>')
              for (x, y), bkt in zip(pts, xs)]
        ends.append([pts[-1][1], name, F[key_]["8-16K"], dot])
        tab.append([name] + [kl(F[key_][bkt]) for bkt in xs])
    ends.sort()
    for k in range(1, len(ends)):
        if ends[k][0] - ends[k - 1][0] < 14: ends[k][0] = ends[k - 1][0] + 14
    for y, name, v, dot in ends:
        o.append(f'<line class="conn" x1="{X(2) + 6:.1f}" x2="{X(2) + 12:.1f}" y1="{y:.1f}" y2="{y:.1f}"/>' + tx(X(2) + 15, y + 4, f"{name} {v:.4f}"))
    o.append("</svg>")
    return "".join(o), htable(["Configuration", "0-2K", "2-8K", "8-16K"], tab)


def figure(title, chart, caption, cls=""):
    """chart: (svg, table) from a chart function; the table is the figure's data view."""
    s, table = chart if isinstance(chart, tuple) else (chart, "")
    data = f'<details class="data"><summary>Data</summary>{table}</details>' if table else ""
    return f'<figure class="{cls}">{s}<figcaption><div class="t">{title}</div><div class="s">{caption}</div></figcaption>{data}</figure>'


def htable(head, rows, cls=""):
    return (f'<div class="tbl"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")


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
         f"KL from BF16, vLLM fork vs CuteAFD, tpurtell's fidelity set. His official FP8 model scores 0.0216 on the same set. "
         f"At 8-16K: {kl(F['kl_v']['8-16K'])} vs {kl(F['kl_c']['8-16K'])}."),
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


def which_to_use(F):
    d, rows = F["d"], F["len"]
    lo, hi = F["dec_range"]
    a8 = rows[1024]["agg8"]
    t16 = rows[1024]["tth"]; t32 = rows[32768]["tth"]
    return ('<h2 id="which-to-use">Which to use when</h2><ul class="use">'
            f'<li><b>CuteAFD for single-user and agent-style work with long or repeated contexts.</b> Single-stream decode is '
            f'{span(lo, hi)} faster, long prompts prefill at about 4,400-4,500 against 3,700-3,900 tokens per second, '
            f'and a repeated prompt comes back from its cache in 0.017 s. Limit: with many long prompts at once, its first tokens '
            f'come later (32K input, {rows[32768]["hi"]} streams: {max(b for _, b in t32):.0f} vs {max(a for a, _ in t32):.0f} s), '
            'because it schedules prefills ahead of decode.</li>'
            f'<li><b>The vLLM fork where long-code precision matters most, or for many short concurrent prompts.</b> It is closer '
            f'to BF16 at 8-16K ({dkl(d[("8-16K", "kl", "C1")][0])} KL in its favour), answers 1K prompts sooner (0.25 vs 0.41 s), '
            f'and at 1K input with 8 streams completes {span(1 / max(a8), 1 / min(a8))} more tokens per second.</li>'
            f'<li><b>CuteAFD with W8A16 prefill as a middle option</b> (<code>GLM5_FLASH_FP8_PREFILL=off</code>): about half of the '
            f'precision difference goes ({dkl(d[("all", "kl", "C1")][0])} → {dkl(d[("all", "kl", "F1c")][0])} overall), for about '
            f'{pp(F["f1c_ttft"])} longer time to first token and no measured decode cost.</li></ul>'
            '<p class="note">One machine: two RTX PRO 6000 Blackwell Max-Q GPUs at their 300 W power cap, one model '
            '(GLM-5.3-Flash, EXL3 K3.25 experts), thinking on. Other GPUs, quantizations or settings can change the picture.</p>')


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
             ("NLL", "Negative log-likelihood of the actual text: lower means the engine found the text less surprising."),
             ("TTFT", "Time to first token: from sending a request to the first generated token; mostly prompt processing."),
             ("Prefill", "Processing the prompt before generation starts. Decode: generating tokens one step at a time."),
             ("Stream", "One request in flight. Aggregate: all completion tokens of a batch divided by its wall time."),
             ("W8A8 / W8A16", "FP8 weights with FP8 or 16-bit activations in CuteAFD's prefill matrix multiplies.")]
    return ('<h2 id="terms">Terms</h2><dl class="gl">' + "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in terms)
            + "</dl>")


def sign_note():
    return '<p class="sign">Sign convention: a positive KL difference means CuteAFD is further from the BF16 model than the vLLM fork.</p>'


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
    run = f'<a href="{REPO_URL}/tree/main/{RD}">receipts</a>'
    lo, hi = F["dec_range"]

    S = startup()
    fig_hero = figure("Where each engine leads", chart_hero(F, S),
                      "Bars to the left mean the vLLM fork leads, to the right CuteAFD; grey rows are level. CuteAFD leads on "
                      "speed and restarts, the vLLM fork on precision and on short first tokens.")
    fig_ctx = figure("Precision difference by context length", chart_context(F),
                     "The difference sits at 8-16K, the panel's long code reading; below 8K the intervals include zero. "
                     "Hollow dots: W8A16 prefill, which pulls the 8-16K difference about half way back.")
    fig_trade = lambda cls="": figure("Precision against speed: CuteAFD's FP8 switches", chart_tradeoff(F),
                     "Most of the 8-16K precision difference comes back for almost no speed: W8A16 prefill keeps 99% of decode "
                     "speed. Measured against the mean of the first two vLLM runs, as in follow-up F1.", cls)
    fig_dumb = figure("Single-stream speed by content type, 1K input", chart_dumbbell(F),
                      "CuteAFD is faster on every content type, most on reasoning and code (with thinking on, those cells "
                      "are reasoning text).")
    fig_len = figure("Throughput by input length, CuteAFD ÷ vLLM fork", chart_length(F),
                     "Level at 1K-8K, then CuteAFD pulls ahead as prompts grow: its prefill is faster. The band spans the "
                     "cells (content types, 1-16 streams).")
    fig_lo = figure("Long-output outcomes at the 128K cap", chart_outcomes(F),
                    "Code, math and prose come out the same on both engines; JSON differs, on two seeds per prompt.")
    su = chart_startup(S)
    fig_su = (figure("Startup to ready", su, "On this setup, persisting the vLLM fork's JIT caches removes the TileLang "
                     "compiles and most of the graph-capture time; weight loading remains. CuteAFD ships its kernels compiled.")
              if su[0] else '<p class="note">Startup timeline: pending.</p>')
    fig_p = figure("Distance from the BF16 model by context length", chart_precision(F),
                   "Absolute KL from BF16 on generated rows. The buckets also differ in content, so the level across buckets "
                   "is not a trend with length.")

    answer = ("On two RTX PRO 6000s, CuteAFD is the faster engine and tpurtell's vLLM fork is the slightly more precise one; "
              f"one CuteAFD setting (W8A16 prefill) halves the precision difference for about {pp(F['f1c_ttft'])} slower "
              "first token.")
    page("index.html", "CuteAFD and tpurtell's vLLM fork on two RTX PRO 6000s", html.escape(answer),
         '<p class="lede">Both engines are tpurtell\'s. Same model (GLM-5.3-Flash with his 3.25-bit EXL3 experts), same '
         f'machine, measured under a frozen protocol with an independent audit. Every number comes from the {run} in the '
         'repository.</p>' + fig_hero + cards(F) +
         '<h2 id="charts">The results in pictures</h2>' + fig_ctx + fig_trade("small") + fig_dumb +
         which_to_use(F) + how_sure() + glossary() +
         '<h2 id="detail">In detail</h2><ul class="links">' +
         "".join(f'<li><a href="{p}">{t}</a>: {html.escape(s)}</li>' for p, t, s in LINKS) + "</ul>", lede_cls="answer")

    # precision
    bk = [("all", "All"), ("0-2K", "0-2K"), ("2-8K", "2-8K"), ("8-16K", "8-16K, long code")]
    key = [[lab, kl(F["kl_v"][b]), kl(F["kl_c"][b]), f'<b>{dkl(d[(b, "kl", "C1")][0])}</b> {civ(d[(b, "kl", "C1")])}'
            f'<br>W8A16: {dkl(d[(b, "kl", "F1c")][0])} {civ(d[(b, "kl", "F1c")])}'] for b, lab in bk]
    top = [[lab, f'{100 * d[(b, "top1", "C1")][0]:+.2f} pts<br>{civ(d[(b, "top1", "C1")], 2, 100)}'] for b, lab in bk]
    rq = strip_title(read(f"{RD}/q/RESULTS-Q.md")); f1 = strip_title(read(f"{RD}/f1/RESULTS-F1.md"))
    page("precision.html", "Precision", "How close each engine's next-token probabilities stay to the original BF16 model.",
         f'<p class="plain">Both engines are close to BF16; CuteAFD is slightly further, by {dkl(d[("all", "kl", "C1")][0])} KL '
         f'overall and {dkl(d[("8-16K", "kl", "C1")][0])} at 8-16K, where the panel is long code reading. Below 8K the '
         'intervals include zero. W8A16 prefill removes about half of the overall difference. On human-written text at '
         '32K-128K the engines\' NLL differs by no more than about ±0.005 nat (six documents, no BF16 reference there).</p>' +
         fig_ctx + fig_trade() + fig_p + f'<p class="sign">KL from BF16 on generated rows; vLLM = mean of {F["n_vruns"]} runs. Difference = CuteAFD '
         'minus vLLM: positive means CuteAFD is further from BF16; the second line is CuteAFD with W8A16 prefill. In grey: 95% '
         'interval.</p>' + htable(["Context", "vLLM", "CuteAFD", "Difference"], key) +
         details("Top-1 agreement, CuteAFD minus vLLM fork", htable(["Context", "Difference"], top)) +
         f'<p class="sign">The 2K full-vocabulary panel (P-A) gives {dkl(F["pa"]["B_minus_A"])} '
         f'<span class="ci">[{F["pa"]["ci95"][0]:+.4f}, {F["pa"]["ci95"][1]:+.4f}]</span>. Intervals: 95%, paired bootstrap over windows.</p>' +
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
         fig_len + '<p class="sign">Decode: CuteAFD vs vLLM, one request at a time. Throughput: CuteAFD ÷ vLLM, median over '
         'content types and 1-16 streams (range). First token: one request, vLLM vs CuteAFD.</p>' +
         htable(["Input", "Decode", "Throughput", "First token"], lrows) + fig_dumb +
         f'<details class="more" id="caveats"><summary>Caveats: inputs, labels, draft policies, noise</summary>{md(cav, f"{RD}/t", 1)}</details>' +
         details("The headline cells", md(B.t_table()) + md(B.t_counts())) +
         f'<details class="more" id="drift"><summary>Drift check: the same cells hours later</summary>{md(dr, f"{RD}/drift", 1)}</details>' +
         f'<details class="more" id="follow-up-f2"><summary>Follow-up F2: the vLLM fork\'s prefix-cache reuse</summary>{md(f2, f"{RD}/f2", 1)}</details>' +
         f'<details class="more" id="full-grid"><summary>Full grid: every cell, decode, aggregate, first token, prefill</summary>{md(ts, f"{RD}/t", 1)}</details>')

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
         fig_lo + f'<div class="outcomes">{cards_l}</div>' +
         '<p class="sign">At the 128K cap; 8 replies per content type (4 prompts, 2 seeds).</p>' +
         details("Every stage, 8K, 32K, 128K and one at a time", md(B.L_NOTE) + md(B.l_table(detail=True))))

    page("observations.html", "Observations and confounds", "Behaviour differences between the two stacks, each with how it "
         "is known, and what else differs and how each block handles it.",
         '<p class="plain">The differences a user notices first: CuteAFD honours "thinking off" and the vLLM fork does not; '
         'CuteAFD reuses repeated prompts from its cache and the vLLM fork only in whole 4,352-token blocks; '
         + E(startup_sentence(short=True)) + '; the vLLM fork\'s '
         'long prefill is not bit-reproducible run to run, CuteAFD\'s is.</p>' +
         '<h2 id="observations-in-detail">Observations in detail</h2>' + md(R.get("Observations in detail", "")) + fig_su +
         f'<details class="more" id="confounds"><summary>Confounds: what else differs, and how it is handled</summary>{md(R.get("Confounds", ""))}</details>')

    proto = strip_title(read("protocol/PROTOCOL.md")); fol = strip_title(read("protocol/FOLLOWUPS.md"))
    page("method.html", "Method", "How the comparison was set up and measured.",
         '<p class="plain">Each engine ran as its author ships it, with a short list of local changes, on one machine. Precision '
         'was scored teacher-forced against a BF16 reference; speed and long output with one client, unique prompts and a '
         'distinct seed per request. The protocol was frozen before the speed and long-output runs; three follow-ups and a drift '
         'check were declared later and are labelled as such.</p>' +
         '<h2 id="limits">Limits</h2>' + summary_block("Limits") +
         '<h2 id="status">Status</h2>' + md(B.status_lines()) +
         f'<details class="more" id="setup"><summary>Setup: hardware, engines, checkpoints, settings</summary>{md(R.get("Setup", ""))}</details>' +
         f'<details class="more" id="protocol"><summary>The protocol, v2 with amendments A1-A2</summary>'
         f'{md(strip_title(read("protocol/README.md")).split(chr(10) + "## ")[0], "protocol")}{md(proto, "protocol", 2)}</details>' +
         f'<details class="more" id="follow-ups"><summary>Follow-ups F1-F3 and the drift check</summary>{md(fol, "protocol", 1)}</details>' +
         f'<details class="more" id="other-runs"><summary>Other runs: checks and an exploratory test</summary>{md(R.get("Other runs", ""))}</details>')

    au = strip_title(read(f"{RD}/AUDIT-2026-10-27.md"))
    page("audit.html", "Independent audit (2026-10-27)", "A read-only, CPU-only review of the precision and speed blocks and "
         "of vLLM's long-output block, made before CuteAFD's long-output block and the later follow-ups ran.",
         '<p class="plain">The audit found the instruments sound and the precision difference robust. It traced the vLLM '
         'fork\'s run-to-run variation to multi-chunk prefill, which led to pairing CuteAFD against several vLLM runs; showed '
         'that the 8-16K bucket is long code reading, so length and content are not separated; and confirmed the speed '
         'explanation (prefill-first scheduling).</p>' + md(au, RD, 1))

    page("ledger.html", "Ledger", "What was run and established, and when (times UTC−7).", md(R.get("Ledger", "")))

    page("reproduce.html", "Reproduce", "From the frozen protocol to the published summaries, step by step.",
         md(strip_title(read("repro/REPRODUCE.md")), "repro", 1) + '<h2 id="verify">Verify and rebuild</h2>' + md(R.get("Reproduce", "")))
    print(f"wrote {len(PAGES)} pages to docs/")


if __name__ == "__main__":
    main()
