#!/usr/bin/env python3
"""Build the results site (GitHub Pages, served from main /docs) from the repository's own files.

    python3 tools/build_site.py

One page per question. The home page and README.md share their text (tools/build_readme.py, home_parts()); every other
page opens with a short answer, then its evidence. Reads README.md (built by tools/build_readme.py), the result markdown
and JSON under results/, the protocol, the audit and repro/REPRODUCE.md, and writes static HTML pages to docs/. No
scripts, no external stylesheets, fonts or images: plain HTML with one inline stylesheet, light and dark
(prefers-color-scheme), readable at phone width. Links between pages are relative; links to files in the repository
point at REPO_URL, the one place the repository's address is assumed. Charts are static SVG drawn by
tools/site_charts.py (one chart grammar, described there). Standard library only (Python 3.10+).
"""
import html, importlib.util, re, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO_URL = "https://github.com/UrbanAstroLA/cuteafd-eval"          # the only absolute address the site assumes
spec = importlib.util.spec_from_file_location("build_readme", ROOT / "tools" / "build_readme.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
RUN, D = B.RUN, B.D
RD = f"results/{RUN}"
R4D = B.D4
R4 = f"results/{B.K4}"
_cs = importlib.util.spec_from_file_location("site_charts", ROOT / "tools" / "site_charts.py")
C = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(C)

PAGES = [("index.html", "Home"), ("precision.html", "Precision"), ("settings.html", "Settings"), ("speed.html", "Speed"),
         ("long-tasks.html", "Long tasks"), ("running.html", "Running it"), ("method.html", "Method"), ("audit.html", "Audit"),
         ("research.html", "Research"), ("reproduce.html", "Reproduce")]
SITE = {p for p, _ in PAGES}
# pages of the earlier site layout: a stub that sends the reader to the page that now answers the question
MOVED = {"throughput.html": ("speed.html", "Speed"), "long-output.html": ("long-tasks.html", "Long tasks"),
         "observations.html": ("running.html", "Running it"), "ledger.html": ("method.html#timeline", "Method: timeline")}
# repository files that have a page of their own
PAGE_OF = {f"{RD}/AUDIT-2026-10-27.md": "audit.html", "repro/REPRODUCE.md": "reproduce.html"}
# README anchors -> pages
ANCHOR_OF = {"running-it-observations-in-detail": "running.html", "setup": "method.html#setup", "confounds": "method.html#confounds",
             "reproduce": "reproduce.html", "timeline": "method.html#timeline"}

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
a{color:var(--s1)}.lede{font-size:16px;max-width:820px}.lede p,.lede li{color:var(--ink)}b,strong{color:var(--ink)}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13.5px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tbl{overflow-x:auto}.note{border-left:3px solid var(--axis);padding:6px 12px;margin:14px 0;color:var(--ink2);font-size:14px}
blockquote{border-left:3px solid var(--axis);margin:14px 0;padding:2px 12px}
code{font-size:12.5px;overflow-wrap:anywhere}pre{overflow-x:auto;background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:10px;font-size:12.5px;line-height:1.45}
pre code{overflow-wrap:normal;white-space:pre}
details.more{border-left:3px solid var(--grid);padding:2px 0 2px 12px;margin:10px 0}details.more>summary{cursor:pointer;color:var(--ink2);font-size:14px}
details.more[open]>summary{margin-bottom:6px}
.answer{font-size:clamp(17px,4.4vw,20px);line-height:1.45;color:var(--ink);max-width:820px;margin:10px 0 18px;font-weight:500}
figure{background:var(--surface);border:1px solid var(--ring);border-radius:10px;margin:16px 0;padding:14px 14px 10px}
figcaption .t{font-weight:600;color:var(--ink)}svg{display:block;width:100%;height:auto;max-width:560px;margin:8px 0;font:12px system-ui,-apple-system,"Segoe UI",sans-serif}
svg text{fill:var(--ink2)}svg .lab{fill:var(--ink)}svg .grid{stroke:var(--grid);stroke-width:1}svg .axis{stroke:var(--axis);stroke-width:1}
svg .c1{fill:var(--s1);stroke:var(--s1)}svg .c2{fill:var(--s2);stroke:var(--s2)}svg .hit{fill:transparent;stroke:none}svg .inbar{fill:#fff;font-size:11px}
details.data{margin:6px 0 0}details.data>summary{cursor:pointer;color:var(--ink2);font-size:13px}
svg path.c1,svg path.c2,svg rect.c1,svg rect.c2{stroke:none}.ci{color:var(--muted);font-size:12px;white-space:nowrap}td .ci,p .ci,li .ci{white-space:normal}
.sign{font-size:13px;color:var(--ink2)}dl.gl{columns:2 320px;column-gap:28px}dl.gl div{break-inside:avoid;margin:0 0 8px}
dl.gl dt{font-weight:600;color:var(--ink);display:inline}dl.gl dt::after{content:": "}dl.gl dd{display:inline;margin:0;color:var(--ink2)}
.pages li{margin:6px 0}.slot{border:1px dashed var(--axis);border-radius:10px;padding:8px 14px;margin:12px 0;color:var(--ink2)}
footer{max-width:980px;margin:0 auto;padding:0 16px 40px;color:var(--muted);font-size:13px}footer nav{padding:10px 0;border:0;margin:0;max-width:none}"""
CSS += "\n" + C.CSS
E = html.escape


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
    if path in SITE: return url                                    # a page of this site
    parts = []
    for seg in (base.split("/") if base else []) + path.split("/"):
        if seg in ("", "."): continue
        if seg == "..":
            if parts: parts.pop()
        else: parts.append(seg)
    p = "/".join(parts)
    if p.rstrip("/") in PAGE_OF: return PAGE_OF[p.rstrip("/")]
    if p == "README.md": return ANCHOR_OF.get(frag, "index.html" + (f"#{frag}" if frag else ""))
    target = ROOT / p
    kind = "tree" if target.is_dir() or path.endswith("/") else "blob"
    return f"{REPO_URL}/{kind}/main/{p.rstrip('/')}" + (f"#{frag}" if frag else "")


def inline(text, base, codelink=None):
    """codelink(span) -> html or None: lets a page turn `file` references into links (audit, reproduce)."""
    codes = []
    def keep(m):
        c = codelink(m.group(1)) if codelink else None
        codes.append(c or f"<code>{E(m.group(1))}</code>"); return f"\x00{len(codes) - 1}\x00"
    text = re.sub(r"`([^`]+)`", keep, text)
    text = E(text, quote=False)
    def link(m):
        label, url = m.group(1), html.unescape(m.group(2))
        label = re.sub(r"\x00(\d+)\x00", lambda x: re.sub(r"</?a[^>]*>", "", codes[int(x.group(1))]), label)
        return f'<a href="{E(href(url, base))}">{label}</a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w])_(?!\s)([^_]+?)(?<!\s)_(?![\w])", r"<i>\1</i>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


NUM = re.compile(r"^[−\-+~]?[\d.,]+(?:-[\d.,]+)?(?:%| pts| s|x| tok/s)?$")
FENCE = re.compile(r"^(\s*)```")


def md(text, base="", shift=0, codelink=None):
    """Convert markdown to HTML. base: repository directory of the source file (for links); shift: heading levels to add.
    Fenced code may be indented under a list item: it ends the list (an ordered list resumes with its own number) and
    renders as one multi-line <pre>."""
    il = lambda s: inline(s, base, codelink)
    lines, prev_tbl, fence = [], False, False
    for l in text.replace("\r\n", "\n").split("\n"):    # tables indented under a list item: lift them out of the list
        if FENCE.match(l): fence = not fence
        is_tbl = not fence and bool(re.match(r"^\s+\|", l))
        if is_tbl and not prev_tbl: lines.append("")
        if prev_tbl and not is_tbl and l.strip(): lines.append("")
        lines.append(l.lstrip() if is_tbl else l); prev_tbl = is_tbl
    out, i = [], 0
    def para(buf):
        if buf: out.append("<p>" + il(" ".join(x.strip() for x in buf)) + "</p>")
    buf = []
    while i < len(lines):
        l = lines[i]
        fm = FENCE.match(l)
        if fm:
            para(buf); buf = []; ind = len(fm.group(1)); j = i + 1
            while j < len(lines) and not FENCE.match(lines[j]): j += 1
            body = [x[ind:] if x[:ind].strip() == "" else x.lstrip() for x in lines[i + 1:j]]
            out.append("<pre><code>" + E("\n".join(body)) + "</code></pre>"); i = j + 1; continue
        m = re.match(r"^(#{1,6}) (.*)$", l)
        if m:
            para(buf); buf = []
            lvl = min(6, len(m.group(1)) + shift); h = il(m.group(2))
            out.append(f'<h{lvl} id="{slug(h)}">{h}</h{lvl}>'); i += 1; continue
        if l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1]):
            para(buf); buf = []
            cells = lambda s: [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s.strip()[1:-1] if s.strip().endswith("|") else s.strip()[1:])]
            head = cells(l); rows = []; j = i + 2
            while j < len(lines) and lines[j].startswith("|"): rows.append(cells(lines[j])); j += 1
            td = lambda c: f'<td class="n">{il(c)}</td>' if NUM.match(c) else f"<td>{il(c)}</td>"
            out.append('<div class="tbl"><table><thead><tr>' + "".join(f"<th>{il(c)}</th>" for c in head) +
                       "</tr></thead><tbody>" + "".join("<tr>" + "".join(td(c) for c in r) + "</tr>" for r in rows) +
                       "</tbody></table></div>"); i = j; continue
        if re.match(r"^\s*(?:[-*]|\d+\.) ", l):
            para(buf); buf = []; j = i
            items = []                                   # (indent, ordered, text, number)
            while j < len(lines) and lines[j].strip() and not FENCE.match(lines[j]):
                mm = re.match(r"^(\s*)([-*]|\d+\.) (.*)$", lines[j])
                if mm: items.append([len(mm.group(1)), mm.group(2)[0].isdigit(), mm.group(3),
                                     int(mm.group(2)[:-1]) if mm.group(2)[0].isdigit() else None])
                elif items: items[-1][2] += " " + lines[j].strip()
                j += 1
            out.append(render_list(items, il)); i = j; continue
        if l.startswith(">"):
            para(buf); buf = []; j = i; q = []
            while j < len(lines) and lines[j].startswith(">"): q.append(lines[j][1:].lstrip()); j += 1
            out.append("<blockquote>" + md("\n".join(q), base, codelink=codelink) + "</blockquote>"); i = j; continue
        if not l.strip() or l.strip() == "---":
            para(buf); buf = []
            if l.strip() == "---": out.append("<hr>")
            i += 1; continue
        buf.append(l); i += 1
    para(buf)
    return "\n".join(out)


def render_list(items, il):
    out, stack = [], []
    for ind, ordered, text, number in items:
        while stack and ind < stack[-1][0]:
            out.append("</li></" + stack.pop()[1] + ">")
        if not stack or ind > stack[-1][0]:
            tag = "ol" if ordered else "ul"; stack.append((ind, tag))
            start = f' start="{number}"' if ordered and number not in (None, 1) else ""
            out.append(f"<{tag}{start}><li>")
        else:
            out.append("</li><li>")
        out.append(il(text))
    while stack: out.append("</li></" + stack.pop()[1] + ">")
    return "".join(out)


# ------------------------------------------------------------------ sources and page frame

def sections(text, level=2):
    """{heading: body} of a markdown text at one heading level."""
    parts = re.split(rf"(?m)^{'#' * level} ", text)
    out = {}
    for s in parts[1:]:
        head, _, body = s.partition("\n")
        out[head.strip()] = body.strip()
    return out


def read(rel):
    p = ROOT / rel
    return p.read_text() if p.exists() else ""


def strip_title(text):
    return re.sub(r"\A# [^\n]*\n", "", text.lstrip())


def gh(path, label=None):
    """A link to a repository file or folder on GitHub."""
    kind = "tree" if (ROOT / path).is_dir() else "blob"
    return f'<a href="{REPO_URL}/{kind}/main/{path}">{label or f"<code>{E(path)}</code>"}</a>'


def page(name, title, lede, body, answer=True):
    """lede: HTML (the page's short answer). Refuses a page with duplicate ids."""
    nav = "".join(f'<a href="{p}" class="{"on" if p == name else ""}">{t}</a>' for p, t in PAGES)
    foot = "".join(f'<a href="{REPO_URL}/blob/main/{f}">{t}</a>' for f, t in
                   [("README.md", "README"), ("protocol/README.md", "Protocol"), ("NOTICE.md", "Notice"),
                    ("LICENSE", "Licence (code)"), ("LICENSE-DATA.md", "Licence (results)"), ("CITATION.cff", "Citation")])
    lead = f'<div class="{"answer" if answer else "lede"}">{lede}</div>'
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
           f'initial-scale=1"><meta name="color-scheme" content="light dark"><title>{E(title)} - cuteafd-eval</title>'
           f'<style>\n{CSS}\n</style></head><body><nav aria-label="Pages"><span class="brand">cuteafd-eval</span>{nav}</nav><main>'
           f'<h1>{E(title)}</h1>{lead}\n{body}\n</main><footer><nav aria-label="Repository documents">'
           f'{foot}</nav>Generated from the repository data by <code>tools/build_site.py</code>. Maintained by Michael M '
           f'(UrbanAstroLA on GitHub, @UrbanAstroFella on X). Results CC BY 4.0, code Apache-2.0.</footer></body></html>\n')
    ids = re.findall(r'\bid="([^"]+)"', doc)
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup: raise SystemExit(f"docs/{name}: duplicate ids {dup}")
    (DOCS / name).write_text(doc)


def moved_page(name, target, label):
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
           f'initial-scale=1"><meta http-equiv="refresh" content="0; url={target}"><title>Moved - cuteafd-eval</title></head>'
           f'<body><p>This page moved: <a href="{target}">{E(label)}</a>.</p></body></html>\n')
    (DOCS / name).write_text(doc)


def details(summary_text, inner, did=None):
    return f'<details class="more"{f" id={chr(34)}{did}{chr(34)}" if did else ""}><summary>{summary_text}</summary>{inner}</details>'


def htable(head, rows, cls=""):
    return (f'<div class="tbl"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")


def h2(hid, text): return f'<h2 id="{hid}">{E(text)}</h2>'


# ------------------------------------------------------------------ numbers (from the published JSON)

def facts():
    q = D / "q"
    gen = lambda a: B.load(q / "pb" / f"pb-{a}.json")["summary"]["gen"]
    v_runs = [gen(a) for a in ("V1", "V1r", "V2")]
    bk = ("0-2K", "2-8K", "8-16K")
    F = {"n_vruns": len(v_runs)}
    F["kl_v"] = {b: st.mean(r["by_bucket"][b]["kl"]["value"] for r in v_runs) for b in bk}
    F["kl_v"]["all"] = st.mean(r["overall"]["kl"]["value"] for r in v_runs)
    c = gen("C1"); F["kl_c"] = {**{b: c["by_bucket"][b]["kl"]["value"] for b in bk}, "all": c["overall"]["kl"]["value"]}
    f1 = B.load(D / "f1/F1-RESULTS.json")
    m = B.load(q / "pb/pb-vs-vllm-mean3.json")
    F["d"] = {(b, met, arm): m[f"{b}|{met}|{arm}"] for b in ("all",) + bk for met in ("kl", "top1") for arm in ("C1", "F1c", "F1d")}
    F["pa"] = B.load(D / "q/pa/pa-pair-V1-vs-C1.json")["overall"]["kl"]
    F["f1"] = f1
    F["L"] = B.l_summaries()
    F["T"] = tails()
    return F


def startup():
    p = ROOT / "results/2026-10-27-vllm-startup-cache/startup.json"
    return B.load(p) if p.exists() else None


def tails():
    return {k: B.load(D / "q" / "tails" / f"{k}-tails.json") for k in ("pa", "pb", "q2") if (D / "q" / "tails" / f"{k}-tails.json").exists()}


def kl(x): return f"{x:.4f}"
def num(x): return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"
def hist(c): return f"{num(c['min'])} / {num(c['median'])} / {num(c['max'])}"
def hist_short(c): return f"{num(c['min'])}-{num(c['max'])} tokens of history, median {num(c['median'])}"
def pb_band(T, b): return next(x for x in T["pb"]["by_position"] if x["band"] == b)
def vmean(arms, key, names=("V1", "V1r", "V2")): return st.mean(arms[a][key] for a in names if a in arms)
def pctc(r): return f"{100 * (r - 1):+.0f}%".replace("-", C.MINUS)
def pct1(r): return f"{100 * (r - 1):+.1f}%".replace("-", C.MINUS)


sg, cit, rx = C.sg, C.ci_txt, C.rx
f1_speed, k4_settings, k4_setting_speed, k325_cells, k4_cells = B.f1_speed, B.k4_settings, B.k4_setting_speed, B.k325_cells, B.k4_cells


# ------------------------------------------------------------------ chart helpers (tools/site_charts.py: one grammar, static SVG)
# Engine colour and shape follow the engine: vLLM fork = blue circle, CuteAFD = orange triangle; a hollow triangle is a
# CuteAFD setting that does not fit a serving launch on 2x RTX PRO 6000 with that checkpoint. Every number below is read
# from the published files; where a figure needs a value the files do not publish (an interval), it is drawn without
# one and the table view says so.

LG_ENGINE = [("v", "vLLM fork"), ("c", "CuteAFD"), ("ci", "95% interval excludes the reference (resolved)"),
             ("ciu", "95% interval includes it (not resolved)"), ("band", "the vLLM fork's own run-to-run spread")]


def vband(vals):
    """Band around 0: the largest difference between any two vLLM runs' published means on the same rows."""
    w = max(vals) - min(vals)
    return (-w, w)


def spec_strip(scored, panel, ref, metric, sel=None):
    s = scored; tpw = s["tokens_per_window"]
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
PANEL = {"pa": "P-A, BF16 teacher panel", "pb": "P-B, fidelity set, generated positions", "q2": "Q2, long human-written text"}
SEL = {"pa": "every position", "pb": "generated positions", "q2": "last 4,096 positions per window"}


def strip(T, run, key):
    ref, metric = REF[run][key]
    return spec_strip(T[key]["scored"], PANEL[key], ref, metric, SEL[key])


def frow(label, est, lo, hi, band, title, sub=None, who="c", hollow=False, extra=""):
    return {"label": label, "sub": sub, "est": est, "lo": lo, "hi": hi, "band": band, "who": who, "hollow": hollow,
            "value": f"{sg(est)} {cit(lo, hi)}{extra}", "title": title}


def clusters_816(run, K=None):
    """Windows behind the P-B 8-16K bucket (the paired comparison's clusters)."""
    if run == "k4": return K["pb"]["paired"]["C-r1-Vmean"]["gen 8-16K"]["clusters"]
    return B.load(D / "q/pb/pb-pair-V1-C1.json")["gen"]["by_bucket"]["8-16K"]["clusters"]


def k325_runs():
    q = D / "q"
    pa = {a: B.load(q / ("pa-v2" if a == "V2" else "pa") / f"pa-{a}.json")["overall"]["kl"]["value"] for a in ("V1", "V1r", "V2")}
    pb = {}
    for a in ("V1", "V1r", "V2"):
        g = B.load(q / "pb" / f"pb-{a}.json")["summary"]["gen"]
        pb[a] = {"all": g["overall"]["kl"]["value"], **{b: g["by_bucket"][b]["kl"]["value"] for b in ("0-2K", "2-8K", "8-16K")}}
    q2 = B.load(q / "q2" / "q2-C1-vs-V1.json")["groups"]["overall"]
    return pa, pb, q2


# ------------------------------------------------------------------ home: does the precision difference matter (scale chart)

def fig_scale(P):
    """Horizontal bars, one panel per measure: KL from BF16 (lower is closer), on the panel's own axis from 0."""
    panels = [(t, rows) for t, rows in P["bars"]]
    svg = C.bars(panels, aria="Distance from the BF16 model by checkpoint, engine and setting, one panel per measure")
    return C.figure("does-it-matter-chart", "Distance from the BF16 model (lower is closer to BF16)",
                    "Each panel is one measure on one set of texts, with its own axis; compare bars within a panel.",
                    [(svg, None, None)],
                    "Grey is tpurtell's official FP8 model: the 3.25-bit quantization adds most of the distance; the blue-orange gap "
                    "is the engine difference.",
                    md(P["bars_table"]) + '<p class="sign">The official FP8 baseline is tpurtell\'s published value for his set, '
                    f'quoted in {gh(f"{RD}/q/RESULTS-Q.md", "<code>q/RESULTS-Q.md</code>")}. Top-20 KL (KL20) reads about 0.8 of '
                    'full-vocabulary KL on the same rows.</p>',
                    [("bv", "vLLM fork"), ("bc", "CuteAFD"), ("bcs", "CuteAFD with a setting"), ("br", "official FP8 model")])


def dl_glossary(items):
    return '<dl class="gl">' + "".join(f"<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>" for k, v in items) + "</dl>"


PAGE_LINKS = [("precision.html", "Precision", "closeness to BF16"), ("settings.html", "Settings", "every CuteAFD setting"),
              ("speed.html", "Speed", "every speed cell"), ("long-tasks.html", "Long tasks", "long replies, long prompts"),
              ("running.html", "Running it", "operator notes"), ("method.html", "Method", "protocols and timeline"),
              ("audit.html", "Audit", "the K3.25 review"), ("research.html", "Research", "deep dives"),
              ("reproduce.html", "Reproduce", "every step")]


def page_home():
    P = B.home_parts(site=True)
    body = (h2("findings", "Findings") + md(P["findings"]) +
            h2("does-it-matter", "Does the precision difference matter?") + fig_scale(P) + md(P["matters"]) +
            h2("pick-by-workload", "Pick by workload") +
            '<p class="sign">What the results show on this machine and these checkpoints; not a general ranking.</p>' + md(P["pick"]) +
            h2("settings-measured", "Settings measured") + md(P["settings"]) +
            h2("speed-in-numbers", "Speed in numbers") + md(P["speed"]) + f'<p class="sign">{inline(P["speed_note"], "")}</p>' +
            h2("how-sure", "How sure are we") + md(P["sure"]) +
            h2("terms", "Terms") + dl_glossary(P["glossary"]) +
            h2("pages", "Pages") + '<p class="pages">' +
            " · ".join(f'<a href="{p}">{t}</a> ({E(s)})' for p, t, s in PAGE_LINKS) + "</p>")
    page("index.html", "CuteAFD and tpurtell's vLLM fork on two RTX PRO 6000s", md(P["intro"]), body, answer=False)


# ------------------------------------------------------------------ precision

def long_code_rows(F, K):
    """The P-B 8-16K difference from the vLLM fork, by setting, per checkpoint (canonical references)."""
    d, T = F["d"], F["T"]; _, pb_runs, _ = k325_runs()
    band3 = vband([pb_runs[a]["8-16K"] for a in pb_runs])
    r3 = [{"section": "K3.25 · coarse KL · against the mean of 3 vLLM runs"}]
    for arm, lab, env in (("C1", "As shipped", None), ("F1c", "W8A16 prefill", "F1c"),
                          ("F1d", "W8A16 + BF16 KDA and head", "F1d: all three FP8 switches off")):
        v = d[("8-16K", "kl", arm)]
        r3.append(frow(lab, v[0], v[1], v[2], band3, f"K3.25 {lab}: CuteAFD − vLLM {sg(v[0])} {cit(v[1], v[2])} coarse KL at 8-16K"
                       + (f" ({env})" if env else ""), sub=env))
    S = k4_settings(K)
    runs = [K["pb"]["per_arm"][a]["gen 8-16K"]["kl_pb20"]["value"] for a in ("V-r1", "V-r1b", "V-r2")]
    band4 = vband(runs)
    r4 = [{"section": "K4 · KL_pb20 (top-20) · against the mean of 2 vLLM launches"}]
    for a, lab, env, hol in (("shipped", "As shipped", None, False), ("f1c", "W8A16 prefill", "F1-K4", False),
                             ("amax", "amax scale rule", "F1-K4b", False), ("best", "best scale rule", "F1-K4b", False),
                             ("w16amax", "W8A16 + amax scale rule", "K4c", False), ("w16best", "W8A16 + best scale rule", "K4d", False),
                             ("head16", "BF16 output head", "F1-K4b; does not fit 2x RTX", True), ("kda16", "BF16 KDA projections", "F1-K4b; does not fit 2x RTX", True),
                             ("all16", "Every switch", "F1-K4b; does not fit 2x RTX", True)):
        v = S[a]["pb8_v"]
        r4.append(frow(lab, v[0], v[1], v[2], band4, f"K4 {lab}: CuteAFD − vLLM {sg(v[0])} {cit(v[1], v[2])} KL_pb20 at 8-16K"
                       + (f" ({env})" if env else ""), sub=env, hollow=hol))
    return r3, r4, band3, band4


def fig_long_code(F, K):
    r3, r4, b3, b4 = long_code_rows(F, K); T, T4 = F["T"], K["T"]
    kw = dict(ref="vLLM fork", ref_who="v", left="closer to BF16", right="further from BF16")
    s3 = C.forest(r3, aria="Long-code difference from the vLLM fork by CuteAFD setting, K3.25, coarse KL", **kw)
    s4 = C.forest(r4, aria="Long-code difference from the vLLM fork by CuteAFD setting, K4, KL_pb20", **kw)
    rows = [[E(sec), E(r["label"]) + (f'<br><span class="ci">{E(r["sub"])}</span>' if r.get("sub") else ""), sg(r["est"]), cit(r["lo"], r["hi"]),
             f'±{r["band"][1]:.4f}', "no" if r.get("hollow") else "yes"]
            for sec, rs in (("K3.25, coarse KL", r3), ("K4, KL_pb20", r4)) for r in rs if "section" not in r]
    table = htable(["Checkpoint and measure", "CuteAFD setting", "CuteAFD − vLLM fork", "95% interval", "vLLM run-to-run band",
                    "Serves on 2x RTX"], rows)
    sp = lambda TT, run, K_=None: spec_band("P-B 8-16K, long code reading", pb_band(TT, "8-16K")["positions"], clusters_816(run, K_),
                                            pb_band(TT, "8-16K")["context"], REF[run]["pb"][0], REF[run]["pb"][1])
    return C.figure("long-code", "Long code reading (8-16K prompts): CuteAFD's distance from BF16 minus the vLLM fork's (left is closer to BF16)",
                    "One row per CuteAFD setting, paired on the same scored positions; the two checkpoints use different measures, so each "
                    "has its own panel.",
                    [(s3, sp(T, "k325"), "K3.25"), (s4, sp(T4, "k4", K), "K4")],
                    "The blue line is the vLLM fork; a row whose interval is solid is resolved from it. Hollow triangles need more GPU "
                    "memory than two RTX PRO 6000s have with K4.",
                    table, LG_ENGINE + [("ch", "setting that does not fit a serving launch on 2x RTX")])


def pa_table(F, K):
    R = K["ref"]["pa"]; pa = K["pa"]; p = F["pa"]
    rows = [["K3.25", "full-vocabulary KL", kl(p["A"]), kl(p["B"]), f"{sg(p['B_minus_A'])} {cit(*p['ci95'])}", "differs"],
            ["K3.25", "KL20 (top-20)", kl(R["per_arm"]["V1"]["kl_e20"]), kl(R["per_arm"]["C1"]["kl_e20"]),
             f"{sg(R['C1_minus_V1']['kl_e20']['diff'])} {cit(*R['C1_minus_V1']['kl_e20']['ci95'])}", "differs"],
            ["K4", "KL20 (top-20)", kl(pa["per_arm"]["Vmean"]["kl_e20"]["value"]), kl(pa["per_arm"]["C-r1"]["kl_e20"]["value"]),
             f"{sg(pa['paired']['C-r1-Vmean']['kl_e20']['B_minus_A'])} {cit(*pa['paired']['C-r1-Vmean']['kl_e20']['ci95'])}",
             B.k4_reading(pa['paired']['C-r1-Vmean']['kl_e20']['B_minus_A'], pa['paired']['C-r1-Vmean']['kl_e20']['ci95'],
                          pa["floors"]["V-r2-V-r1"]["kl_e20"]["B_minus_A"])],
            ["K3.25", "top-1 agreement", f"{100 * R['per_arm']['V1']['top1']:.2f}%", f"{100 * R['per_arm']['C1']['top1']:.2f}%",
             f"{C.sg(100 * R['C1_minus_V1']['top1']['diff'], 2)} pts", ""],
            ["K4", "top-1 agreement", f"{100 * pa['per_arm']['Vmean']['top1']['value']:.2f}%", f"{100 * pa['per_arm']['C-r1']['top1']['value']:.2f}%",
             f"{C.sg(100 * pa['paired']['C-r1-Vmean']['top1']['B_minus_A'], 2)} pts {cit(*[100 * x for x in pa['paired']['C-r1-Vmean']['top1']['ci95']], nd=2)}",
             B.k4_reading(pa['paired']['C-r1-Vmean']['top1']['B_minus_A'], pa['paired']['C-r1-Vmean']['top1']['ci95'],
                          pa["floors"]["V-r2-V-r1"]["top1"]["B_minus_A"])]]
    return htable(["Checkpoint", "Measure", "vLLM fork (K3.25: run V1, which its other two runs match to 1e-6; K4: mean of 2 launches)",
                   "CuteAFD", "CuteAFD − vLLM fork [95%]", "Reading"], rows)


def pb_table(F, K):
    d, T = F["d"], F["T"]; _, pb_runs, _ = k325_runs()
    lab = {"all": "all generated positions", "0-2K": "0-2K", "2-8K": "2-8K", "8-16K": "8-16K (long code)"}
    rows = []
    for b in ("all", "0-2K", "2-8K", "8-16K"):
        v = d[(b, "kl", "C1")]; ctx = T["pb"]["scored"]["context"] if b == "all" else pb_band(T, b)["context"]
        band = vband([pb_runs[a][b] for a in pb_runs])
        rows.append(["K3.25 · coarse KL", lab[b], hist(ctx), kl(F["kl_v"][b]), kl(F["kl_c"][b]), f"{sg(v[0])} {cit(v[1], v[2])}",
                     f"±{band[1]:.4f}", "differs" if v[1] > 0 or v[2] < 0 else "not resolved"])
    T4 = K["T"]; band4 = {x["band"]: x for x in T4["pb"]["by_position"]}
    for g, l4, ctx in (("gen", "all generated positions", T4["pb"]["scored"]["context"]), ("gen 0-2K", "0-2K", band4["0-2K"]["context"]),
                       ("gen 2-8K", "2-8K", band4["2-8K"]["context"]), ("gen 8-16K", "8-16K (long code)", band4["8-16K"]["context"]),
                       ("gen block B", "block B (long code, the 8-16K windows)", K["histB"])):
        p = K["pb"]["paired"]["C-r1-Vmean"][g]["kl_pb20"]; fl = K["pb"]["floors"]["V-r2-V-r1"][g]["kl_pb20"]["B_minus_A"]
        runs = [K["pb"]["per_arm"][a][g]["kl_pb20"]["value"] for a in ("V-r1", "V-r1b", "V-r2")]
        rows.append(["K4 · KL_pb20 (top-20)", l4, hist(ctx), kl(p["A"]), kl(p["B"]), f"{sg(p['B_minus_A'])} {cit(*p['ci95'])}",
                     f"±{vband(runs)[1]:.4f}", B.k4_reading(p["B_minus_A"], p["ci95"], fl)])
    gen = lambda a: B.load(D / "q" / "pb" / f"pb-{a}.json")["summary"]["gen"]
    vr = [gen(a) for a in ("V1", "V1r", "V2")]; c1 = gen("C1")
    for b_, l3 in (("all", "all generated positions"), ("8-16K", "8-16K (long code)")):
        pick = (lambda g: g["overall"]["top1"]["value"]) if b_ == "all" else (lambda g: g["by_bucket"][b_]["top1"]["value"])
        v = d[(b_, "top1", "C1")]; ctx = T["pb"]["scored"]["context"] if b_ == "all" else pb_band(T, b_)["context"]
        rows.append(["K3.25 · top-1 agreement", l3, hist(ctx), f"{100 * st.mean(pick(g) for g in vr):.2f}%", f"{100 * pick(c1):.2f}%",
                     f"{C.sg(100 * v[0], 2)} pts {cit(100 * v[1], 100 * v[2], nd=2)}", "", "differs" if v[1] > 0 or v[2] < 0 else "not resolved"])
    for g, l4 in (("gen", "all generated positions"), ("gen 8-16K", "8-16K (long code)")):
        p = K["pb"]["paired"]["C-r1-Vmean"][g]["top1"]; fl = K["pb"]["floors"]["V-r2-V-r1"][g]["top1"]["B_minus_A"]
        ctx = T4["pb"]["scored"]["context"] if g == "gen" else band4["8-16K"]["context"]
        rows.append(["K4 · top-1 agreement", l4, hist(ctx), f"{100 * p['A']:.2f}%", f"{100 * p['B']:.2f}%",
                     f"{C.sg(100 * p['B_minus_A'], 2)} pts {cit(100 * p['ci95'][0], 100 * p['ci95'][1], nd=2)}", "",
                     B.k4_reading(p["B_minus_A"], p["ci95"], fl)])
    return htable(["Checkpoint and measure", "Positions", "History, tokens (min / median / max)", "vLLM fork (K3.25: mean of 3 runs; K4: of 2 launches)",
                   "CuteAFD", "CuteAFD − vLLM fork [95%]", "vLLM run-to-run band", "Reading"], rows)


def q2_table(K):
    q = B.load(D / "q/q2/q2-C1-vs-V1.json")["groups"]["overall"]; n = q["nll_paired"]; fl = q["noise_floor_B"]
    q4 = K["q2"]; v = q4["vs_vllm_mean"]["C-r1"]["dnll_x_minus_v_documents_t"]
    vm = st.mean(q4["per_arm"][a]["nll_mean_of_documents"] for a in ("V-r1", "V-r2"))
    f4l = q4["pairs"]["V-r1|V-r2"]["dnll_yx_documents_t"]["mean"]
    rows = [["K3.25 (against vLLM run V1, the run scored on all six documents)", f"{n['B']:.4f}", f"{n['A']:.4f}", f"{sg(-n['B_minus_A'])} {cit(-n['ci95'][1], -n['ci95'][0])} (bootstrap over documents)",
             f"{sg(fl['dnll_repeat']['B_minus_A'])} (vLLM repeat, {fl['clusters']} of 6 documents)", "not resolved"],
            ["K4 (against the mean of 2 vLLM launches)", f"{vm:.4f}", f"{q4['per_arm']['C-r1']['nll_mean_of_documents']:.4f}", f"{sg(v['mean'])} {cit(*v['ci95'])} (t-interval over documents)",
             f"{sg(f4l)} (launch 2 − launch 1, all 6 documents)", B.k4_reading(v["mean"], v["ci95"])]]
    return htable(["Checkpoint", "NLL, vLLM fork", "NLL, CuteAFD", "CuteAFD − vLLM fork [95%]", "vLLM run-to-run floor", "Reading"], rows)


def page_precision(F, K):
    N = B.canon(); pb8, k8 = N["pb8"], N["k4_pb8"]
    alt_v1 = B.load(D / "q/pb/pb-pair-V1-C1.json")["gen"]["by_bucket"]["8-16K"]["kl"]["B_minus_A"]
    alt_2 = F["f1"]["precision"]["C1"]["8-16K"]["vs_vllm_mean"]["kl"][0]
    alt_20 = K["ref"]["pb"]["C1_minus_Vmean3"]["gen 8-16K"]["kl_pb20"]["diff"]
    c0 = B.load(D / "q/pb/pb-pair-C0-C1.json")["gen"]["overall"]["kl"]
    lede = ("<p>Both engines stay close to the BF16 model, and the vLLM fork is slightly closer. The difference is largest when "
            f"reading long code (8-16K-token prompts): CuteAFD is {sg(pb8['d'])} further on K3.25 (coarse KL) and {sg(k8['d'])} on "
            "K4 (a top-20 measure). Below 8K on K3.25, and on long human-written text at 32K-128K on both checkpoints, no difference "
            "is resolved. K4 sits about half as far from BF16 as K3.25 on both engines.</p>")
    body = (fig_long_code(F, K) +
            '<p class="sign">"Reading" follows each run\'s declared rule: K3.25, the 95% interval excludes 0; K4, it also has to exceed the '
            'vLLM fork\'s launch-to-launch difference on the same rows. Band: the largest difference between any two vLLM runs\' means '
            'on the same rows. CuteAFD repeats are byte-identical, so CuteAFD needs no band.</p>' +
            h2("checkpoints", "Teacher panel (P-A): every position of 25 texts of 2,048 tokens") +
            '<p class="plain">brandonmusic\'s BF16 teacher logits, the full vocabulary. The K3.25 KL20 row is K3.25\'s own captures '
            'scored with K4\'s top-20 measure, so the two checkpoints can be compared on the same quantity.</p>' + pa_table(F, K) +
            h2("fidelity-set", "Fidelity set (P-B): the model's own replies, prompts up to 14.4K tokens") +
            '<p class="plain">tpurtell\'s cuteafd-fidelity set, generated positions only (his rule). K3.25 is scored with his coarse KL '
            '(top 1,024 tokens plus the rest), K4 with its top-20 truncation, which keeps 98-99% of the coarse value on these rows.</p>'
            + pb_table(F, K) +
            f'<p class="sign">The K3.25 8-16K figure ({sg(pb8["d"])}) is against the mean of all three vLLM runs. Against other '
            f'references it reads {sg(alt_v1)} (the first vLLM run alone), {sg(alt_2)} (the first two runs, the reference follow-up F1 '
            f'used) and {sg(alt_20)} (K4\'s top-20 measure); the audit also reports +0.0057 against the second run alone.</p>' +
            h2("long-text", "Long human-written text (Q2, 32K-128K tokens): no BF16 reference") +
            '<p class="plain">Six documents (three books, three source files) at 32K, 64K and 128K tokens; the last 4,096 positions '
            'of each. With no BF16 reference this compares how surprised each engine is by the text (NLL), not closeness to BF16. '
            'K3.25 had a vLLM repeat on 2 of the 6 documents; K4 ran two full vLLM launches on all six, so its noise floor covers '
            'every document.</p>' + q2_table(K) +
            f'<p class="sign">One code window, <code>q2-code-c2-064k</code>, dominates the code result on both checkpoints; on K4 the '
            f'vLLM fork differs from its own second launch there on 192 rows by more than 1 nat (<a href="research.html#c2">Research</a>). '
            f'Without that window K4 reads +0.0012 and −0.0008 against the two vLLM launches.</p>' +
            h2("notes", "Notes") + md(f"""- **Why the vLLM fork is averaged over runs.** Its prefill is not bit-reproducible beyond the first 2,045-token
  chunk, so one vLLM run is one draw; CuteAFD's repeats are byte-identical. CuteAFD is paired against the mean of three
  vLLM runs from two launches (K3.25) or two launches (K4).
- **Length or content.** The 8-16K bucket is block B of the set, long code reading; within block A, the only block at
  every length, the K3.25 KL difference is flat. Which of the two drives the difference is not separated.
- **Projection source inside CuteAFD (K3.25).** CuteAFD on Core-FP8 with the official FP8 projections (C1) against
  CuteAFD on K3.25-v1 with FP8 projections made at load (C0): C1 − C0 {sg(c0['B_minus_A'])} {cit(*c0['ci95'])}, not resolved.
- **Where the panel text came from.** P-B's replies were written greedily by an earlier CuteAFD release serving the
  official FP8 model; any bias from that favours CuteAFD, against the observed difference.
- **Top-20 measures.** KL20 reads about 0.8 of full-vocabulary KL on P-A; KL_pb20 keeps 98-99% of coarse KL on P-B
  generated positions; every K3.25 difference kept its sign and significance under the truncation.
- **Only the prefill path was scored.** Tokens generated during decode use another path; its precision was not measured.""")
            + '<p class="sign">Deeper: tails, position and the c2 document on <a href="research.html">Research</a>; the full write-ups: '
            + gh(f"{RD}/q/RESULTS-Q.md", "<code>RESULTS-Q.md</code>") + " (K3.25), " + gh(f"{R4}/README.md", "the K4 run README") +
            ", " + gh(f"{RD}/f1/RESULTS-F1.md", "<code>RESULTS-F1.md</code>") + ".</p>")
    page("precision.html", "Precision: how close to the BF16 model?", lede, body)


# ------------------------------------------------------------------ settings

F1_NAME = {"f1a": "BF16 KDA projections", "f1b": "BF16 output head", "f1c": "W8A16 prefill",
           "f1d": "W8A16 prefill + BF16 KDA projections + BF16 output head"}
F1_ENV = {"f1a": "GLM5_FLASH_KDA_FP8=off", "f1b": "GLM5_FLASH_FP8_HEAD=off", "f1c": "GLM5_FLASH_FP8_PREFILL=off",
          "f1d": "GLM5_FLASH_KDA_FP8=off GLM5_FLASH_FP8_HEAD=off GLM5_FLASH_FP8_PREFILL=off"}
K4ARMS = [  # (key, label, config lines, follow-up, fits)
    ("f1c", "W8A16 prefill", "GLM5_FLASH_FP8_PREFILL=off", "F1-K4", True),
    ("amax", "amax scale rule", "FP8_SCALES=amax", "F1-K4b", True),
    ("best", "best scale rule", "FP8_SCALES=best", "F1-K4b", True),
    ("w16amax", "W8A16 prefill + amax scale rule", "GLM5_FLASH_FP8_PREFILL=off FP8_SCALES=amax", "K4c", True),
    ("w16best", "W8A16 prefill + best scale rule", "GLM5_FLASH_FP8_PREFILL=off FP8_SCALES=best", "K4d", True),
    ("head16", "BF16 output head", "GLM5_FLASH_FP8_HEAD=off", "F1-K4b", False),
    ("kda16", "BF16 KDA projections", "GLM5_FLASH_KDA_FP8=off", "F1-K4b", False),
    ("all16", "Every switch (best scale rule, BF16 KDA and head, W8A16 prefill)", "FP8_SCALES=best GLM5_FLASH_KDA_FP8=off GLM5_FLASH_FP8_HEAD=off GLM5_FLASH_FP8_PREFILL=off", "F1-K4b", False)]


def cfg(lines): return "<br>".join(f"<code>{E(x)}</code>" for x in lines.split())


def settings_table(F, K):
    P = F["f1"]["precision"]; d = F["d"]; spd = f1_speed(); S = k4_settings(K); sp4 = k4_setting_speed()
    t = lambda v: f"{sg(v[0])} {cit(v[1], v[2])}"
    m3 = {"f1c": "F1c", "f1d": "F1d"}
    src = lambda x: f'<span class="ci">{x}</span>'
    rows = [["<b>K3.25</b>: as shipped", "", "yes", t(d[("8-16K", "kl", "C1")]), "", "not scored", "", "", src("Block Q")]]
    for a in ("f1a", "f1b", "f1c", "f1d"):
        if a in m3: after = t(d[("8-16K", "kl", m3[a])])
        else: after = (t(P[a]["8-16K"]["vs_vllm_mean"]["kl"]) + '<br><span class="ci">against the mean of the first two vLLM runs only '
                       f'(as shipped reads {sg(P["C1"]["8-16K"]["vs_vllm_mean"]["kl"][0])} there)</span>')
        s = spd[a]
        rows.append([F1_NAME[a], cfg(F1_ENV[a]), "yes", after, t(P[a]["8-16K"]["vs_C1"]["kl"]), "not scored",
                     f"{pct1(s[0])} ({pct1(s[1])} to {pct1(s[2])})", f"{rx(s[3])} median" + (f", worst cell {rx(s[4])}" if a == "f1d" else ""), src("F1")])
    sh = S["shipped"]
    rows.append(["<b>K4</b>: as shipped", cfg("MAX_CONTEXT_TOKENS=262144"), "yes", t(sh["pb8_v"]), "", t(sh["pa_v"]), "", "", src("Block Q")])
    for a, lab, env, fu, fits in K4ARMS:
        s = S[a]; sp = sp4.get(a)
        tt = (f"{pct1(sp[0])} ({pct1(sp[1])} to {pct1(sp[2])})" if sp else ("not measured (stored scale values only)" if fits else "not measured (does not fit)"))
        dec = (f"level ({sp[3]:.2f}-{sp[4]:.2f}x per cell)" if sp else "")
        rows.append([lab, cfg(env), "yes" if fits else "<b>no</b>", t(s["pb8_v"]), t(s["pb8_c"]) if s.get("pb8_c") else "",
                     t(s["pa_v"]) if s.get("pa_v") else "", tt, dec, src(fu)])
    v = S["nospec"]
    rows.append(["Control: drafter off (validation, not a setting)", cfg("SPECULATOR=off"), "scoring only", t(v["pb8_v"]), "0 (rows byte-identical)",
                 t(v["pa_v"]), "", "", src("F1-K4b")])
    return htable(["Setting", "Config lines (added to the serving config)", "Serves on 2x RTX?", "Long code (8-16K): CuteAFD − vLLM fork",
                   "Change against as shipped (paired)", "Teacher panel (P-A): CuteAFD − vLLM fork", "First token against as shipped",
                   "Decode against as shipped", "Source"], rows, cls="cfg")


def fig_map_k325(F):
    P = F["f1"]["precision"]; spd = f1_speed()
    lab = {"C1": "as shipped", "f1a": "BF16 KDA", "f1b": "BF16 head", "f1c": "W8A16 prefill", "f1d": "all three"}
    pts, tab = [], []
    for a in ("C1", "f1a", "f1b", "f1c", "f1d"):
        v = P[a]["8-16K"]["vs_vllm_mean"]["kl"]
        t = spd.get(a, (1.0, 1.0, 1.0, 1.0, 1.0))
        dec = f" · decode {rx(t[3])}" if a != "C1" else ""
        pts.append({"label": lab[a] + dec, "x": 100 * (t[0] - 1), "y": v[0], "lo": v[1], "hi": v[2], "shipped": a == "C1",
                    "title": f"{lab[a]}: first token {100 * (t[0] - 1):+.1f}% against as shipped, decode {rx(t[3])}; still {sg(v[0])} "
                             f"{cit(v[1], v[2])} KL from the vLLM fork at 8-16K"})
        tab.append([lab[a], pct1(t[0]) if a != "C1" else "0 (reference)", rx(t[3]) if a != "C1" else "1.00x (reference)", f"{sg(v[0])} {cit(v[1], v[2])}"])
    c1 = P["C1"]["8-16K"]["vs_vllm_mean"]["kl"][0]
    s = C.settings_map(pts, aria="Settings map K3.25: first-token cost against the remaining difference from the vLLM fork",
                       shipped_y=c1, xlabel="time to first token, % change against CuteAFD as shipped (median of 8 cells)",
                       ylabel="coarse KL difference from the vLLM fork (mean of its first two runs), P-B 8-16K")
    table = htable(["Setting", "First token against as shipped", "Decode against as shipped", "Remaining difference from the vLLM fork, 8-16K"], tab) + \
        ('<p class="sign">Here the vLLM reference is the mean of its first two runs, as follow-up F1 publishes it '
         f'({gh(f"{RD}/f1/F1-RESULTS.json", "<code>f1/F1-RESULTS.json</code>")}); the settings table above gives the three-run figures. '
         'Speed: each arm ÷ the F1 base launch over the 8 cells of the speed subset; no interval is published for the speed ratios.</p>')
    return C.figure("map-k325", "K3.25 settings map: first-token cost against the remaining long-code difference (lower is closer to the vLLM fork)",
                    "Each triangle is one CuteAFD setting: across, its first-token cost against as shipped; up and down, how far it still "
                    "is from the vLLM fork on long code reading, here against the mean of its first two runs (follow-up F1's reference).",
                    [(s, spec_band("P-B 8-16K, long code reading", pb_band(F["T"], "8-16K")["positions"], clusters_816("k325"),
                                   pb_band(F["T"], "8-16K")["context"], REF["k325"]["pb"][0], REF["k325"]["pb"][1]), None)],
                    "Points low and to the left close the most for the least first-token time; decode cost is in each label, because on "
                    "K3.25 it is not level for every switch.",
                    table, [("c", "CuteAFD setting (serves on 2x RTX)"), ("refdv", "vLLM fork (0)"), ("refdc", "CuteAFD as shipped"),
                            ("ci", "interval excludes 0"), ("ciu", "includes 0")])


def fig_map_k4(K):
    S = k4_settings(K); spd = k4_setting_speed()
    lab = {"shipped": "as shipped", "f1c": "W8A16", "amax": "amax rule", "best": "best rule", "w16amax": "W8A16 + amax rule",
           "w16best": "W8A16 + best rule", "head16": "BF16 head", "kda16": "BF16 KDA", "all16": "every switch"}
    fits = {a: f for a, _, _, _, f in K4ARMS}
    pts, tab = [], []
    for a in ("shipped", "f1c", "w16amax", "w16best", "amax", "best", "head16", "kda16", "all16"):
        v = S[a]["pb8_v"]; x = 0.0 if a == "shipped" else (100 * (spd[a][0] - 1) if a in spd else None)
        hol = not fits.get(a, True)
        pts.append({"label": lab[a], "x": x, "y": v[0], "lo": v[1], "hi": v[2], "hollow": hol, "shipped": a == "shipped",
                    "title": f"{lab[a]}: " + (f"first token {x:+.1f}% against as shipped; " if x is not None else "speed not measured; ")
                             + f"still {sg(v[0])} {cit(v[1], v[2])} KL_pb20 from the vLLM fork at 8-16K" + ("; does not fit 2x RTX" if hol else "")})
        sp = spd.get(a)
        tab.append([lab[a], "0 (reference)" if a == "shipped" else (f"{pct1(sp[0])} ({pct1(sp[1])} to {pct1(sp[2])})" if sp else "not measured"),
                    "1.00x (reference)" if a == "shipped" else (f"{sp[3]:.2f}-{sp[4]:.2f}x per cell" if sp else "not measured"),
                    f"{sg(v[0])} {cit(v[1], v[2])}", "no" if hol else "yes"])
    s = C.settings_map(pts, aria="Settings map K4: first-token cost against the remaining difference from the vLLM fork",
                       shipped_y=S["shipped"]["pb8_v"][0], xlabel="time to first token, % change against CuteAFD as shipped (median of 8 cells)",
                       ylabel="KL_pb20 difference from the vLLM fork, P-B 8-16K (long code)", gutter="speed not measured")
    table = htable(["Setting", "First token against as shipped (range over cells)", "Decode against as shipped", "Remaining difference from the vLLM fork, 8-16K",
                    "Serves on 2x RTX"], tab) + \
        ('<p class="sign">Speed: per content cell (1K and 32K prompts, 1 and 4 streams, code and prose; 8 requests each), the median per '
         'request divided by the mean of the as-shipped launches run before and after the setting. Decode stayed inside the '
         'base-to-base band for every measured setting. No interval is published for the speed ratios.</p>')
    return C.figure("map-k4", "K4 settings map: first-token cost against the remaining long-code difference (lower is closer to the vLLM fork)",
                    "The same map for K4: filled triangles serve on two RTX PRO 6000s, hollow ones need more GPU memory; scale rules and "
                    "settings that do not fit have no measured speed and sit in the right-hand column.",
                    [(s, spec_band("P-B 8-16K, long code reading", pb_band(K["T"], "8-16K")["positions"], clusters_816("k4", K),
                                   pb_band(K["T"], "8-16K")["context"], REF["k4"]["pb"][0], REF["k4"]["pb"][1]), None)],
                    "On two RTX GPUs, read the filled triangles: the lowest is the closest-to-vLLM setting that serves, and its position "
                    "across is its first-token cost.",
                    table, [("c", "serves on 2x RTX"), ("ch", "does not fit 2x RTX"), ("gut", "speed not measured"), ("refdv", "vLLM fork (0)"),
                            ("refdc", "CuteAFD as shipped"), ("ci", "interval excludes 0"), ("ciu", "includes 0")])


def k4e_section(K):
    E4 = B.k4e_data()
    if not E4:
        return ('<p class="slot" id="k4e"><b>K4e</b> (W8A16 prefill + amax scale rule on K4 under the full speed grid and long '
                'output): running on 2026-10-28; results will be added.</p>')
    T = E4["T"]
    cw = B.t_request_cells(R4D / "f1k4" / "t" / "C-w16amax-r1.json")
    cc = B.t_request_cells(R4D / "t" / "C-r1.json"); cv = B.t_request_cells(R4D / "t" / "V-r1.json")
    b1 = B.t_request_cells(R4D / "f1k4" / "t" / "C-e-base1.json"); b2 = B.t_request_cells(R4D / "f1k4" / "t" / "C-e-base2.json")
    d1 = B.t_request_cells(R4D / "t" / "C-d1.json")
    band = max([0.08] + [abs(b2[k][0] / b1[k][0] - 1) for k in b1 if k in b2])     # FOLLOWUPS-K4e.md: max(8%, base-to-base)
    state = [b[k][0] / d1[k][0] for b in (b1, b2) for k in b if k in d1]
    changed = any(abs(r - 1) > band for r in state)
    rows = []
    for k in sorted(cw):
        rows.append([f"{k[0] // 1024}K × {k[1]}, {k[2]}", f"{cv[k][0]:.1f}" if k in cv else "", f"{cc[k][0]:.1f}" if k in cc else "", f"{cw[k][0]:.1f}",
                     f"{cv[k][1]:.2f}" if k in cv else "", f"{cc[k][1]:.2f}" if k in cc else "", f"{cw[k][1]:.2f}"])
    tt = htable(["Cell (prompt × streams, content)", "Decode tok/s: vLLM fork", "CuteAFD as shipped", "W8A16 + amax",
                 "First token s: vLLM fork", "CuteAFD as shipped", "W8A16 + amax"], rows)
    lrows = []
    A = E4["analysis"]; L4 = B.k4_l_summaries()
    for s_ in ("L1", "L2", "L3", "L3s"):
        reqs = [r for stg in E4["L"][s_]["stages"] for r in stg["requests"]]
        for c in ("prose", "code", "reasoning", "json"):
            rr = [r for r in reqs if r["content"] == c]
            if not rr: continue
            stop = sum(r["finish_reason"] == "stop" for r in rr); cap = sum(bool(r.get("hit_cap")) for r in rr)
            chk = B.l_check(A[("C-w16amax-r1", s_, c)]) if A and ("C-w16amax-r1", s_, c) in A else "analysis pending"
            v, u = L4.get(("V", s_, c)), L4.get(("C", s_, c))
            ref = lambda x: f"{x['stop']} / {x['cap']}, {x['completion_tokens_median']:,.0f}, {B.l_check(x)}" if x else ""
            lrows.append([s_, c, str(len(rr)), ref(v), ref(u), f"{stop} / {cap}, {st.median(r['completion_tokens'] for r in rr):,.0f}, {chk}",
                          f"{st.median(r['decode_tok_s'] for r in rr):.1f}"])
    lt = htable(["Stage", "Content", "Requests", "vLLM fork: finished / at cap, median tokens, check", "CuteAFD as shipped: the same",
                 "W8A16 + amax: the same", "W8A16 + amax: median decode tok/s"], lrows)
    note = (f"<b>Machine state changed</b> between this session and the main run (an as-shipped drift cell moved by more than the "
            f"±{100 * band:.0f}% band), so read only the within-session comparison." if changed else
            f"The as-shipped drift subsets before and after stayed within the ±{100 * band:.0f}% band of the main run's drift cells, so "
            "the columns compare directly.")
    return (h2("k4e", "W8A16 prefill + amax scale rule as a deployment (follow-up K4e)") +
            f'<p class="plain">CuteAFD with W8A16 prefill and the amax scale rule on K4, through the full speed grid and the four long-output '
            f'stages (declared before any request: {gh(f"{R4}/f1k4/FOLLOWUPS-K4e.md", "<code>FOLLOWUPS-K4e.md</code>")}). {note} Per cell: the '
            'median over every measured request. Descriptive: one run; read speed against the K4 noise band.</p>' + tt + lt)


def page_settings(F, K):
    N = B.canon(); pb8, k8 = N["pb8"], N["k4_pb8"]; sp3 = N["sp_f1"]; sp4 = N["sp4"]
    lede = (f"<p>CuteAFD has switches that trade a little speed, or GPU memory, for precision. On K3.25, W8A16 prefill closes about "
            f"{100 * pb8['share_w16']:.0f}% of the long-code difference from the vLLM fork for about {100 * (sp3['f1c'][0] - 1):.0f}% longer "
            f"time to first token; with all three switches no difference is resolved, at about {100 * (1 - sp3['f1d'][3]):.0f}% slower decode. "
            f"On K4 on two RTX PRO 6000s, W8A16 prefill with the amax scale rule closes about two thirds for about "
            f"{100 * (sp4['w16amax'][0] - 1):.0f}% longer first token, with decode level; the BF16 options do not fit there. Every setting "
            "here was measured in a follow-up outside the frozen protocols.</p>")
    body = (h2("all-settings", "Every setting tested") +
            '<p class="sign">Long code: P-B 8-16K, CuteAFD − vLLM fork (K3.25 coarse KL; K4 KL_pb20, top-20), 95% interval. Change against as '
            'shipped: the same positions, CuteAFD against itself (bit-deterministic, so no band). First token and decode: against an '
            'as-shipped launch measured beside it. Settings marked "no" do not fit a serving launch on two RTX PRO 6000s with K4; their '
            'precision comes from scoring launches.</p>' + settings_table(F, K) +
            '<p class="sign">The share of the difference a setting closes is (as shipped − setting) ÷ as shipped against the vLLM fork: '
            f'K3.25 W8A16 {100 * pb8["share_w16"]:.0f}%; K4 W8A16 {100 * k8["share_w16"]:.0f}%, W8A16 + amax {100 * k8["share_w16amax"]:.0f}% '
            f'(about two thirds), W8A16 + best {100 * k8["share_w16best"]:.0f}%. Sources: {gh(f"{RD}/f1/RESULTS-F1.md", "<code>RESULTS-F1.md</code>")}, '
            f'{gh(f"{R4}/f1k4/RESULTS-F1K4.md", "<code>RESULTS-F1K4.md</code>")}, {gh(f"{R4}/f1k4/RESULTS-F1K4b.md", "<code>RESULTS-F1K4b.md</code>")} '
            '(K4b, K4c, K4d) and their summary JSON.</p>' +
            h2("settings-map", "Settings map") + fig_map_k325(F) + fig_map_k4(K) + k4e_section(K))
    page("settings.html", "Settings: what each CuteAFD setting buys", lede, body)


# ------------------------------------------------------------------ speed

UNIT = {"dec": "tok/s per stream", "agg": "tok/s", "ttft": "s"}
CN = {"json": "JSON"}
SPEED = {"dec": ("Decode speed per stream", "slower", "faster"), "agg": ("Aggregate throughput", "fewer tokens/s", "more tokens/s"),
         "ttft": ("Time to first token", "sooner", "later")}


def speed_row(label, cells, m, band, run, sub=None):
    """One forest row: a small mark per content cell, a larger mark at the median over them."""
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


def fig_speed(run, m, cells, fid, band):
    G = speed_groups(cells); rows, tab = [], []
    for L in sorted({g[0] for g in G}):
        rows.append({"section": f"{L // 1024}K prompt"})
        for (LL, lv), cs in G.items():
            if LL != L: continue
            r, _ = speed_row(f"{lv} stream{'s' if lv > 1 else ''}", cs, m, band, run)
            rows.append(r)
            for (L_, content, lv_), c in cs:
                v, cu = c[m]; rr = c["ratio"][m] if run == "k4" and m in ("dec", "agg") else cu / v
                tab.append([f"{L_ // 1024}K", CN.get(content, content), str(lv_), f"{v:.2f}", f"{cu:.2f}", f"{rr:.2f}x",
                            (c["read"][m] if run == "k4" and m in ("dec", "agg") else
                             ("for scale only" if m == "ttft" else ("level" if band[0] <= rr <= band[1] else "outside the band")))])
    name, left, right = SPEED[m]
    s = C.forest(rows, ref="vLLM fork", ref_who="v", scale="log", left=left, right=right,
                 aria=f"{name}, CuteAFD ÷ vLLM fork, per cell, {run}", label_w=120, value_w=150)
    ck = "K3.25" if run == "k325" else "K4"
    good = {"dec": "right is faster on CuteAFD", "agg": "right is more tokens per second on CuteAFD", "ttft": "left is sooner on CuteAFD"}[m]
    what = {"dec": "Per-stream generation speed, CuteAFD ÷ vLLM fork, per prompt length and number of streams; small triangles are content "
                   "types, the large one their median.",
            "agg": "All generated tokens of a batch per second of wall time, CuteAFD ÷ vLLM fork; small triangles are content types.",
            "ttft": "Time from sending a request to its first token, CuteAFD ÷ vLLM fork; small triangles are content types."}[m]
    table = htable(["Prompt", "Content", "Streams", f"vLLM fork, {UNIT[m]}", f"CuteAFD, {UNIT[m]}", "CuteAFD ÷ vLLM fork", "Reading"], tab)
    lg = ([("dotc", "content type, outside the band"), ("dotcu", "content type, inside the band"), ("c", "median of the content types"),
           ("refv", "vLLM fork (1.0)"), ("band", "noise band")] if m != "ttft" else
          [("dotc", "content type"), ("c", "median of the content types"), ("refv", "vLLM fork (1.0)"), ("band", "noise band, for scale")])
    return C.figure(fid, f"{ck}: {name.lower()}, CuteAFD ÷ vLLM fork ({good})", what, [(s, None, None)],
                    "Find the row for your prompt length and number of requests at once; the grey band is the noise band stated above.",
                    table, lg)


def abs_table(cells, run):
    rows = []
    for (L, lv), cs in speed_groups(cells).items():
        dv = [c["dec"][0] for _, c in cs]; dc = [c["dec"][1] for _, c in cs]
        av = [c["agg"][0] for _, c in cs]; ac = [c["agg"][1] for _, c in cs]
        tv = st.median(c["ttft"][0] for _, c in cs); tc = st.median(c["ttft"][1] for _, c in cs)
        r = lambda xs: f"{min(xs):.0f}-{max(xs):.0f}" if f"{min(xs):.0f}" != f"{max(xs):.0f}" else f"{min(xs):.0f}"
        rows.append([f"{L // 1024}K × {lv}", r(dv), r(dc), r(av), r(ac), B.secs(tv), B.secs(tc)])
    return htable(["Prompt × streams", "Decode per stream, tok/s: vLLM fork", "CuteAFD", "Aggregate, tok/s: vLLM fork", "CuteAFD",
                   "First token: vLLM fork", "CuteAFD"], rows)


def page_speed(F, K):
    N = B.canon(); a3, a4 = N["k325"], N["k4"]; c3, c4 = N["c3"], N["c4"]
    t8 = N["k325"]["ttft_1k8"]
    lede = (f"<p>One request at a time, CuteAFD generates faster: {B.tok_rng(a3['dec1'][0])} tokens/s on the vLLM fork and "
            f"{B.tok_rng(a3['dec1'][1])} on CuteAFD (K3.25; K4 {B.tok_rng(a4['dec1'][0])} and {B.tok_rng(a4['dec1'][1])}). A single long "
            f"prompt gets its first token sooner on CuteAFD ({B.secs(a3['ttft'][131072][0])} and {B.secs(a3['ttft'][131072][1])} at 128K), "
            f"a single short one sooner on the vLLM fork ({B.secs(a3['ttft'][1024][0])} and {B.secs(a3['ttft'][1024][1])} at 1K). With "
            "several requests at once the vLLM fork's advantage is time to first token (1K × 8: "
            f"{B.secs(t8[0])} and {B.secs(t8[1])}); per-stream decode and aggregate throughput there are level or ahead on CuteAFD, "
            "except aggregate throughput at 1K × 8. The vLLM fork interleaves chunked prefill with decode, so every request starts "
            "early; CuteAFD's prefill is faster per request, but concurrent requests queue for it.</p>")
    t3 = B.t_counts(); t4 = B.k4_t_counts(K)
    body = (h2("how-to-read", "How to read this page") +
            '<p class="plain">A <b>cell</b> is one prompt length (1K to 128K tokens), one content type (prose, code, reasoning, JSON) and one '
            'number of <b>streams</b> (requests in flight at once), measured 3 times; each request generates 1,024 tokens with thinking on, '
            'every prompt is unique and every request has its own seed. <b>Decode</b> is the per-stream generation speed, '
            '<b>aggregate</b> all generated tokens of a batch per second of wall time, <b>first token</b> the time from sending to the '
            'first generated token. With thinking on, the code and JSON cells measure reasoning text about a code or JSON prompt.</p>'
            f'<p class="note">{E(B.NOISE_K325)}<br>{E(B.NOISE_K4)}</p>' +
            h2("k325", "K3.25 (2026-10-26/27)") + abs_table(c3, "k325") +
            f'<p class="sign">{inline(t3, RD)} Ranges run over the content types; first token is the median over them. Full grid: '
            f'{gh(f"{RD}/t/T-SUMMARY.md", "<code>t/T-SUMMARY.md</code>")}.</p>' +
            fig_speed("k325", "dec", c3, "dec-k325", (0.9, 1.1)) + fig_speed("k325", "ttft", c3, "ttft-k325", (0.9, 1.1)) +
            fig_speed("k325", "agg", c3, "agg-k325", (0.9, 1.1)) +
            h2("k4", "K4 (2026-10-27)") +
            '<p class="plain">The K4 grid is smaller: 1 and 4 streams at 1K-32K and 1 stream at 128K, set once for every arm of its frozen '
            '<a href="method.html#k4-protocol">protocol</a>. Readings per cell use the declared band.</p>' + abs_table(c4, "k4") +
            f'<p class="sign">{inline(t4, R4)}</p>' +
            fig_speed("k4", "dec", c4, "dec-k4", (0.92, 1.08)) + fig_speed("k4", "ttft", c4, "ttft-k4", (0.92, 1.08)) +
            fig_speed("k4", "agg", c4, "agg-k4", (0.92, 1.08)) +
            h2("caveats", "Caveats") + md("""- **Long prompts with several streams mostly measure scheduling.** The vLLM fork interleaves chunked prefill
  with decode, so its streams' decode overlaps other requests' prefill (a median 40-81% of each decode window) and their
  first tokens come early; CuteAFD finishes each prefill faster but queues the requests behind it. Streams that decode
  without another stream's prefill running decode at the same speed on both engines. At 32K and
  128K, 71-92% of a batch's wall time passes before its last first token, so the aggregate there mostly reflects
  CuteAFD's faster long prefill (about 4,400-4,500 against 3,700-3,900 tokens/s).
- **Draft policies differ.** The vLLM fork drafts 3 tokens per step with a BF16 drafter; CuteAFD drafts adaptively with
  an FP8 drafter. The vLLM fork accepted 1.53 of 3 drafted tokens per step; CuteAFD exposes no counter.
- **Inputs differ in two details.** Each request's first line is a nonce, different between the engines on K3.25 (prompt
  bodies identical); the 128K code prompts hold literal `<think>` text that the vLLM stack parses as control tokens.""")
            + f'<p class="sign">More: {gh(f"{RD}/t/CAVEATS.md", "<code>t/CAVEATS.md</code>")}, the drift check '
            f'{gh(f"{RD}/drift/RESULTS-DRIFT.md", "<code>drift/RESULTS-DRIFT.md</code>")}, the K4 per-cell readings '
            f'{gh(f"{R4}/t/t-compare.json", "<code>t/t-compare.json</code>")}.</p>')
    page("speed.html", "Speed: tokens per second and first-token time", lede, body)


# ------------------------------------------------------------------ long tasks

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
                          "value": f"{rx(r)}" + (" (both at cap)" if capped else f" ({mc:,.0f} vs {mv:,.0f})"),
                          "title": f"{st_} {name}: median reply CuteAFD {mc:,.0f} vs vLLM fork {mv:,.0f} tokens = {r:.2f}x"
                                   + ("; every reply on both engines reached the cap" if capped else "")})
            tab.append([st_, name, f"{v['n']}", f"{pv}/{v['n']}", f"{pc}/{u['n']}", f"{v['stop']} / {v['cap']}", f"{u['stop']} / {u['cap']}",
                        f"{mv:,.0f}", f"{mc:,.0f}", f"{r:.2f}x"])
    s1 = C.paired_share(rows, aria=f"Long-output checks passed, both engines, {run}")
    s2 = C.forest(lrows, ref="vLLM fork", ref_who="v", scale="log", left="CuteAFD shorter", right="longer",
                  aria=f"Median reply length, CuteAFD ÷ vLLM fork, {run}", label_w=120, value_w=170)
    ck = "K3.25" if run == "k325" else "K4"
    n_in = "8 requests in flight" if run == "k325" else "2 requests in flight"
    table = htable(["Stage", "Content", "n per engine", "vLLM: passed", "CuteAFD: passed", "vLLM: finished / at cap", "CuteAFD: finished / at cap",
                    "vLLM median tokens", "CuteAFD median tokens", "Length ratio"], tab) + \
        ('<p class="sign">Passed: code, every hidden test passes; reasoning, the correct MATH-500 answer; prose, the reply finished on its '
         'own; JSON, schema, count and ids valid. Descriptive: 4 prompts per content type, 2 seeds each (n = 8; 1 at L3s). No interval is '
         'published for these counts or for the length ratio. The code, JSON and prose tasks were sized for thinking off: at the '
         'first two caps, and for the 1,030-record JSON task at the last, the reasoning leaves too little room for the answer, so '
         'those cells measure finishing against the cap rather than task completion.</p>')
    return C.figure(fid, f"{ck}: long-output checks and reply length, both engines (more passing is better; descriptive, small n)",
                    f"Top: how many of the n replies passed their check, per stage and content type ({n_in}). Bottom: CuteAFD's "
                    "median reply length divided by the vLLM fork's.",
                    [(s1, None, "Passed, out of n"), (s2, None, "Median reply length, CuteAFD ÷ vLLM fork")],
                    "Read the long-cap rows (L3, L3s): where the two marks sit together the engines did the same; with n = 8, one or two "
                    "replies apart is not evidence of a difference.",
                    table, [("v", "vLLM fork"), ("c", "CuteAFD"), ("refv", "vLLM fork (length 1.0)")])


