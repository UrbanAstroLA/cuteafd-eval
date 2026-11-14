#!/usr/bin/env python3
"""Builds the site under next/docs from next/site. Standard library only.

  build.py            check every source, then write next/docs/*.html, findings.json and runs.json
  build.py --check    check only

Sources (next/site):
  runs/<run>.json          run index: goals and files (checked by check_runs.py)
  findings/<run>.json      findings: one measured quantity each, with evidence pointers into results/
  syntheses.json           judgements across findings, with basis and strength
  terms.md                 terms, one definition each
  pages/<page>.md          page text; directives on their own line:
                             {{finding ID}}  {{synthesis ID}}  {{table NAME}}  {{goals RUN}}  {{runs}}
  style.css                the site's stylesheet (inlined into every page; pages carry no scripts)

A finding is refused when a field is missing, a pointer does not resolve to the value stored beside it, or a decimal
number in its statement matches no evidence value at the precision shown.

Evidence kinds (each stores the value it read, and the build re-reads it):
  {"file": "x.json", "pointer": "/a/b", "value": ...}                   a JSON value (RFC 6901 pointer)
  {"file": "x.csv", "where": {"col": "v"}, "columns": [...], "value": {...}}  one CSV row (exactly one match); the
                                                                         named columns, as the strings in the file
  {"file": "x.md", "lines": [a, b], "text": "..."}                      lines a..b (1-based, inclusive) of a text file,
                                                                         exactly; numbers in it count as evidence
  {"file": "x"}                                                          a file cited without values

  build.py --only RUN[,RUN]   report problems for these runs' findings (and run index) only
  build.py --out DIR          write the pages to DIR (and README.md beside it) instead of next/docs
                              (a default build also copies next/docs to docs/preview/, the copy GitHub Pages serves)
"""
import csv
import io
import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SITE, OUT = REPO / "next" / "site", REPO / "next" / "docs"
sys.path.insert(0, str(HERE))
import check_runs  # noqa: E402
import tables      # noqa: E402

REPO_URL = "https://github.com/UrbanAstroLA/cuteafd-eval"
E = html.escape
NAV = [("index.html", "Answers"), ("precision.html", "Precision"), ("long-tasks.html", "Long tasks"),
       ("thinking.html", "Thinking length"), ("settings.html", "Settings"), ("checkpoints.html", "Checkpoints"),
       ("speed.html", "Speed"), ("running.html", "Running it"), ("tools.html", "Tool calling"),
       ("studies.html", "Studies"), ("method.html", "Method"), ("terms.html", "Terms")]
STUDY_PAGE = {"2026-11-10-context-probe": "v5.html", "2026-10-30-cuteafd-v4": "v4.html"}      # runs with a record page of their own; others: studies.html
FINDING_KEYS = ("id", "run", "goal", "question", "statement", "class", "status", "quantity", "sign", "unit", "n",
                "interval", "scope", "family", "replication", "evidence")
CLASSES = {"difference", "not detected", "descriptive", "source reading", "accounting"}
SCOPE_KEYS = ("engine", "checkpoint", "items", "context", "path", "hardware")
STRENGTH = {"established": 3, "supported": 2, "indicated": 1, "open": 0}
ROLES = {"supports", "limits", "contradicts", "context"}
NUM = re.compile(r"(?<![\w.])[−+-]?\d[\d,]*\.\d+")


# ------------------------------------------------------------------ data
def pointer(doc, ptr):
    for part in ptr.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


_cache = {}


def resolve(file, ptr):
    if file not in _cache:
        _cache[file] = json.loads((REPO / file).read_text())
    return pointer(_cache[file], ptr)


def read_csv_row(file, where, columns):
    rows = [r for r in csv.DictReader(io.StringIO((REPO / file).read_text()))
            if all(r.get(k) == v for k, v in where.items())]
    if len(rows) != 1:
        raise ValueError(f"{len(rows)} rows match {where}")
    return {c: rows[0][c] for c in columns}


def read_lines(file, lines):
    a, b = lines
    return "\n".join((REPO / file).read_text().splitlines()[a - 1:b])


def read_evidence(ev):
    """The value an evidence entry points at, re-read from the file; None for a file cited without values."""
    if "pointer" in ev:
        return resolve(ev["file"], ev["pointer"]), ev.get("value")
    if "where" in ev:
        return read_csv_row(ev["file"], ev["where"], ev.get("columns", [])), ev.get("value")
    if "lines" in ev:
        return read_lines(ev["file"], ev["lines"]), ev.get("text")
    if not (REPO / ev.get("file", "")).exists():
        raise FileNotFoundError(ev.get("file"))
    return None, None


def flat(v):
    if isinstance(v, (list, tuple)):
        for x in v:
            yield from flat(x)
    elif isinstance(v, dict):
        for x in v.values():
            yield from flat(x)
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        yield v
    elif isinstance(v, str):                       # numbers written in published prose fields
        for m in NUM.finditer(v):
            yield float(m.group(0).replace("−", "-").replace(",", ""))


