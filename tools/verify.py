#!/usr/bin/env python3
"""Verify cuteafd-eval: manifests, published-copy hashes, result labels, and a content scan.

    python3 tools/verify.py            # everything
    python3 tools/verify.py --quiet    # failures and the final line only

Checks
  1. Every MANIFEST.json (the repository's and each results/<run>/ one): every listed file exists with that
     sha256, and every file under the manifest's directory is listed.
  2. docs/ (the Pages site): static HTML and CSS only, no scripts (except the one-line forwarding script of a page that
     moved), external stylesheets, fonts or remote images; every link to another page or anchor of the site, and every
     link to a repository file or folder, resolves.
  3. protocol/HASHES.json: every file marked identical to a frozen file has the frozen sha256.
  4. results/<run>/RUN.json: a kind (measurement, exploratory, withdrawn or check); runs that are not
     measurements open their README with a banner naming the kind; slots marked done have their files.
  5. README.md: the run list states each run's kind as its RUN.json does.
  0. A self-test of the content patterns (absolute paths after ":-", "=", quotes and brackets are caught; relative
     segments such as "humanevalplus/data/x" are not).
  7. Block Q tails: tools/kl_tails.py --check recomputes every results/<run>/q/tails/<panel>-tails.json whose
     per-position file is in the repository and requires byte-identical output.
  8. The site's sources (site/): tools/build.py --check passes (run index covers every published file; every finding's
     values re-read from its file; every number in findings, judgements and pages traces to data), and docs/ and
     README.md equal a fresh build. Recomputations carried from the earlier findings file (site/recompute.json) are
     rerun with check 6's code.
  6. Content scan of every file, docs/ included: local paths, machine and user names, private IP addresses, e-mail addresses
     other than the maintainer's public no-reply address, credentials, GPU identifiers, benchmark names that
     must not appear, names of the K4 protocol's unpublished arm (its project name, build tag, author and run
     labels), and attribution lines. Every hit is printed as file:line.

Standard library only (Python 3.10+). Exit status 1 on any failure.
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOREPLY = "337816102+UrbanAstroLA@users.noreply.github.com"
KINDS = {"measurement", "exploratory", "withdrawn", "check"}
SKIP_DIRS = {".git", "__pycache__"}

# Patterns are assembled from pieces so that this file does not match itself.
J = "".join
FORBIDDEN = [
    ("machine name", re.compile(J(["(?i)al", "bir", "eo"]))),
    # An absolute path is flagged wherever it starts (line start, "=", ":-", quotes, brackets, spaces); only a relative
    # segment preceded by a letter or digit, such as "humanevalplus/data/x", is allowed.
    ("local path", re.compile(J([r"(?<![A-Za-z0-9])/(?:da", "ta|ho", "me|tm", r"p)/"]))),
    ("user name", re.compile(J([r"(?i)\bsys", r"op\b"]))),
    ("private IP", re.compile(J([r"\b192\.16", r"8\.\d{1,3}\.\d{1,3}\b"]))),
    ("private IP", re.compile(J([r"(?<![\d.])10\.\d{1,3}\.\d{1,3}", r"\.\d{1,3}(?![\d.])"]))),
    ("private IP", re.compile(J([r"\b172\.(?:1[6-9]|2\d|3[01])", r"\.\d{1,3}\.\d{1,3}\b"]))),
    ("e-mail", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}\b")),
    ("excluded benchmark", re.compile(J(["(?i)gp", "qa"]))),   # allowed only in BENCH_SCOPE below
    ("excluded project", re.compile(J(["(?i)tensor", "fold|aevo", r"nix|\bm", r"ia\b"]))),
    # an engine arm of the K4 protocol that is not published: its build tag, its author and its run labels
    ("unpublished arm", re.compile(J(["(?i)tf1", "17|ashh", r"art|\bT-", r"[rqtd]1"]))),
    ("attribution", re.compile(J(["(?i)clau", "de|anthro", "pic|co-author", "ed-by|generated with \\[", "|\U0001F916"]))),
    ("credential", re.compile(J([r"\bs", r"k-[A-Za-z0-9_\-]{12,}|\bh", r"f_[A-Za-z0-9]{20,}|\bgh[pousr]", r"_[A-Za-z0-9]{20,}"]))),
    ("credential", re.compile(J([r"github_", r"pat_|AK", r"IA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIV", r"ATE KEY|Bear", r"er [A-Za-z0-9._\-]{20,}"]))),
    ("GPU identifier", re.compile(J([r"\bGP", r"U-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}|(?i:serial)(?: number)?\W{1,4}\d{8,}"]))),
]
fails = []
# The thinking-length investigation is built on that benchmark's question ids (never its question text), so its name may
# appear in the investigation's folders (vLLM fork, CuteAFD core swap and the 2026-11-05/06 follow-ups) and page, and in
# the page's builder; everywhere
# else it stays excluded.
BENCH_SCOPE = ("results/2026-11-02-thinking-length/", "results/2026-11-03-cuteafd-core-swap/", "results/2026-11-05-code-thinking/",
               "results/2026-11-05-attn-position/", "results/2026-11-06-new-questions/", "results/2026-11-06-vllm-code-thinking/", "docs/thinking.html")
REPO_URL = "https://github.com/UrbanAstroLA/cuteafd-eval"

# Self-test of the content patterns, run on every invocation: (text, kind expected or None). Built from pieces so that
# this file does not match itself.
D, H, T = "/da" + "ta/", "/ho" + "me/", "/tm" + "p/"
SELF_TEST = [
    ('OUT_DIR="${OUT_DIR:-' + D + 'runs/x}"', "local path"), ('p = "' + H + 'someone/x"', "local path"),
    (D + "runs/x at line start", "local path"), ("X=" + T + "y", "local path"), ("(" + D + "x)", "local path"),
    ("'" + T + "x'", "local path"), ("--out=" + D + "x", "local path"), ("a ./" + "da" + "ta/x", "local path"),
    ("humanevalplus" + D + "test.parquet", None), ("tiering/p2p" + D + "x", None), ("<data>/x", None),
    ("pair " + "T-" + "r1|C-r1", "unpublished arm"), ("--arm " + "T-" + "q1", "unpublished arm"), ("Ten" + "sorFold 1.1.7", "excluded project"),
    ("V-r1|C-r1 and V-r2", None), ("Block T-SUMMARY.md, t-compare.json", None),
]


def self_test():
    for text, want in SELF_TEST:
        got = [w for w, rx in FORBIDDEN if rx.search(text) and not (w == "e-mail" and rx.search(text).group(0) == NOREPLY)]
        if (want is None and got) or (want is not None and want not in got):
            fails.append(f"self-test: {text!r} gave {got}, expected {want or 'no hit'}")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def files_under(d):
    return sorted(p for p in d.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS))


def rel(p):
    return p.relative_to(ROOT).as_posix()


def check_manifest(mpath):
    base = mpath.parent
    try:
        m = json.loads(mpath.read_text())
    except Exception as e:
        fails.append(f"{rel(mpath)}: unreadable ({e})"); return 0
    listed = m.get("files", {})
    for name, h in listed.items():
        p = base / name
        if not p.is_file(): fails.append(f"{rel(mpath)}: listed file missing: {name}")
        elif sha(p) != h: fails.append(f"{rel(mpath)}: sha256 mismatch: {name}")
    for p in files_under(base):
        r = p.relative_to(base).as_posix()
        if p == mpath: continue
        if r not in listed: fails.append(f"{rel(mpath)}: file not listed: {r}")
    return len(listed)


SITE_FORBIDDEN = [("script", re.compile(r"(?i)<script")), ("external stylesheet or font", re.compile(r"(?i)<link[^>]+rel=.?stylesheet|@import|@font-face")),
                  ("remote resource", re.compile(r"""(?i)\b(?:src|srcset)\s*=\s*["']?(?:https?:)?//|url\(\s*["']?(?:https?:)?//"""))]


def check_site(d=ROOT / "docs"):
    if not d.is_dir(): fails.append(f"{rel(d)}/ missing"); return 0
    pages = {p.name: p.read_text() for p in sorted(d.glob("*.html"))}
    if "index.html" not in pages: fails.append("docs/index.html missing")
    for name, html in pages.items():
        if 'http-equiv="refresh"' in html:                                # a page that moved: its forwarding line only
            html = re.sub(r'<script>var a=\{[^<]*\};var h=location\.hash\.slice\(1\);h=[^<]*;location\.replace\([^<]*\)</script>', "", html, count=1)
        for what, rx in SITE_FORBIDDEN:
            if rx.search(html): fails.append(f"{rel(d)}/{name}: {what} not allowed on the static site")
        for href in re.findall(r'href="([^"]+)"', html):
            m = re.match(re.escape(REPO_URL) + r"/(blob|tree)/main/([^#?]+)", href)
            if m:                                                          # a link to a repository file or folder
                t = ROOT / m.group(2)
                if not (t.is_file() if m.group(1) == "blob" else t.is_dir()):
                    fails.append(f"{rel(d)}/{name}: link to a missing repository {'file' if m.group(1) == 'blob' else 'folder'} {m.group(2)}")
                continue
            if re.match(r"(?i)[a-z][a-z0-9+.-]*:", href): continue          # other absolute link
            page, _, frag = href.partition("#")
            if page and not page.endswith(".html") and (d / page).is_file(): continue   # findings.json, runs.json, llms.txt
            target = pages.get(page or name)
            if target is None: fails.append(f"{rel(d)}/{name}: link to missing page {href}"); continue
            if frag and f'id="{frag}"' not in target: fails.append(f"{rel(d)}/{name}: link to missing anchor {href}")
    return len(pages)


def check_hashes():
    p = ROOT / "protocol" / "HASHES.json"
    if not p.exists(): fails.append("protocol/HASHES.json missing"); return
    for e in json.loads(p.read_text())["frozen"]:
        if e.get("published") and e.get("published_identical"):
            f = ROOT / e["published"]
            if not f.is_file() or sha(f) != e["frozen_sha256"]:
                fails.append(f"protocol/HASHES.json: {e['published']} is marked identical to the frozen file but is not")


def check_runs():
    kinds = {}
    for d in sorted((ROOT / "results").iterdir()):
        if not d.is_dir(): continue
        rp = d / "RUN.json"
        if not rp.exists(): fails.append(f"{rel(d)}: RUN.json missing"); continue
        r = json.loads(rp.read_text()); k = r.get("kind")
        kinds[d.name] = k
        if k not in KINDS: fails.append(f"{rel(rp)}: kind {k!r} not one of {sorted(KINDS)}")
        if not (d / "MANIFEST.json").exists(): fails.append(f"{rel(d)}: MANIFEST.json missing")
        readme = (d / "README.md").read_text() if (d / "README.md").exists() else ""
        if not readme: fails.append(f"{rel(d)}: README.md missing")
        if k != "measurement" and k in KINDS and k.upper() not in readme[:600].upper():
            fails.append(f"{rel(d)}: README.md must open with a banner naming the kind ({k})")
        for slot, s in r.get("slots", {}).items():
            if s.get("status") not in ("done", "pending"): fails.append(f"{rel(rp)}: slot {slot} status must be done or pending")
            for f in s.get("files", []) if s.get("status") == "done" else []:
                if not (d / f).is_file(): fails.append(f"{rel(rp)}: slot {slot} is done but {f} is missing")
    return kinds


def check_findings():
    """docs/findings.json: every pointer resolves to the recorded value, every file and page anchor exists, and the
    entries that carry 'recompute' match a recomputation from the published per-reply tables (or, for the kind
    window_ratio_bootstrap, from a published per-window table, joined by window id with the tables named in
    recompute.windows_with)."""
    import csv, math, statistics
    fp = ROOT / "docs" / "findings.json"
    if not fp.exists(): fails.append("docs/findings.json missing"); return 0
    doc = json.loads(fp.read_text()); cache = {}
    if "syntheses" in doc: doc = {"findings": []}      # findings and judgements: checked by tools/build.py (check_build)
    lp = ROOT / "site" / "recompute.json"
    if lp.exists():                                     # recomputations carried from the earlier findings file
        doc["findings"] += [dict(e, _legacy=True) for e in json.loads(lp.read_text())["checks"]
                            if e["id"] not in {f["id"] for f in doc["findings"]}]
    def at(file, pointer):
        if file not in cache: cache[file] = json.loads((ROOT / file).read_text())
        v = cache[file]
        for part in pointer.lstrip("/").split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            v = v[int(part)] if isinstance(v, list) else v[part]
        return v
    def rows(file):
        with open(ROOT / file, newline="") as f: return list(csv.DictReader(f))
    def ok(r): return r["finish_reason"] == "stop" and r["hit_cap"] == "False" and int(r["reasoning_tokens"] or 0) > 0
    def logs(ra, a, rb, b, prompts):
        A = {(int(r["prompt"]), int(r["rep"])): r for r in ra if r["arm"] == a}
        B = {(int(r["prompt"]), int(r["rep"])): r for r in rb if r["arm"] == b}
        by = {}
        for k, r in A.items():
            if k[0] in prompts and k in B and ok(r) and ok(B[k]):
                by.setdefault(k[0], []).append(math.log(int(r["reasoning_tokens"]) / int(B[k]["reasoning_tokens"])))
        return by
    for f in doc["findings"]:
        fid = f["id"]
        for e in ([] if f.get("_legacy") else f.get("evidence", [])):
            if not (ROOT / e["file"]).is_file(): fails.append(f"findings {fid}: file missing {e['file']}"); continue
            if "pointer" in e:
                try: v = at(e["file"], e["pointer"])
                except (KeyError, IndexError, ValueError): fails.append(f"findings {fid}: pointer does not resolve {e['file']}#{e['pointer']}"); continue
                if v != e["value"]: fails.append(f"findings {fid}: {e['file']}#{e['pointer']} is {v!r}, findings.json says {e['value']!r}")
        for d in f.get("data", []):
            if not (ROOT / d).is_file(): fails.append(f"findings {fid}: data file missing {d}")
        if not f.get("_legacy"):
            page, _, frag = f["page"].rpartition("/")[2].partition("#")
            html = (ROOT / "docs" / page).read_text() if (ROOT / "docs" / page).exists() else None
            if html is None or (frag and f'id="{frag}"' not in html): fails.append(f"findings {fid}: page anchor missing {f['page']}")
        rc = f.get("recompute")
        if not rc: continue
        if rc["kind"] == "seed_paired_ratio":
            ra = rows(rc["data"] if "data" in rc else rc["data_a"]); rb = ra if "data" in rc else rows(rc["data_b"])
            by = logs(ra, rc["a"], rb, rc["b"], set(rc["prompts"]))
            got = math.exp(statistics.mean(x for v in by.values() for x in v))
        elif rc["kind"] == "cross_engine_ratio":
            by = logs(rows(rc["data_a"]), rc["a"], rows(rc["data_b"]), rc["b"], set(rc["prompts"]))
            got = math.exp(statistics.mean(statistics.mean(v) for v in by.values()))
        elif rc["kind"] == "count_all_pass":
            allr = [r for d in rc["data"] for r in rows(d)]
            got = {arm: sum(r["all_tests_pass"] == "True" and (arm.startswith("C-") or ok(r)) for r in allr if r["arm"] == arm)
                   for arm in f["result"]["value"]}
            if got != f["result"]["value"]: fails.append(f"findings {fid}: recomputed {got}, findings.json says {f['result']['value']}")
            continue
        elif rc["kind"] == "pass_pairs":
            allr = [r for d in rc["data"] for r in rows(d)]
            arm = lambda n: {(r["prompt"], r["rep"]): r["all_tests_pass"] == "True" for r in allr if r["arm"] == n and ok(r)}
            for c_, want in f["result"]["value"].items():
                A, B = (arm(n) for n in c_.split(" vs "))
                ks = [k for k in A if k in B]
                got = statistics.mean(int(A[k]) - int(B[k]) for k in ks)
                if abs(got - want) > 1e-9: fails.append(f"findings {fid}: {c_} recomputed {got:.6f}, findings.json says {want:.6f}")
            continue
        elif rc["kind"] == "item_paired_difference":
            import random
            def val(r): return int(r["correct"]) / int(r["fields"]) if r["finish_class"] == "stop" and int(r["fields"] or 0) else 0.0
            if rc.get("value") == "unfinished":            # share of replies that did not finish, in place of the request score
                def val(r): return float(r["finish_class"] != "stop")
            F = {(r["arm"], r["pass"], r["item"], r["length"]): r for d in ([rc["data"]] if isinstance(rc["data"], str) else rc["data"])
                 for r in rows(d) if r["final"] == "1" and r["status"] == "ok"}
            fam = {k[2]: r["family"] for k, r in F.items()}
            items = sorted(i for i in fam if rc.get("family") in (None, fam[i]))
            cells = [(p, L) for p in rc["passes"] for L in rc["lengths"]]
            n, draws = len(items), rc["bootstrap"]["draws"]; rng = random.Random(rc["bootstrap"]["seed"])
            if rc["estimator"] == "frozen":
                d = [statistics.fmean(val(F[(rc["b"], p, i, L)]) - val(F[(rc["a"], p, i, L)]) for p, L in cells
                                      if (rc["a"], p, i, L) in F and (rc["b"], p, i, L) in F) for i in items]
                bs = sorted(statistics.fmean(d[rng.randrange(n)] for _ in range(n)) for _ in range(draws))
                got = [statistics.fmean(d), bs[int(0.025 * draws)], bs[int(0.975 * draws) - 1]]
            else:
                def sc(arm, i):
                    v = [val(F[(arm, p, i, L)]) for p, L in cells]
                    return sum((x == 1.0) if rc.get("strict") else x for x in v) / len(v)
                d = [sc(rc["b"], i) - sc(rc["a"], i) for i in items]
                bs = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
                got = [sum(d) / n, bs[int(0.025 * draws)], bs[int(0.975 * draws)]]
            fr = f["result"][rc["result"]] if "result" in rc else f["result"]        # an entry with several results names the one recomputed
            got = [round(x, 4) for x in got]; want = [fr["value"]] + list(fr["ci95"])
            if got != want or n != fr["items"]: fails.append(f"findings {fid}: recomputed {got} over {n} items, findings.json says {want} over {fr['items']}")
            continue
        elif rc["kind"] == "window_ratio_bootstrap":
            # Ratio of sums over windows with a window-block bootstrap (SplitMix64, linear-interpolation percentiles), from a
            # published per-window table: positions x mean = the window's sum. One check per published [value, 2.5%, 97.5%].
            W = sorted(at(rc["data"], rc["windows"]), key=lambda w: w["window"]); M = (1 << 64) - 1; bt = rc["bootstrap"]
            for x in rc.get("windows_with", []):        # the same windows in another stage's table, joined by window id
                more = {w["window"]: w for w in at(x["data"], x["windows"])}
                if any(w["window"] not in more or more[w["window"]]["positions"] != w["positions"] for w in W):
                    fails.append(f"findings {fid}: the windows of {x['data']} do not match those of {rc['data']}"); W = []; break
                W = [dict(w, kl_mean={**more[w["window"]]["kl_mean"], **w["kl_mean"]}) for w in W]
            if not W: continue
            for c in rc["checks"]:
                sel = [w for w in W if c.get("bucket") in (None, w["bucket"])]
                num = [w["positions"] * (w["kl_mean"][c["b"]] - (w["kl_mean"][c["a"]] if c.get("a") else 0.0)) for w in sel]
                den = [w["positions"] for w in sel]; G = len(sel); s = bt["seed"] & M; lim = ((1 << 64) - G) % G; reps = []
                for _ in range(bt["replicates"]):
                    n_ = d_ = 0.0
                    for _ in range(G):
                        while True:
                            s = (s + 0x9E3779B97F4A7C15) & M; z = s
                            z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M; z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M; z ^= z >> 31
                            if z >= lim: break
                        n_ += num[z % G]; d_ += den[z % G]
                    reps.append(n_ / d_)
                reps.sort()
                def q(p):
                    h = (len(reps) - 1) * p; i = int(h)
                    return reps[i] if i + 1 >= len(reps) else reps[i] + (reps[i + 1] - reps[i]) * (h - i)
                got = [sum(num) / sum(den), q(0.025), q(0.975)]; want = at(rc["data"], c["pointer"])
                if len(want) != 3 or any(abs(g - w) > 2e-9 for g, w in zip(got, want)):
                    fails.append(f"findings {fid}: {c['pointer']} recomputed {[round(g, 9) for g in got]} from the per-window table, {rc['data']} says {want}")
            continue
        else:
            fails.append(f"findings {fid}: unknown recompute kind {rc['kind']}"); continue
        if abs(got - f["result"]["value"]) > 1e-9: fails.append(f"findings {fid}: recomputed {got:.6f} from {rc.get('data') or rc.get('data_a')}, findings.json says {f['result']['value']:.6f}")
    return len(doc["findings"])


def check_build(kinds):
    """The site's sources (site/) pass tools/build.py --check, and docs/ and README.md are exactly what a fresh build
    produces; the README's run list states each run's kind."""
    import filecmp, shutil, tempfile
    tool = ROOT / "tools" / "build.py"
    if not tool.exists(): fails.append("tools/build.py missing"); return
    r = subprocess.run([sys.executable, "-B", str(tool), "--check"], capture_output=True, text=True, cwd=ROOT)
    if r.returncode: fails.append("tools/build.py --check: " + " | ".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
    tmp = Path(tempfile.mkdtemp(prefix="cuteafd-eval-build-"))
    try:
        out = tmp / "docs"
        r = subprocess.run([sys.executable, "-B", str(tool), "--out", str(out)], capture_output=True, text=True, cwd=ROOT)
        if r.returncode: fails.append("tools/build.py: " + " | ".join((r.stdout + r.stderr).strip().splitlines()[-6:])); return
        built = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
        have = {p.relative_to(ROOT / "docs").as_posix() for p in (ROOT / "docs").rglob("*") if p.is_file()}
        for x in sorted(built ^ have): fails.append(f"docs/{x} {'missing' if x in built else 'not produced by the build'}")
        for x in sorted(built & have):
            if not filecmp.cmp(out / x, ROOT / "docs" / x, shallow=False): fails.append(f"docs/{x}: differs from a fresh build (python3 tools/build.py)")
        if not filecmp.cmp(tmp / "README.md", ROOT / "README.md", shallow=False): fails.append("README.md: differs from a fresh build (python3 tools/build.py)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    t = (ROOT / "README.md").read_text()
    a, b = t.find("<!-- results:start -->"), t.find("<!-- results:end -->")
    if a < 0 or b < a: fails.append("README.md: results markers missing"); return
    for row in t[a:b].splitlines():
        m = re.match(r"\| \[[^\]]+\]\(results/([^)]+)\) \| (\w+) \|", row)
        if m and kinds.get(m.group(1)) != m.group(2):
            fails.append(f"README.md: {m.group(1)} shown as {m.group(2)}, RUN.json says {kinds.get(m.group(1))}")


def scan():
    hits = 0
    for p in files_under(ROOT):
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            fails.append(f"{rel(p)}: not UTF-8 text (binary files are not published)"); continue
        for n, line in enumerate(text.splitlines(), 1):
            for what, rx in FORBIDDEN:
                for m in rx.finditer(line):
                    if what == "e-mail" and m.group(0) == NOREPLY: continue
                    if what == "excluded benchmark" and rel(p).startswith(BENCH_SCOPE): continue
                    hits += 1
                    fails.append(f"{rel(p)}:{n}: {what}: {line.strip()[:160]}")
    return hits


def check_tails():
    tool = ROOT / "tools" / "kl_tails.py"
    if not tool.exists(): return
    r = subprocess.run([sys.executable, "-B", str(tool), "--check"], capture_output=True, text=True, cwd=ROOT)
    if r.returncode: fails.append("tools/kl_tails.py --check: " + " | ".join((r.stdout + r.stderr).strip().splitlines()))


def main(argv):
    quiet = "--quiet" in argv
    self_test()
    n = 0
    for mp in [ROOT / "MANIFEST.json"] + sorted((ROOT / "results").glob("*/MANIFEST.json")):
        if mp.exists(): n += check_manifest(mp)
        else: fails.append(f"{rel(mp)} missing")
    pages = check_site(); check_hashes()
    kinds = check_runs(); check_tails(); nf = check_findings(); check_build(kinds)
    files = len(files_under(ROOT)); hits = scan()
    if not quiet:
        print(f"self-test: {len(SELF_TEST)} cases; site pages: {pages}; manifests: {1 + len(list((ROOT / 'results').glob('*/MANIFEST.json')))} ({n} entries); files scanned: {files}; "
              f"findings checked: {nf}; runs: {', '.join(f'{k} ({v})' for k, v in kinds.items())}; content hits: {hits}")
    for f in fails: print("FAIL", f)
    print("OK" if not fails else f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