def needle_section():
    nd = B.needle_data()
    if not nd:
        return h2("needles", "Needles in very long prompts") + '<p class="plain">Not published.</p>'
    res = lambda s: ("found" if s["found"] else "not found") if "found" in s else f"{s['found_count']}/6" + (" in order" if s.get("in_order") else "")
    rows = [[r["id"], f"{r['usage']['prompt_tokens']:,}", B.secs(r["ttft_s"]), B.secs(u["ttft_s"]), res(r["score"]), res(u["score"])]
            for r, u in zip(nd["V"], nd["C"])]
    return (h2("needles", "Needles in very long prompts (exploratory)") +
            '<p class="plain"><b>Exploratory: one request per prompt and engine, not under a frozen protocol.</b> tpurtell\'s two needle '
            'designs from his vLLM fork, a secret code near the start and six records spread from 5% to 99% of the prompt, at 256K, 512K '
            'and 1M tokens, on both engines with K3.25. ' +
            ("Every reply finished on its own and found every needle on both engines." if nd["all_ok"] else "Not every needle was found.") +
            '</p>' + htable(["Prompt", "Prompt tokens", "First token: vLLM fork", "CuteAFD", "Result: vLLM fork", "CuteAFD"], rows) +
            f'<p class="sign">Receipts without reply text: {gh(f"results/{B.NEEDLE_RUN}", f"<code>results/{B.NEEDLE_RUN}</code>")}. '
            'It shows that both engines accept and answer 1M-token prompts; it does not rank them.</p>')