def traces(text, values):
    """Decimal numbers in text that match no value at the precision shown."""
    bad = []
    for m in NUM.finditer(text):
        after = text[m.end():m.end() + 4]
        before = text[max(0, m.start() - 2):m.start() + 1]
        if after == "-bit" or after[:1] == "K" or re.match(r"\.\d", after) or re.match(r"[A-Za-z]-", before):
            continue                                    # format name, context label, version, model name (GLM-5.3)
        s = m.group(0).replace("−", "-").replace(",", "")
        nd = len(s.split(".")[1])
        x = float(s)
        tol = 10 ** -nd / 2 + 1e-9
        if not any(abs(v - x) <= tol or abs(abs(v) - abs(x)) <= tol or abs(100 * v - x) <= tol for v in values):
            bad.append(m.group(0))
    return bad


def load_findings():
    out, errs = {}, []
    for src in sorted((SITE / "findings").glob("*.json")):
        try:
            items = json.loads(src.read_text())
        except json.JSONDecodeError as e:
            errs.append(f"{src.name}: not valid JSON ({e})")
            continue
        for f in items:
            fid = f.get("id", "?")
            errs += [f"finding {fid}: missing {k}" for k in FINDING_KEYS if k not in f]
            errs += [f"finding {fid}: scope missing {k}" for k in SCOPE_KEYS if k not in f.get("scope", {})]
            if f.get("class") not in CLASSES:
                errs.append(f"finding {fid}: class {f.get('class')!r}")
            if f.get("class") == "not detected" and not f.get("bound"):
                errs.append(f"finding {fid}: 'not detected' needs a bound (largest effect not excluded)")
            vals = []
            if not f.get("evidence"):
                errs.append(f"finding {fid}: no evidence")
            for ev in f.get("evidence", []):
                where = ev.get("pointer") or ev.get("where") or ev.get("lines") or ""
                try:
                    got, stored = read_evidence(ev)
                except (KeyError, IndexError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as e:
                    errs.append(f"finding {fid}: {ev.get('file')} {where} does not resolve ({e!r})")
                    continue
                if got is None:
                    continue
                if stored is None:
                    errs.append(f"finding {fid}: {ev['file']} {where}: store the value read (value/text)")
                elif got != stored:
                    errs.append(f"finding {fid}: {ev['file']} {where} is {str(got)[:200]!r}, stored {str(stored)[:200]!r}")
                vals += list(flat(got))
            for k in ("statement", "bound"):
                bad = traces(str(f.get(k, "")), vals)
                if bad:
                    errs.append(f"finding {fid}: {k} numbers not in evidence: {bad}")
            if fid in out:
                errs.append(f"finding {fid}: duplicate id")
            out[fid] = f
    return out, errs


def load_syntheses(F):
    src = SITE / "syntheses.json"
    S, errs = {}, []
    for s in (json.loads(src.read_text()) if src.exists() else []):
        sid = s.get("id", "?")
        for k in ("id", "question", "judgement", "strength", "strength_basis", "scope", "basis", "does_not_show"):
            if k not in s:
                errs.append(f"synthesis {sid}: missing {k}")
        if s.get("strength") not in STRENGTH:
            errs.append(f"synthesis {sid}: strength {s.get('strength')!r}")
        vals = []
        named = [b.get("finding") for b in s.get("basis", [])]
        errs += [f"synthesis {sid}: {x} listed twice in its basis" for x in sorted({x for x in named if named.count(x) > 1})]
        for b in s.get("basis", []):
            if b.get("role") not in ROLES:
                errs.append(f"synthesis {sid}: role {b.get('role')!r}")
            if b.get("finding") not in F:
                errs.append(f"synthesis {sid}: unknown finding {b.get('finding')}")
                continue
            for ev in F[b["finding"]]["evidence"]:
                vals += list(flat(read_evidence(ev)[0]))
            vals += list(flat(F[b["finding"]]["statement"]))
        for k in ("judgement", "strength_basis", "short"):
            bad = traces(str(s.get(k, "")), vals)
            if bad:
                errs.append(f"synthesis {sid}: {k} numbers not in its basis: {bad}")
        S[sid] = s
    return S, errs


def load_runs():
    runs = {}
    for src in sorted((SITE / "runs").glob("*.json")):
        r = json.loads(src.read_text())
        runs[r["id"]] = r
    return runs


# ------------------------------------------------------------------ markdown (the subset the pages use)
def inline(t):
    t = E(t, quote=False)
    t = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)
    return t


def table_md(lines):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    head, body = rows[0], [r for r in rows[2:]]
    num = [all(re.fullmatch(r"[−+\-\d.,%×x\[\] /]*\d[−+\-\d.,%×x\[\] /]*", r[i] or "x") for r in body if i < len(r))
           for i in range(len(head))]
    th = "".join(f"<th>{inline(h)}</th>" for h in head)
    def cell(c):                                 # "text {#id}" anchors a cell
        m = re.search(r"\s*\{#([\w-]+)\}$", c)
        return f'<span id="{m.group(1)}"></span>{inline(c[:m.start()])}' if m else inline(c)
    tb = "".join("<tr>" + "".join(f'<td{" class=n" if num[i] else ""}>{cell(c)}</td>' for i, c in enumerate(r)) + "</tr>"
                 for r in body)
    return f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