def page_long(F, K):
    N = B.canon(); L, L4 = N["L"], N["L4"]
    vc, cc = L[("V1", "L3", "code")], L[("C1", "L3", "code")]; vm, cm = L[("V1", "L3", "reasoning")], L[("C1", "L3", "reasoning")]
    vc4, cc4 = L4[("V", "L3", "code")], L4[("C", "L3", "code")]
    nd = N["needle"]
    c2v, c2c = L[("V1", "L2", "code")], L[("C1", "L2", "code")]; c2v4, c2c4 = L4[("V", "L2", "code")], L4[("C", "L2", "code")]
    lede = (f"<p>At the longest output cap the two engines did the same on code and math: code passed every hidden test in "
            f"{vc['all_pass']} of {vc['n']} replies on both with K3.25 and {vc4['all_pass']} of {vc4['n']} with K4, math {vm['correct']} of "
            f"{vm['n']}. At the 32K cap CuteAFD finished more code tasks ({c2v['stop']} of 8 on the vLLM fork against {c2c['stop']} on "
            f"CuteAFD with K3.25, {c2v4['stop']} against {c2c4['stop']} with K4), consistent with its shorter code replies "
            f"({cc['completion_tokens_median'] / vc['completion_tokens_median']:.2f}x and {cc4['completion_tokens_median'] / vc4['completion_tokens_median']:.2f}x "
            "the vLLM fork's median length at the last cap). Descriptive: n = 8 per content type and stage.</p>")
    body = (needle_section() +
            h2("long-output", "Long output: replies up to 128K tokens") +
            '<p class="plain">Four task types with machine checks: multi-file Python projects with hidden tests, MATH-500 level-5 problems, '
            '10,000-12,000-word essays, and product catalogues as JSON. Each stage raises the output cap; L3s repeats one prompt per type '
            'one request at a time. K3.25 ran 8 requests in flight with caps of 8K, 32K and 128K tokens; K4 ran 2 in flight with caps of '
            '8,192, 32,768 and 130,048, because K4\'s grid was common to its protocol\'s arms (<a href="method.html#k4-protocol">Method</a>). '
            f'Math replies were short on both: median {vm["completion_tokens_median"]:,.0f} (vLLM fork) and '
            f'{cm["completion_tokens_median"]:,.0f} (CuteAFD) tokens at the last cap on K3.25.</p>' +
            fig_long(L, "k325", "V1", "C1", "long-k325") + fig_long(L4, "k4", "V", "C", "long-k4") +
            f'<p class="sign">Per stage and content: {gh(f"{RD}/l/SUMMARY.md", "<code>l/SUMMARY.md</code>")} (K3.25), the Block L table in '
            f'{gh(f"{R4}/README.md", "the K4 run README")}.</p>')
    page("long-tasks.html", "Long tasks: long replies and very long prompts", lede, body)