def md(text, ctx):
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        if s.startswith("{{") and s.endswith("}}"):
            out.append(directive(s[2:-2].strip(), ctx))
            i += 1
        elif s.startswith(":::"):
            kind, _, rest = s[3:].partition(" ")
            j, depth = i + 1, 1
            while j < len(lines):
                t = lines[j].strip()
                if t.startswith(":::") and t != ":::":
                    depth += 1
                elif t == ":::":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = md("\n".join(lines[i + 1:j]), ctx)
            m = re.search(r"\s*\{#([\w-]+)\}$", rest)
            rid = f' id="{m.group(1)}"' if m else ""
            rest = rest[:m.start()] if m else rest
            if kind == "more":
                out.append(f'<details class="more"{rid}><summary>{inline(rest)}</summary>{inner}</details>')
            else:
                out.append(f'<div class="{kind}"{rid}>{inner}</div>')
            i = j + 1
        elif s.startswith("```"):
            j = i + 1
            while not lines[j].strip().startswith("```"):
                j += 1
            out.append("<pre><code>" + E("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
        elif re.match(r"#{2,5} ", s):
            lvl = len(s) - len(s.lstrip("#"))
            title = s[lvl:].strip()
            m = re.search(r"\s*\{#([\w-]+)\}$", title)
            hid = m.group(1) if m else re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            title = title[:m.start()] if m else title
            out.append(f'<h{lvl}>{inline(title)}</h{lvl}>' if ctx.get("noid") else f'<h{lvl} id="{hid}">{inline(title)}</h{lvl}>')
            i += 1
        elif s.startswith("|"):
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            out.append(table_md(lines[i:j]))
            i = j
        elif re.match(r"(- |\d+\. )", s):
            tag = "ol" if s[0].isdigit() else "ul"
            items, j = [], i
            while j < len(lines) and lines[j].strip() and (re.match(r"\s*(- |\d+\. )", lines[j]) or lines[j].startswith("  ")):
                if re.match(r"(- |\d+\. )", lines[j]):
                    items.append(re.sub(r"^(- |\d+\. )", "", lines[j]))
                elif re.match(r"\s*(- |\d+\. )", lines[j]) or "\n" in items[-1]:
                    items[-1] += "\n" + lines[j][2:]      # nested list: rendered as a block
                else:
                    items[-1] += " " + lines[j].strip()   # wrapped line of the same item
                j += 1
            lis = []
            for it in items:
                first, _, rest = it.partition("\n")
                lis.append(f"<li>{inline(first)}{md(rest, ctx) if rest.strip() else ''}</li>")
            out.append(f"<{tag}>{''.join(lis)}</{tag}>")
            i = j
        elif s.startswith("<") and not ctx.get("noraw"):
            out.append(s)
            i += 1
        else:
            j = i
            while j < len(lines) and lines[j].strip() and not re.match(r"(#{2,5} |\||- |\d+\. |:::|```|\{\{)", lines[j].strip()):
                j += 1
            out.append(f"<p>{inline(' '.join(x.strip() for x in lines[i:j]))}</p>")
            i = j
    return "\n".join(out)


# ------------------------------------------------------------------ directives
def gh(file, label=None):
    return f'<a href="{REPO_URL}/blob/main/{file}">{E(label or file)}</a>'


def finding_home(f, here=None):
    page = STUDY_PAGE.get(f["run"], "studies.html")
    return f'#f-{f["id"]}' if page == here else f'{page}#f-{f["id"]}'


def render_finding(f, ctx):
    fid = f["id"]
    first = fid not in ctx["shown"]
    ctx["shown"].add(fid)
    sc = f["scope"]
    fam = f["family"]
    fam_t = (f'{fam["size"]} intervals in this family, {fam["excluding_0"]} exclude 0' + (f'; {fam["note"]}' if fam.get("note") else "")
             if isinstance(fam, dict) else str(fam))
    ev = "".join(f"<li>{gh(e['file'])} <code>{E(e.get('pointer', ''))}</code> — {E(e.get('what', ''))}</li>" for e in f["evidence"])
    meta = [("Measured", f["quantity"]), ("Sign", f["sign"]), ("Unit, n", f"{f['unit']}; {f['n']}"),
            ("Interval", f["interval"]), ("Added", f["status"]), ("Multiplicity", fam_t),
            ("Replication", f["replication"]),
            ("Scope", "; ".join(f"{k}: {sc[k]}" for k in SCOPE_KEYS))]
    if f.get("bound"):
        meta.insert(3, ("Not excluded", f["bound"]))
    dl = "".join(f"<dt>{E(k)}</dt><dd>{E(str(v))}</dd>" for k, v in meta)
    rid = f' id="f-{fid}"' if first else ""
    return (f'<div class="finding"{rid}><div class="fq"><span class="cls c-{f["class"].replace(" ", "-")}">{E(f["class"])}</span> '
            f'{E(f["question"])}</div><p class="fs">{E(f["statement"])}</p>'
            f'<details class="fm"><summary>{E(fid)} · {E(f["status"])} · evidence</summary><dl>{dl}</dl><ul>{ev}</ul></details></div>')


def render_synthesis(s, ctx):
    F = ctx["F"]
    rows = "".join(f'<li><span class="role r-{b["role"]}">{b["role"]}</span> <a href="{finding_home(F[b["finding"]], ctx["page"])}">'
                   f'{E(b["finding"])}</a> — {E(b.get("note", F[b["finding"]]["question"]))}</li>' for b in s["basis"])
    dns = "".join(f"<li>{E(x)}</li>" for x in s["does_not_show"])
    return (f'<div class="synthesis" id="s-{s["id"]}"><div class="sq">{E(s["question"])}</div>'
            f'<p class="sj"><span class="str st-{s["strength"]}">{s["strength"]}</span> {E(s["judgement"])}</p>'
            f'<p class="sb"><strong>Why this strength:</strong> {E(s["strength_basis"])} <strong>Scope:</strong> {E(s["scope"])}</p>'
            f'<details class="more"><summary>Basis ({len(s["basis"])} findings) and what it does not show</summary>'
            f'<ul class="basis">{rows}</ul><p><strong>Does not show</strong></p><ul>{dns}</ul></details></div>')


def render_goals(run, ctx):
    r = ctx["R"][run]
    rows = []
    for g in r["goals"]:
        fl = ", ".join(f'<a href="{finding_home(ctx["F"][x], ctx["page"])}">{E(x)}</a>' if x in ctx["F"]
                       else f'{E(x)} <span class=muted>(published, not yet rewritten)</span>' for x in g["findings"]) or E(g.get("no_findings_reason", ""))
        docs = ", ".join(gh(f"results/{run}/{d}", d) for d in g["result_docs"])
        rows.append(f'<tr id="g-{E(run)}-{E(g["id"])}"><td>{E(g["id"])}</td><td>{E(g["question"])}<div class="gh">{E(g["headline"])}</div></td>'
                    f'<td>{E(g["added"])}</td><td>{E(g["status"])}</td><td>{docs}</td><td>{fl}</td></tr>')
    return ('<div class="tbl"><table class="goals"><thead><tr><th>Goal</th><th>Question and what was measured</th><th>Added</th>'
            '<th>Status</th><th>Result</th><th>Findings</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def render_runs(ctx):
    rows = []
    for rid, r in sorted(ctx["R"].items()):
        page = STUDY_PAGE.get(rid, f"studies.html#{rid}")
        rows.append(f'<tr><td><a href="{page}">{E(r["date"])}</a></td><td>{E(r["question"])}</td><td>{E(r["kind"])}</td>'
                    f'<td>{len(r["goals"])}</td><td>{sum(len(g["findings"]) for g in r["goals"])}</td></tr>')
    return ('<div class="tbl"><table><thead><tr><th>Run</th><th>Question</th><th>Kind</th><th>Goals</th><th>Findings</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


def directive(d, ctx):
    name, _, arg = d.partition(" ")
    arg = arg.strip()
    if name == "finding":
        f = ctx["F"][arg]
        if STUDY_PAGE.get(f["run"], "studies.html") != ctx["page"]:
            raise SystemExit(f"{ctx['page']}: finding {arg} renders only on its study page; cite it from a synthesis")
        return render_finding(f, ctx)
    if name == "findings":                       # every finding of a run, in file order
        return "\n".join(render_finding(f, ctx) for f in ctx["F"].values() if f["run"] == arg)
    if name == "synthesis":
        return render_synthesis(ctx["S"][arg], ctx)
    if name in ("protocols", "setup"):           # method page: generated from the run index
        rows = []
        for rid, r in sorted(ctx["R"].items()):
            link = f'<a href="{STUDY_PAGE.get(rid, "studies.html#" + rid)}">{E(r["date"])}</a><br><span class="muted">{E(r["title"])}</span>'
            if name == "protocols":
                pr = r.get("protocol") or {}
                f = pr.get("file")
                fp = f"results/{rid}/{f}" if f and (REPO / "results" / rid / f).is_file() else f
                fl = f'<a href="{REPO_URL}/blob/main/{E(fp)}">{E(fp)}</a>' if f and (REPO / fp).is_file() else E(f or "none")
                am = "".join(f"<li>{E(a)}</li>" for a in pr.get("amendments") or [])
                rows.append(f'<tr id="p-{E(rid)}"><td>{link}</td><td>{fl}</td><td>{E(pr.get("frozen") or "not frozen")}</td>'
                            f'<td>{"<ul>" + am + "</ul>" if am else "none"}</td></tr>')
            else:
                ul = lambda xs: "<ul>" + "".join(f"<li>{E(x)}</li>" for x in xs) + "</ul>"
                rows.append(f'<tr><td>{link}</td><td>{ul(r["engines"])}</td><td>{ul(r["checkpoints"])}</td><td>{E(r["hardware"])}</td></tr>')
        head = (("Run", "Protocol file", "Frozen", "Amendments") if name == "protocols"
                else ("Run", "Engines", "Checkpoints", "Hardware"))
        return ('<div class="tbl"><table><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
                + "".join(rows) + "</tbody></table></div>")
    if name == "corrections":                    # audit page: statements this rebuild corrected, each with its findings
        rows = []
        for c in json.loads((SITE / "corrections.json").read_text()):
            vals = []
            for fid in c["findings"]:
                f = ctx["F"][fid]
                ctx["cited"].add(fid)
                vals += list(flat(f["statement"])) + [v for ev in f["evidence"] for v in flat(read_evidence(ev)[0])]
            bad = traces(c["now"], vals)
            if bad:
                raise SystemExit(f"correction {c['id']}: numbers not in its findings: {bad}")
            links = " ".join(f'<a href="{finding_home(ctx["F"][x], ctx["page"])}">{E(x)}</a>' for x in c["findings"])
            rows.append(f'<tr id="{c["id"]}"><td>{E(c["where"])}</td><td>{E(c["said"])}</td><td>{E(c["now"])}</td>'
                        f'<td>{E(c["kind"])}</td><td>{links}</td></tr>')
        return ('<div class="tbl"><table><thead><tr><th>Where</th><th>Said</th><th>What the data show</th><th>Kind</th>'
                '<th>Findings</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
    if name == "include":                        # a published Markdown document, rendered (procedures, not findings)
        arg, _, opt = arg.partition(" ")
        noid = opt.strip() == "noid"             # headings without ids, for documents included beside others
        path = REPO / arg
        if not arg.startswith(("repro/", "protocol/", "results/")) or path.suffix != ".md" or not path.is_file():
            raise SystemExit(f"{ctx['page']}: {{{{include {arg}}}}} is not a published .md file")
        base = str(Path(arg).parent)
        def link(m):
            t = m.group(2)
            if re.match(r"[a-z]+:|#", t):
                return m.group(0)
            path, _, frag = t.partition("#")
            target = (REPO / base / path).resolve().relative_to(REPO).as_posix()
            kind = "tree" if (REPO / target).is_dir() else "blob"
            return f"]({REPO_URL}/{kind}/main/{target}{'#' + frag if frag else ''})"
        text = re.sub(r"^# .*\n", "", path.read_text(), count=1)
        text = re.sub(r"\]\(()([^)\s]+)\)", link, text)
        sub = dict(ctx, noraw=True, noid=noid)
        return (f'<p class="muted">Rendered from {gh(arg)}.</p>' + md(text, sub))
    if name == "file":                           # a published file, verbatim, with its link
        path = REPO / arg
        if not arg.startswith(("repro/", "results/", "protocol/")) or not path.is_file():
            raise SystemExit(f"{ctx['page']}: {{{{file {arg}}}}} is not a published file under repro/, results/ or protocol/")
        return (f'<p class="muted"><a href="{REPO_URL}/blob/main/{E(arg)}">{E(arg)}</a></p>'
                f'<pre><code>{E(path.read_text().rstrip())}</code></pre>')
    if name == "cite":                           # one-line statements of findings, each linked to its home
        rows = []
        for fid in arg.split():
            f = ctx["F"][fid]
            ctx["cited"].add(fid)
            rows.append(f'<li>{E(f["statement"])} <a class="fid" href="{finding_home(f, ctx["page"])}">{E(fid)}</a>'
                        f' <span class="muted">({E(f["class"])}, {E(f["status"])})</span></li>')
        return f'<ul class="cite">{"".join(rows)}</ul>'
    if name == "answers":                        # index: every synthesis, by the page that renders it
        rows = "".join(f'<tr><td>{E(s["question"])}</td><td>{E(s.get("short", s["judgement"]))}</td>'
                       f'<td><span class="str st-{s["strength"]}">{s["strength"]}</span></td>'
                       f'<td><a href="{ctx["home"][sid]}#s-{E(sid)}">{E(ctx["home"][sid].removesuffix(".html"))}</a></td></tr>'
                       for sid, s in ctx["S"].items() if sid in ctx["home"])
        return (f'<div class="tbl"><table class="answers"><thead><tr><th>Question</th><th>Current answer</th>'
                f'<th>Strength</th><th>Page</th></tr></thead><tbody>{rows}</tbody></table></div>')
    if name == "goals":
        return render_goals(arg, ctx)
    if name == "runs":
        return render_runs(ctx)
    if name == "study":                          # studies page: one run, its goals and its findings
        r = ctx["R"][arg]
        own = [f for f in ctx["F"].values() if f["run"] == arg]
        head = (f'<h2 id="{E(arg)}">{E(r["date"])} · {E(r["title"])}</h2><p class="fs">{E(r["question"])}</p>'
                f'<p class="muted">{E(r["kind"])} · protocol: {E((r.get("protocol") or {}).get("file") or "none (not a frozen-protocol run)")}'
                f' · data: <a href="{REPO_URL}/tree/main/results/{E(arg)}">results/{E(arg)}</a></p>')
        page = STUDY_PAGE.get(arg)
        if page:
            return head + f'<p>Full record: <a href="{page}">{page}</a>.</p>'
        body = "".join(render_finding(f, ctx) for f in own)
        more = (f'<details class="more"><summary>Findings written to the current standard ({len(own)})</summary>{body}</details>' if own else "")
        return head + more + f'<details class="more"><summary>Every goal of this run ({len(r["goals"])})</summary>{render_goals(arg, ctx)}</details>'

    if name == "table":                          # {{table NAME [ARG ...]}}: a named table built from published data
        fn, *args = arg.split()
        return getattr(tables, fn.replace("-", "_"))(REPO, *args)
    raise SystemExit(f"{ctx['page']}: unknown directive {{{{{d}}}}}")


# ------------------------------------------------------------------ anchors that live links point at
REDIRECTS = {"research.html": ("precision.html", "Precision"), "ledger.html": ("method.html#timeline", "Method: runs"),
             "long-output.html": ("long-tasks.html", "Long tasks"), "observations.html": ("running.html", "Running it"),
             "throughput.html": ("speed.html", "Speed")}
STUBS = set(REDIRECTS)


def stub(target, label):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            f'initial-scale=1"><meta http-equiv="refresh" content="0; url={target}"><title>Moved - cuteafd-eval</title>'
            f'</head><body><p>This page moved: <a href="{target}">{E(label)}</a>.</p></body></html>\n')


def page_numbers(text, ctx):
    """Numbers typed into a page must come from the findings that page renders, cites or links."""
    ids = set(ctx["shown"]) | set(ctx["cited"]) | set(re.findall(r"#f-([\w.-]+)", text))
    for sid in re.findall(r"^\{\{synthesis (\S+)\}\}$", text, re.M) + re.findall(r"#s-([\w.-]+)", text):
        if sid in ctx["S"]:
            ids |= {b["finding"] for b in ctx["S"][sid]["basis"]}
            ids.add("S:" + sid)
    vals = []
    for i in ids:
        if i.startswith("S:"):
            vals += list(flat({k: ctx["S"][i[2:]][k] for k in ("judgement", "short") if k in ctx["S"][i[2:]]}))
        elif i in ctx["F"]:
            vals += list(flat(ctx["F"][i]["statement"]))
            for ev in ctx["F"][i]["evidence"]:
                vals += list(flat(read_evidence(ev)[0]))
    prose = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    prose = "\n".join(ln for ln in prose.split("\n") if not ln.strip().startswith("{{"))
    prose = re.sub(r"\]\([^)]*\)", "]", prose)                       # link targets
    return traces(prose, vals)


def link_targets():
    """(page, id) pairs that the published site, README, llms.txt, findings or run documents link to."""
    pat = re.compile(r"(?<![\w/.-])(?:docs/)?([a-z0-9-]+\.html)#([A-Za-z0-9_.:-]+)")
    srcs = [*sorted((REPO / "docs").glob("*.html")), REPO / "README.md", REPO / "docs" / "llms.txt",
            REPO / "docs" / "findings.json", *sorted((REPO / "results").rglob("*.md")),
            *sorted((REPO / "results").rglob("*.json"))]
    out = set()
    for src in srcs:
        if src.exists():
            out |= set(pat.findall(src.read_text(errors="replace")))
    return {(p, i) for p, i in out if p not in STUBS}


# ------------------------------------------------------------------ pages
def page(name, text, ctx):
    css = (SITE / "style.css").read_text()
    m = re.match(r"# (.+)\n", text)
    title = m.group(1).strip() if m else name
    body = md(text[m.end():] if m else text, ctx)
    nav = "".join(f'<a href="{p}" class="{"on" if p == name else ""}">{t}</a>' for p, t in NAV)
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
           f'initial-scale=1"><meta name="color-scheme" content="light dark"><title>{E(title)} - cuteafd-eval</title>'
           f'<link rel="alternate" type="application/json" title="Findings with source pointers" href="findings.json">'
           f'<style>\n{css}</style></head><body><nav aria-label="Pages"><span class="brand">cuteafd-eval</span>{nav}</nav>'
           f'<main><h1>{inline(title)}</h1>\n{body}\n</main><footer>Machine-readable: <a href="findings.json">findings.json</a> '
           f'(findings and syntheses with source pointers) and <a href="runs.json">runs.json</a> (every run, its goals and files). '
           f'Built from the repository data by <code>next/tools/build.py</code>. Maintained by Michael M (UrbanAstroLA on GitHub, '
           f'@UrbanAstroFella on X). Results CC BY 4.0, code Apache-2.0.</footer></body></html>\n')
    ids = re.findall(r'\bid="([^"]+)"', doc)
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        raise SystemExit(f"{name}: duplicate ids {dup}")
    if "<script" in doc.lower():
        raise SystemExit(f"{name}: pages carry no scripts")
    return doc


# GitHub Pages serves docs/ only: until cutover the rebuilt pages are also written to docs/preview/ and served from there
SITE_URL = "https://urbanastrola.github.io/cuteafd-eval/preview/"
PREVIEW = REPO / "docs" / "preview"


def _cell(t):
    return str(t).replace("|", "/").replace("\n", " ")


def write_readme(F, S, R, home):
    """README.md from its template: the answers and the run list come from the judgements and the run index."""
    ans = ["| Question | Current answer | Strength |", "|---|---|---|"] + [
        f"| {_cell(s['question'])} | {_cell(s.get('short', s['judgement']))} "
        f"([{home[sid].removesuffix('.html')}]({SITE_URL}{home[sid]}#s-{sid})) | {s['strength']} |"
        for sid, s in S.items() if sid in home]
    runs = ["<!-- results:start -->", "| Run | Kind | Question | Findings |", "|---|---|---|---|"] + [
        f"| [{r['date']}](results/{rid}) | {r['kind']} | {_cell(r['question'])} | {sum(1 for f in F.values() if f['run'] == rid)} |"
        for rid, r in sorted(R.items())] + ["<!-- results:end -->"]
    text = (SITE / "README.template.md").read_text()
    text = text.replace("{{answers-md}}", "\n".join(ans)).replace("{{runs-md}}", "\n".join(runs)).replace("{{site}}", SITE_URL)
    if "{{" in text:
        raise SystemExit("README template: unknown directive")
    # next/README.md sits one folder below the repository root until cutover: point root files one level up
    text = re.sub(r"\]\((results/|NOTICE\.md|CITATION\.cff)", r"](../\1", text)
    text = text.replace("\n\nMeasurements of", "\n\n> **Preview.** This is the rebuilt site, kept in `next/` beside the live one until cutover. Its pages are "
                        f"built into [`next/docs/`](docs/) and served at <{SITE_URL}>; the live site at the repository root is the earlier version "
                        "until cutover.\n\nMeasurements of", 1)
    (OUT.parent / "README.md" if OUT != REPO / "next" / "docs" else REPO / "next" / "README.md").write_text(text)


def write_llms(F, S, R, home):
    """llms.txt: orientation for agents, generated from the judgements and the run index."""
    out = ["# cuteafd-eval", "",
           "> Measurements of CuteAFD and tpurtell's vLLM fork serving quantized GLM-5.3-Flash checkpoints on one machine",
           "> (2x RTX PRO 6000 Blackwell Max-Q, 300 W). Results-first; nothing here is a recommendation. Maintained by Michael M",
           "> (UrbanAstroLA).", "",
           "## Read these first",
           f"- {SITE_URL}findings.json: every finding (one measured quantity: statement, class, status, sign, unit, n, interval,",
           "  scope, family, replication, evidence pointers into results/) and every judgement (strength, basis, does_not_show).",
           f"- {SITE_URL}runs.json: every run, its goals (sub-questions, design, status) and the files each goal owns.",
           "- https://github.com/UrbanAstroLA/cuteafd-eval/tree/main/results: the frozen data, one folder per run.", "",
           "## How to read a finding",
           "- class: difference (interval excludes 0) | not detected (interval includes 0; `bound` gives the largest effect not",
           "  excluded) | descriptive (counts, no interval) | source reading | accounting.",
           "- status: protocol | amendment | follow-up (declared before its own data) | post hoc | exploratory | check.",
           "- family: how many intervals were computed alongside it and how many excluded 0. Intervals are not corrected for",
           "  multiplicity unless a protocol said so.",
           "- Do not read 'not detected' as 'no difference'. Do not generalise past `scope` (one model, one machine).",
           "- Fixtures are not comparable across model families; KL and NLL are per tokenizer.", "",
           "## Current judgements (strength: established > supported > indicated > open)"]
    for sid, s in S.items():
        if sid in home:
            out.append(f"- {s['question']} {s.get('short', s['judgement'])} [{s['strength']}] {SITE_URL}{home[sid]}#s-{sid}")
    out += ["", "## Pages"] + [f"- {SITE_URL}{p}: {t}" for p, t in NAV] + [
        f"- {SITE_URL}v5.html: CuteAFD v5.0.0 study record", f"- {SITE_URL}v4.html: CuteAFD v4.0.0 study record",
        f"- {SITE_URL}audit.html: corrections made in the rebuild, and the 2026-10-27 review", f"- {SITE_URL}reproduce.html: reproduction",
        "", "## Runs"] + [f"- {r['date']} {rid}: {r['question']}" for rid, r in sorted(R.items())]
    (OUT / "llms.txt").write_text("\n".join(out) + "\n")


def main(argv):
    global OUT
    if "--out" in argv:                          # build into another directory (verify.py compares it with next/docs)
        OUT = Path(argv[argv.index("--out") + 1]).resolve()
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    errs = []
    for run in sorted((SITE / "runs").glob("*.json")):
        if only is None or run.stem in only:
            errs += check_runs.check(run.stem)
    F, e = load_findings()
    errs += e
    S, e = load_syntheses(F)
    errs += e
    R = load_runs()
    carried = set(F) | {r for f in F.values() for r in f.get("replaces", [])}
    live = json.loads((REPO / "docs" / "findings.json").read_text())        # the published site: nothing may be lost
    for o in (live["findings"] if isinstance(live, dict) else live):
        if o["id"] not in carried:
            errs.append(f"published finding {o['id']} ({o.get('run', '').split('/')[-1]}) not carried: "
                        f"list it in a new finding's `replaces`")
    for fid, f in F.items():
        goals = {g["id"]: g for g in R.get(f["run"], {}).get("goals", [])}
        if f["run"] in R and f["goal"] not in goals:
            errs.append(f"finding {fid}: goal {f['run']}/{f['goal']} not in the run index")
        elif f["run"] in R and fid not in goals[f["goal"]]["findings"]:
            errs.append(f"finding {fid}: not listed under its goal {f['goal']} in the run index")
    if only is not None:
        mine = {fid for fid, f in F.items() if f["run"] in only}
        errs = [e_ for e_ in errs if any(r in e_ for r in only)
                or (e_.startswith("finding ") and e_.split()[1].rstrip(":") in mine)
                or "not valid JSON" in e_]
    for e_ in errs:
        print("  ", e_)
    if errs:
        print(f"{len(errs)} problem(s)")
        return 1
    if "--check" in argv:
        print(f"ok: {len(R)} runs, {sum(len(r['goals']) for r in R.values())} goals, {len(F)} findings, {len(S)} syntheses")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    home = {}                                    # synthesis id -> the one page that renders it
    for src in sorted((SITE / "pages").glob("*.md")):
        for sid in re.findall(r"^\{\{synthesis (\S+)\}\}$", src.read_text(), re.M):
            if sid in home:
                raise SystemExit(f"synthesis {sid} rendered on {home[sid]} and {src.stem}.html: one home per synthesis")
            home[sid] = src.stem + ".html"
    homeless = sorted(set(S) - set(home))
    for sid, s in S.items():
        if s.get("page") and sid in home and home[sid] != s["page"] + ".html":
            raise SystemExit(f"synthesis {sid}: page {s['page']} but rendered on {home[sid]}")
    rendered = {}
    for target, (to, label) in REDIRECTS.items():
        (OUT / target).write_text(stub(to, label))
    for src in sorted((SITE / "pages").glob("*.md")):
        ctx = {"F": F, "S": S, "R": R, "page": src.stem + ".html", "shown": set(), "home": home, "cited": set()}
        text = src.read_text()
        (OUT / ctx["page"]).write_text(page(ctx["page"], text, ctx))
        rendered[ctx["page"]] = ctx["shown"]
        bad = page_numbers(text, ctx)
        if bad:
            raise SystemExit(f"{ctx['page']}: numbers not in the findings it renders, cites or links: {bad}")
    on_page = {fid for s in rendered.values() for fid in s}
    missing = sorted(set(F) - on_page)
    (OUT / "findings.json").write_text(json.dumps({"findings": list(F.values()), "syntheses": list(S.values())},
                                                  indent=1, ensure_ascii=False) + "\n")
    (OUT / "runs.json").write_text(json.dumps(list(R.values()), indent=1, ensure_ascii=False) + "\n")
    ids = {p.name: set(re.findall(r'\bid="([^"]+)"', p.read_text())) for p in OUT.glob("*.html")}
    broken = sorted({f"{pg}: {h}" for pg in rendered for h in re.findall(r'href="([a-z0-9-]+\.html)?#([^"]+)"', (OUT / pg).read_text()) and
                     [f"{t or pg}#{i}" for t, i in re.findall(r'href="([a-z0-9-]+\.html)?#([^"]+)"', (OUT / pg).read_text())
                      if i not in ids.get(t or pg, set())]})
    if broken:
        raise SystemExit("links to anchors that do not exist:\n  " + "\n  ".join(broken))
    lost = sorted(f"{p}#{i}" for p, i in link_targets()
                  if not (OUT / p).exists() or f'id="{i}"' not in (OUT / p).read_text())
    write_readme(F, S, R, home)
    write_llms(F, S, R, home)
    print(f"built {len(rendered)} pages: {len(R)} runs, {len(F)} findings ({len(missing)} on no page), {len(S)} syntheses")
    if missing:
        print("   on no page:", " ".join(missing))
    if homeless:
        print("   syntheses on no page:", " ".join(homeless))
    if lost:
        print(f"   linked anchors not on the new pages ({len(lost)}):", " ".join(lost))
    if OUT == REPO / "next" / "docs" and PREVIEW.parent.is_dir():     # the served copy; verify.py checks it is identical
        shutil.rmtree(PREVIEW, ignore_errors=True)
        shutil.copytree(OUT, PREVIEW)
        print(f"   copied to {PREVIEW.relative_to(REPO)}/ ({SITE_URL})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