# ------------------------------------------------------------------ running it

def chart_startup(S):
    runs = S["runs"]; W, l, r, bh = 640, 4, 70, 16
    tmax = max(x["ready_s"] for x in runs)
    H = 20 + len(runs) * (bh + 30) + 22
    X = lambda s: l + (W - l - r) * s / tmax
    o = [C.svg_open(W, H, "Startup to ready, by phase, per launch, K3.25")]
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
    return C.figure("startup-chart", "Startup to ready, per launch (K3.25; shorter is better)",
                    "Seconds from container start to ready for each launch, split into phases (one shade per phase, strongest first).",
                    [("".join(o), None, None)],
                    "The total at the right is the wait each time the model is switched.",
                    htable(["Launch", "Phase", "Time"], tab) + f'<p class="sign">{E(S.get("note", ""))}</p>',
                    [("v", "vLLM fork"), ("c", "CuteAFD")])


def page_running(F, K):
    N = B.canon(); su = N["startup"]
    R = sections(read("README.md"))
    obs = R.get("Running it: observations in detail", "")
    subs = sections(obs, 3)
    intro = obs.split("\n### ")[0].strip()
    ids = {"Capacity": "capacity", "Startup": "startup", "Prefix cache": "prefix-cache", "Thinking off and control tokens": "thinking-off",
           "Launcher defaults that matter": "launcher-defaults", "Determinism and drafting": "determinism",
           "Other engine observations": "other-observations"}
    body = (h2("launch-configs", "Launch configurations") +
            '<p class="plain">The configurations measured are on the home page as copyable blocks '
            '(<a href="index.html#settings-measured">Settings measured</a>); the exact files used are in '
            f'{gh("repro/cuteafd/configs")} (K3.25), {gh("repro/k4")} (K4) and described in <a href="reproduce.html">Reproduce</a>. '
            'Scoring launches for precision add CuteAFD\'s bench endpoint (<code>ENABLE_BENCH=on</code>, an API key file, '
            '<code>FULL_PREFILL_LOGITS=on</code>) or, on the vLLM fork, a prompt-logprob capture plugin; serving does not need them.</p>' +
            f'<p class="sign">{inline(intro, "")}</p>')
    for head, hid in ids.items():
        text = subs.get(head, "")
        body += h2(hid, head) + md(text, "")
        if head == "Startup" and startup(): body += chart_startup(startup())
    lede = (f"<p>CuteAFD is ready in {su['c']} s and the vLLM fork in {su['v_warm']} s once its JIT caches are kept between starts "
            f"({su['v_cold']} s without). On K4 the vLLM fork's KV cache holds {N['k4_kv'][0]:,} tokens and CuteAFD's {N['k4_kv'][1]:,}, "
            "and CuteAFD needs <code>MAX_CONTEXT_TOKENS=262144</code> to start there. CuteAFD reuses repeated prompts and honours "
            "\"thinking off\"; its launcher defaults to a 4,096-token output limit and listens on every interface unless told otherwise.</p>")
    page("running.html", "Running it: what an operator needs to know", lede, body)


# ------------------------------------------------------------------ method

def scored_table(T):
    pa, pb, q2 = T["pa"]["scored"], T["pb"]["scored"], T["q2"]["scored"]
    rows = [
        ["<b>P-A</b> BF16 teacher panel (brandonmusic)", f"{pa['windows']}", hist(pa["tokens_per_window"]),
         f"all {num(pa['scored_positions_per_window']['median'])} (rows 0-2046)", f"{pa['selected_positions_total']:,}", hist(pa["context"]),
         "the dataset's 25 qualification windows; general, legal, agentic code and reasoning domains",
         "<code>zai-org/GLM-5.3-Flash-BF16</code> @ <code>a6c167b6</code>, full-vocabulary FP32 logits"],
        ["<b>P-B</b> tpurtell's fidelity set (<code>cuteafd-fidelity</code>, glm5_flash v2)", f"{pb['windows']}", hist(pb["tokens_per_window"]),
         f"last 512; generated positions (primary) per window {hist(pb['selected_positions_per_window'])}",
         f"{pb['selected_positions_total']:,} generated", hist(pb["context"]),
         "replies written by the official FP8 model after conditioning and repository-source context; blocks A-E (B: long code reading)",
         "a BF16 run of <code>zai-org/GLM-5.3-Flash-BF16</code> @ <code>a5b45eb4</code>, stored as its top 1,024 ids plus a tail bin"],
        ["<b>Q2</b> long human-written text", f"{q2['windows']}", hist(q2["tokens_per_window"]),
         f"last {num(q2['scored_positions_per_window']['median'])}", f"{q2['selected_positions_total']:,}", hist(q2["context"]),
         "3 PG-19 books and 3 Apache-2.0 vLLM source files, each at 32K, 64K and 128K tokens", "none"]]
    return htable(["Panel", "Windows", "Tokens per window (min / median / max)", "Scored positions per window", "Total scored",
                   "History behind each scored token, tokens (min / median / max)", "Text", "Reference"], rows)


def page_method(F, K):
    R = sections(read("README.md"))
    _, secs = B.summary_sections(f"{RD}/")
    limits = secs.get("Limits", ("", ""))[1]
    tl = R.get("Timeline", "")
    p = lambda path, label: gh(path, f"<code>{E(label)}</code>")
    k325 = md("""- **Frozen.** Protocol v2 with amendments A1 and A2, frozen on 2026-10-26 at 17:32 (UTC−7), before any speed
  (Block T) or long-output (Block L) request.
- **Order as run.** CuteAFD's precision captures began at 16:32, before the freeze, as amendment A1 declares (the
  instruments were fixed and no vLLM result existed yet); then the vLLM fork's precision captures (17:47-18:40); then
  speed and long output on the vLLM fork first, CuteAFD second. The protocol had planned CuteAFD, the vLLM fork, then
  CuteAFD again as a drift check; the drift repeat that ran instead covers both engines and was declared after the
  audit, before any of its requests.
- **Follow-ups.** F1 (CuteAFD's FP8 switches), F2 (the vLLM fork's prefix cache) and F3 (a second vLLM launch for
  precision) were declared after the precision results were known; they are outside the frozen protocol and reported
  separately.
- **Review.** After the runs, a separate reviewer who did not run the measurements re-ran the scorers and checked the
  claims against the receipts (read-only, CPU only, 2026-10-27): the precision and speed blocks and the vLLM fork's long
  output. Its corrections are applied. It covers K3.25 only.""")
    k4 = md("""- **Frozen.** A second protocol, frozen on 2026-10-27 at 17:58:09 (UTC−7) after the startup and smoke checks and
  before any comparison request; generation 1, no amendments. Every driver refuses to send a request unless its own
  hash and the grid's match the freeze record.
- **Order as run.** vLLM launch 1, CuteAFD's scoring launch, vLLM launch 2 for precision (the two vLLM launches
  bracket CuteAFD in time); speed on the vLLM fork, then CuteAFD, then a final vLLM drift subset; long output on the
  vLLM fork, then CuteAFD.
- **Measures.** Precision was captured as each engine's top 20 tokens per position and scored with top-20 measures,
  identically on both arms.
- **Follow-ups.** F1-K4, F1-K4b, K4c and K4d (CuteAFD settings) were declared after the precision results, each
  before its own requests, outside the frozen protocol.
- **No separate review** of any part of the K4 run.""") + \
        '<p class="plain">The frozen K4 protocol also included a third engine, not reported here; its memory limits set the concurrency grid and the long-output cap.</p>'
    body = (h2("what-was-measured", "What was measured, in plain words") + md("""- **Precision (Block Q).** Each engine reads fixed texts token by token (teacher-forced), and its next-token
  probabilities are compared with the BF16 model's on the same positions: P-A, brandonmusic's BF16 teacher logits on 25
  texts of 2,048 tokens; P-B, tpurtell's fidelity set, 64 prompts up to 14.4K tokens scored on the model's own replies;
  Q2, six long human-written documents at 32K-128K tokens, where no BF16 reference exists and the engines are compared
  with each other.
- **Speed (Block T).** Prompts of 1K to 128K tokens in four content types, 1 to 16 requests at once (K4: 1 and 4),
  1,024 tokens generated per request, thinking on, 3 replicates per cell, a distinct seed and a unique first line per
  request.
- **Long output (Block L).** Replies up to 128K tokens with machine checks: hidden tests for code, the reference answer
  for math, a schema for JSON, the requested length for prose.
- **Arms.** Each engine as its author ships it, plus a short list of local settings (listen address, request logging,
  output limit, GPU memory utilization, a launcher guard); the same checkpoint bytes for the experts on both engines.""") +
            h2("k325-protocol", "K3.25: frozen protocol and order") + k325 +
            h2("k4-protocol", "K4: frozen protocol and order") + k4 +
            h2("versions", "Which vLLM fork") +
            '<p class="plain">"vLLM fork v0.9.2" is tpurtell\'s v0.9.2 release image (digest <code>ea0430aa…</code>) started with the v0.9.0 '
            'repository\'s <code>start.sh</code> through its <code>IMAGE</code> override (the launcher is otherwise unchanged); the K4 launches set <code>MODEL_PROFILE=k4</code> '
            'in the same launcher.</p>' +
            h2("files", "The protocol files") +
            '<ul class="pages">' +
            f'<li>{p("protocol/PROTOCOL.md", "protocol/PROTOCOL.md")}: the K3.25 protocol as frozen (its status lines were written before '
            'the freeze and left unchanged, so the file still matches its frozen hash)</li>'
            f'<li>{p("protocol/FROZEN.json", "protocol/FROZEN.json")}, {p("protocol/HASHES.json", "protocol/HASHES.json")}: the freeze record and '
            'which published copies are byte-identical to it</li>'
            f'<li>{p("protocol/FOLLOWUPS.md", "protocol/FOLLOWUPS.md")}: follow-ups F1-F3 and the drift check, as declared</li>'
            f'<li>{p(f"{R4}/METHOD.md", "METHOD.md")}: the K4 method, restated for the two published arms</li>'
            f'<li>{p(f"{R4}/f1k4", "f1k4/")}: the K4 follow-up declarations (<code>FOLLOWUPS-K4*.md</code>) and results</li></ul>' +
            h2("scored", "What was scored") + scored_table(F["T"]) +
            '<p class="sign">The K4 run scored the same panels and positions with top-20 measures. Teacher dataset identity and hashes: '
            + gh(f"{RD}/q/pa/PROVENANCE.json", "<code>q/pa/PROVENANCE.json</code>") + '.</p>' +
            h2("setup", "Setup") + md(R.get("Setup", "")) +
            h2("confounds", "Confounds") + md(R.get("Confounds", "")) +
            h2("limits", "Limits") + md(limits) +
            h2("timeline", "Timeline") + md(tl) +
            h2("status", "Status") + md(B.status_lines() + "\n" + B.k4_status()) +
            h2("other-runs", "Other runs") + md(R.get("Other runs", "")))
    lede = ("<p>Each engine ran as its author ships it, plus a short list of local settings, on one machine. For each checkpoint the "
            "comparison protocol was frozen before its comparison runs; settings experiments were declared as follow-ups before their own "
            "requests and are labelled outside the protocols. The K3.25 analysis had a separate review after the runs; the K4 run did not.</p>")
    page("method.html", "Method: what was frozen, what ran, in what order", lede, body)


# ------------------------------------------------------------------ audit (cited files become links)

CUTEAFD_SRC = "https://github.com/tpurtell/cuteafd/blob/v3.0.1/"
VLLM_FORK_SRC = "https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx/blob/v0.9.0/"
UPSTREAM = {"run-family.sh": CUTEAFD_SRC + "scripts/launch/run-family.sh", "docs/models/glm5_flash.md": CUTEAFD_SRC + "docs/models/glm5_flash.md",
            "fidelity.rs": CUTEAFD_SRC + "rust/crates/cuteafd-bench/src/fidelity.rs", "reference.rs": CUTEAFD_SRC + "rust/crates/cuteafd-bench/src/reference.rs",
            "probe.rs": CUTEAFD_SRC + "rust/crates/cuteafd-api/src/openai/probe.rs", "start.sh": VLLM_FORK_SRC + "start.sh",
            "chat_template.jinja": "https://huggingface.co/wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K3.25-v1/tree/0490d2f708b12145f6516555ab066aaeb401cd21",
            "windows.json": "https://huggingface.co/datasets/wrldsuksgo2mars/cuteafd-fidelity"}
RENAMED = {"PROTOCOL-DRAFT.md": "protocol/PROTOCOL.md", "FOLLOWUPS.md": "protocol/FOLLOWUPS.md", "FROZEN.json": "protocol/FROZEN.json",
           "RESULTS-Q.md": f"{RD}/q/RESULTS-Q.md", "T-SUMMARY.md": f"{RD}/t/T-SUMMARY.md"}
AUDITOR = {"pb1.py", "pb1.out", "pb3.py", "pb4.py", "ee.py", "ee2.py", "teachH.py", "ctx4.py", "l1.py", "t1.out", "t2.py", "bar.py"}
NOT_PUBLISHED_RAW = ("vllm-v092-dumps/", "capture-manifest.json", ".steps.jsonl", "local/logs/", "t/gpu-before-", "stage0/prompts/T/")
INTERNAL = ("discovery-", "phase1-indexer-selection.md", "contrib/local-inference-evals/", "recipes/")
FILEREF = re.compile(r"^(?P<path>[A-Za-z0-9_./{},*…+\-]+?\.(?:md|json|py|sh|log|txt|out|jsonl|rs|jinja))(?P<lines>:[0-9][0-9,\-]*)?$")


def repo_files():
    return [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts
            and "__pycache__" not in p.parts and not p.relative_to(ROOT).as_posix().startswith("docs/")]


_FILES = None


def resolve_ref(span):
    """A `file` citation in the audit -> (url or None, note or None)."""
    global _FILES
    m = FILEREF.match(span)
    if not m: return None, None
    path = m.group("path"); name = path.split("/")[-1]
    if name in AUDITOR: return None, "the auditor's recomputation, not published"
    if any(k in path for k in NOT_PUBLISHED_RAW): return None, "raw capture or local log, not published"
    if any(path.startswith(k) or k in path for k in INTERNAL): return None, "internal working file, not published"
    if path in RENAMED or name in RENAMED: return f"{REPO_URL}/blob/main/{RENAMED.get(path, RENAMED.get(name))}", None
    if path in UPSTREAM or name in UPSTREAM: return UPSTREAM.get(path, UPSTREAM.get(name)), None
    if _FILES is None: _FILES = repo_files()
    for cand in (path, f"{RD}/{path}", f"repro/{path}", f"repro/stage0/{path}"):
        if cand in _FILES: return f"{REPO_URL}/blob/main/{cand}", None
    hits = [f for f in _FILES if f.endswith("/" + path) and f.startswith(("results/2026-10-26", "repro/", "protocol/"))]
    if len(hits) == 1: return f"{REPO_URL}/blob/main/{hits[0]}", None
    return None, "not published"


def audit_codelink(span):
    if span.startswith("recipes/") and span.endswith("+v0.9.2/env.sh"):      # the K3.25 recipe; its K4 copy is published
        return (f'<a href="{REPO_URL}/blob/main/repro/k4/vllm/env.sh"><code>repro/k4/vllm/env.sh</code></a> '
                '<span class="ci">(cited as the K3.25 recipe, which is not published; the K4 copy carries the same settings)</span>')
    url, note = resolve_ref(span)
    if url:
        tgt = url.split("/blob/main/")[-1] if "/blob/main/" in url else None
        cited = FILEREF.match(span).group("path").split("/")[-1] if FILEREF.match(span) else span
        if tgt and tgt.split("/")[-1] != cited:                               # a renamed file: the label names the target
            return f'<a href="{E(url)}"><code>{E(tgt)}</code></a> <span class="ci">(cited as {E(span)})</span>'
        return f'<a href="{E(url)}"><code>{E(span)}</code></a>'
    if note: return f'<code>{E(span)}</code> <span class="ci">({E(note)})</span>'
    return None


AUDIT_TEXT = [   # the published audit as shown on the site: wording of the review itself, and internal references resolved
    ("This matches the earlier finding in\n  `contrib/local-inference-evals/LEDGER.md:768-800` (amendments 22ax-22az): identical solo prefills",
     "This matches an earlier investigation (local-inference-evals,\n  [`LEDGER.md`](https://github.com/UrbanAstroLA/local-inference-evals/blob/main/LEDGER.md)): identical solo prefills"),
    (" Selection and tie handling differ too (22az).", " Selection and tie handling differ too (same earlier investigation)."),
    (' The local change log summary "~0 below 8K" needs "in KL".', ' A summary reading "~0 below 8K" needs "in KL".'),
    ("`FROZEN.json` itself is `c4815666…`, as the local change log says.", "`FROZEN.json` itself is `c4815666…`."),
]


def page_audit():
    au = strip_title(read(f"{RD}/AUDIT-2026-10-27.md"))
    for old, new in AUDIT_TEXT:
        if old not in au: raise SystemExit(f"audit text changed; update AUDIT_TEXT: {old[:60]!r}")
        au = au.replace(old, new)
    lede = ("<p>A separate adversarial review of the K3.25 analysis, done after the runs by a reviewer who did not run the "
            "measurements: it re-ran the scorers and checked the claims against the receipts, read-only and on CPU only. It covered "
            "the precision and speed blocks and the vLLM fork's long output; it was made before CuteAFD's long output, the drift "
            "repeats and the follow-up results existed, and it does not cover K4 or the needle pilot. It found the instruments "
            "sound and the precision difference robust, traced the vLLM fork's run-to-run variation to multi-chunk prefill (which "
            "led to pairing CuteAFD against several vLLM runs), showed that the 8-16K bucket is long code reading, and confirmed "
            "the scheduling explanation of the speed results.</p>")
    body = ('<p class="sign">The review as published, with suggested follow-up work and local items omitted. Cited files link to '
            'this repository or to the engines\' public sources at the versions tested; files that are not published are marked. '
            'Line numbers refer to the files as reviewed; published copies with placeholders may differ by a few lines.</p>' +
            md(au, RD, 1, codelink=audit_codelink))
    page("audit.html", "Review of the K3.25 analysis (2026-10-27)", lede, body)


# ------------------------------------------------------------------ research (deep dives)

QM = (("kl_p50", 0.5), ("kl_p90", 0.1), ("kl_p99", 0.01), ("kl_p99.9", 0.001))
ARM = {"V1": "vLLM fork V1", "V1r": "vLLM fork V1r", "V2": "vLLM fork V2", "C1": "CuteAFD C1", "C0": "CuteAFD C0 (control)"}
ARM4 = {"Vr1": "vLLM launch 1", "Vr1b": "vLLM launch 1, repeat", "Vr2": "vLLM launch 2", "Cr1": "CuteAFD"}
TAILS = {"k325": {"pa": ({"V1": "kl_V1", "V1r": "kl_V1r", "V2": "kl_V2", "C1": "kl_C1"}, lambda r: True),
                  "pb": ({"V1": "kl_V1", "V1r": "kl_V1r", "V2": "kl_V2", "C1": "kl_C1"}, lambda r: r["role"] == "gen")},
         "k4": {"pa": ({"Vr1": "kl20_Vr1", "Vr2": "kl20_Vr2", "Cr1": "kl20_Cr1"}, lambda r: True),
                "pb": ({"Vr1": "klpb20_Vr1", "Vr2": "klpb20_Vr2", "Cr1": "klpb20_Cr1"}, lambda r: r["role"] == "gen")}}
NAMES = {"V1": "vLLM V1", "V1r": "vLLM V1r", "V2": "vLLM V2", "C1": "CuteAFD", "Vr1": "vLLM launch 1", "Vr1b": "vLLM launch 1 repeat",
         "Vr2": "vLLM launch 2", "Cr1": "CuteAFD"}


def rows_csv(path, select, cols):
    import csv
    with open(path, newline="") as f:
        out = {c: [] for c in cols}
        for r in csv.DictReader(f):
            if not select(r): continue
            for c in cols:
                if r[c] != "": out[c].append(float(r[c]))
    return {c: sorted(v) for c, v in out.items()}


def qmarks(s, name):
    return [(s[k], share, f"{name}: {100 * share:g}% of positions above KL {s[k]:.4g} ({k[3:]}, published)") for k, share in QM]


def tails_table(P, names):
    rows = []
    for a, s in P["arms"].items():
        rows.append([names[a], f"{s['kl_mean']:.4f}", f"{s['kl_p50']:.4f}", f"{s['kl_p90']:.3f}", f"{s['kl_p99']:.3f}",
                     f"{s['kl_p99.9']:.2f}", f"{s['kl_max']:.2f}", f"{100 * s['top1']:.2f}%",
                     f"{100 * s['confident_top1']:.2f}%" if "confident_top1" in s else "n/a"])
    return htable(["Run", "Mean", "p50", "p90", "p99", "p99.9", "Max", "Top-1", "Confident top-1"], rows)


def band_table(T, key):
    P = T[key]; rows = []
    for b in P["by_position"]:
        first = next(iter(b["arms"]))
        for a, s in b["arms"].items():
            rows.append([E(b["band"]) if a == first else "", hist(b["context"]) if a == first else "",
                         ARM[a], f"{s['kl_mean']:.4f}", f"{s['kl_p99']:.3f}", f"{s['kl_p99.9']:.2f}", f"{100 * s['top1']:.2f}%"])
    return htable(["Positions", "History, tokens (min / median / max)", "Run", "Mean KL", "p99", "p99.9", "Top-1"], rows)


def fig_tails(run, key, T, rows_dir, fid, metric, tables):
    cols, sel = TAILS[run][key]
    vals = rows_csv(rows_dir / ("pa-rows.csv" if key == "pa" else "pb-rows.csv"), sel, list(cols.values()))
    P = T[key]; arms = P["arms"]
    vs = [a for a in cols if a.startswith("V")]; ca = [a for a in cols if a.startswith("C")][0]
    unit = "runs" if run == "k325" else "launches"
    series = [{"name": NAMES[a], "who": "v", "values": vals[cols[a]], "thin": i > 0, "label": f"vLLM fork ({len(vs)} {unit})" if i == 0 else None,
               "marks": qmarks(arms[a], NAMES[a]) if i == 0 else []} for i, a in enumerate(vs)]
    series.append({"name": "CuteAFD", "who": "c", "values": vals[cols[ca]], "label": "CuteAFD", "marks": qmarks(arms[ca], "CuteAFD")})
    ex = C.exceedance(series, aria=f"Exceedance of per-position {metric}, panel {key.upper()}, {run}", xlabel=f"per-position {metric} (log scale)")
    bands = P["by_position"]
    cats = [(b["band"], f"history {num(b['context']['min'])}-{num(b['context']['max'])}") for b in bands]
    vmean_ = lambda b: sum(b["arms"][a]["kl_mean"] for a in vs) / len(vs)     # K3.25: three runs; K4: the two launches
    prof = C.profile(cats, [{"name": "vLLM", "who": "v", "values": [vmean_(b) for b in bands],
                             "titles": [f"vLLM fork (mean of {len(vs)} {unit}), {b['band']}, history {hist(b['context'])}: mean {metric} {vmean_(b):.4f}" for b in bands]},
                            {"name": "CuteAFD", "who": "c", "values": [b["arms"][ca]["kl_mean"] for b in bands],
                             "titles": [f"CuteAFD, {b['band']}, history {hist(b['context'])}: mean {metric} {b['arms'][ca]['kl_mean']:.4f}" for b in bands]}],
                     aria=f"Mean {metric} by history, panel {key.upper()}, {run}", ylabel=f"mean {metric} per position band (lower is closer)")
    v0 = vs[0]
    conc = C.concentration([(f"Top {p}% of positions", [("v", arms[v0][f"kl_share_top{p}pct"], f"{NAMES[v0]}: the top {p}% of positions carry "
                                                         f"{100 * arms[v0][f'kl_share_top{p}pct']:.1f}% of its total {metric}"),
                                                        ("c", arms[ca][f"kl_share_top{p}pct"], f"CuteAFD: the top {p}% of positions carry "
                                                         f"{100 * arms[ca][f'kl_share_top{p}pct']:.1f}% of its total {metric}")]) for p in (1, 5, 10)],
                           aria=f"Concentration of {metric} in the highest positions, panel {key.upper()}, {run}")
    title = {"pa": "P-A", "pb": "P-B"}[key]
    return C.figure(fid, f"{title} tails and position ({'K3.25' if run == 'k325' else 'K4, top-20'}): {metric}, lower is closer to BF16",
                    f"Three views of the same {P['scored']['selected_positions_total']:,} per-position scores: how often a position exceeds "
                    "a KL value, the mean by the history behind a position, and the share of the total carried by the highest positions.",
                    [(ex, strip(T, run, key), "Share of positions above a KL"), (prof, None, "Mean KL by history"),
                     (conc, None, "Concentration: share of the total KL in the top positions")],
                    "If the curves run together the engines differ in the bulk of positions, not in a few outliers.",
                    tables, [("lnv", "vLLM fork (each run; marks on the first)"), ("lnc", "CuteAFD"), ("v", "published quantile, vLLM"),
                             ("c", "published quantile, CuteAFD")])


def fig_q2_tails(run, T, rows_dir, fid, metric):
    P = T["q2"]
    if run == "k325":
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
                    "No BF16 reference exists beyond 14K tokens, so this compares the engines with each other (orange) and the vLLM fork with "
                    f"its own repeat (blue; it covers {w0['n']:,} of the {b0['n']:,} positions).",
                    [(ex, spec_strip(T["q2"]["scored"], PANEL["q2"], "none (engine against engine)", f"{metric} between two runs (disagreement), nats",
                                   SEL["q2"]), "Share of positions above a disagreement"), (conc, None, "Concentration of the disagreement")],
                    "The gap between the curves is the engine difference beyond run-to-run noise; it says nothing about which engine is closer "
                    "to BF16 at these lengths.",
                    table, [("lnv", "vLLM fork against its own repeat"), ("lnc", "CuteAFD against the vLLM fork"), ("v", "published quantile"), ("c", "published quantile")])


def page_research(F, K):
    T, T4 = F["T"], K["T"]; rows3, rows4 = D / "q" / "rows", R4D / "q" / "rows"
    pa_s, pb_s = T["pa"]["arms"], T["pb"]["arms"]; pab = T["pa"]["by_position"]
    pbv = [pb_s[a]["kl_p99"] for a in ("V1", "V1r", "V2")]
    c2 = strip_title(read(f"{R4}/c2/README.md"))
    lede = ("<p>Deeper views behind the headline numbers, for readers who want them: how the per-position differences are distributed, "
            "how they depend on the history behind a position, one document where the vLLM fork differs from itself, and the "
            "follow-up designs.</p>")
    body = (h2("tails", "Tails and position (K3.25)") +
            f'<p class="plain">Most positions sit far below the mean: the median position\'s KL on P-A is {pa_s["V1"]["kl_p50"]:.4f} (vLLM fork) '
            f'and {pa_s["C1"]["kl_p50"]:.4f} (CuteAFD) against means of {pa_s["V1"]["kl_mean"]:.4f} and {pa_s["C1"]["kl_mean"]:.4f}; the '
            f'highest-KL 5% of positions carry {100 * pa_s["V1"]["kl_share_top5pct"]:.0f}% and {100 * pa_s["C1"]["kl_share_top5pct"]:.0f}% of the '
            f'total. p99 on P-B generated positions: vLLM fork {min(pbv):.3f}-{max(pbv):.3f} over its three runs, CuteAFD {pb_s["C1"]["kl_p99"]:.3f}. '
            f'On P-A, positions with a short history carry more KL on both engines (history {num(pab[0]["context"]["min"])}-{num(pab[0]["context"]["max"])} '
            f'tokens: {vmean(pab[0]["arms"], "kl_mean"):.3f} and {pab[0]["arms"]["C1"]["kl_mean"]:.3f}; '
            f'{num(pab[-1]["context"]["min"])}-{num(pab[-1]["context"]["max"])} tokens: {vmean(pab[-1]["arms"], "kl_mean"):.3f} and '
            f'{pab[-1]["arms"]["C1"]["kl_mean"]:.3f}), so a panel\'s mean depends on which positions it scores.</p>' +
            fig_tails("k325", "pa", T, rows3, "tails-k325-pa", "KL", tails_table(T["pa"], ARM) + band_table(T, "pa")) +
            fig_tails("k325", "pb", T, rows3, "tails-k325-pb", "coarse KL", tails_table(T["pb"], ARM) + band_table(T, "pb")) +
            fig_q2_tails("k325", T, rows3, "tails-k325-q2", "KL") +
            h2("tails-k4", "Tails and position (K4, top-20 measures)") +
            fig_tails("k4", "pa", T4, rows4, "tails-k4-pa", "KL20", tails_table(T4["pa"], ARM4)) +
            fig_tails("k4", "pb", T4, rows4, "tails-k4-pb", "KL_pb20", tails_table(T4["pb"], ARM4)) +
            fig_q2_tails("k4", T4, rows4, "tails-k4-q2", "KL20n") +
            f'<p class="sign">Computed by {gh("tools/kl_tails.py", "<code>tools/kl_tails.py</code>")} from the per-position files in '
            f'{gh(f"{RD}/q/rows", "<code>q/rows/</code>")} (K3.25) and {gh(f"{R4}/q/rows", "<code>q/rows/</code>")} (K4); '
            '<code>python3 tools/kl_tails.py --check</code> reproduces them.</p>' +
            h2("buckets", "K3.25 by context bucket, with the follow-up F1 arms") + md(B.q_buckets()) +
            h2("k4-full", "K4 precision in full, and K4 against K3.25 on the same measure") + md(B.k4_precision_table(K)) +
            md(B.k4_q2_note(K), R4) + md(B.k4_quant_table(K)) +
            h2("mechanism", "Where the long-code difference may come from") + md("""- **CuteAFD's distributions are flatter at 8-16K** (K3.25): predictive entropy 0.580 against the vLLM fork's 0.523,
  higher in 18 of 18 windows (read from the full-vocabulary dumps by the audit). This is why its NLL difference is larger
  than its KL difference on this greedily generated text.
- **Candidates, not inferred:** the FP8 projections, head and KDA projections; the sparse-attention indexer's key format
  (CuteAFD BF16, the vLLM fork FP8); attention placement (CuteAFD splits each attention layer across both GPUs, the vLLM
  fork gives whole layers to one GPU); prefill geometry; the vLLM fork's BF16 logits. The settings follow-ups switch the
  ones CuteAFD exposes; on K4 what remains with every switch off sits in parts with no BF16 option.""") +
            h2("c2", "Q2 document c2 on K4: a window where the vLLM fork differs from itself") + md(c2, f"{R4}/c2", 1) +
            h2("follow-up-designs", "Follow-up designs") +
            '<ul class="pages">' + "".join(f"<li>{gh(path, f'<code>{E(lab)}</code>')}: {E(txt)}</li>" for path, lab, txt in (
                ("protocol/FOLLOWUPS.md", "FOLLOWUPS.md", "K3.25: F1 (FP8 switches), F2 (prefix cache), F3 (second vLLM launch), drift check"),
                (f"{R4}/f1k4/FOLLOWUPS-K4.md", "FOLLOWUPS-K4.md", "K4: W8A16 prefill"),
                (f"{R4}/f1k4/FOLLOWUPS-K4b.md", "FOLLOWUPS-K4b.md", "K4: the other FP8 switches, K4c (W8A16 + amax), K4d (W8A16 + best)"),
                (f"{RD}/f1/RESULTS-F1.md", "RESULTS-F1.md", "K3.25 F1 results in full"),
                (f"{R4}/f1k4/RESULTS-F1K4b.md", "RESULTS-F1K4b.md", "K4 settings results in full"))) + "</ul>")
    page("research.html", "Research: tails, position and other deep dives", lede, body)


# ------------------------------------------------------------------ reproduce

def repo_codelink(base):
    """`path` in REPRODUCE.md -> a link when it names a file or folder in this repository."""
    def f(span):
        s = span.split()[0] if span.split() else span
        if not re.match(r"^[A-Za-z0-9_.][A-Za-z0-9_./\-]*$", s) or "/" not in s and not s.endswith((".md", ".json", ".py", ".sh", ".log")): return None
        parts = []
        for seg in base.split("/") + s.rstrip("/").split("/"):
            if seg in ("", "."): continue
            if seg == "..":
                if parts: parts.pop()
            else: parts.append(seg)
        p = "/".join(parts)
        if s != span or not (ROOT / p).exists(): return None
        return f'<a href="{REPO_URL}/{"tree" if (ROOT / p).is_dir() else "blob"}/main/{p}"><code>{E(span)}</code></a>'
    return f


def page_reproduce(K):
    R = sections(read("README.md"))
    lede = ("<p>From the frozen protocol to the published summaries, step by step: checkpoints and images by digest, the prompt build "
            "(with hashes to confirm a rebuild), each engine's launch, the capture and scoring commands, and the checks.</p>")
    body = (md(strip_title(read("repro/REPRODUCE.md")), "repro", 1, codelink=repo_codelink("repro")) +
            h2("k4-launch", "K4 launch files") + md(strip_title(read("repro/k4/README.md")), "repro/k4", 1, codelink=repo_codelink("repro/k4")) +
            '<pre><code># vLLM fork, K4: the K3.25 steps above with the K4 recipe\n'
            'source &lt;this repo&gt;/repro/k4/vllm/env.sh &amp;&amp; cd &lt;vllm-stack&gt; &amp;&amp; ./start.sh\n'
            '# CuteAFD v3.0.1, K4: copy the configs into the checkout, then launch from its root\n'
            'cp &lt;this repo&gt;/repro/k4/cuteafd/*.config &lt;cuteafd&gt;/local/ &amp;&amp; cd &lt;cuteafd&gt;\n'
            './run.sh --config local/glm53-flash-exl3-k4-2rtx.config --restart          # serving\n'
            './run.sh --config local/glm53-flash-exl3-k4-2rtx-score.config --restart    # Block Q scoring\n'
            '# K4 tails from the published per-position files, from the root of this repository\n'
            'cd &lt;this repo&gt; &amp;&amp; python3 tools/kl_tails.py --run k4 --check</code></pre>')
    page("reproduce.html", "Reproduce", lede, body)


# ------------------------------------------------------------------ main

def main():
    DOCS.mkdir(exist_ok=True)
    for p in DOCS.glob("*.html"): p.unlink()
    F = facts(); K = B.k4_data()
    page_home(); page_precision(F, K); page_settings(F, K); page_speed(F, K); page_long(F, K); page_running(F, K)
    page_method(F, K); page_audit(); page_research(F, K); page_reproduce(K)
    for name, (target, label) in MOVED.items(): moved_page(name, target, label)
    print(f"wrote {len(PAGES)} pages and {len(MOVED)} forwarding stubs to docs/")


if __name__ == "__main__":
    main()
