#!/usr/bin/env python3
"""Verify cuteafd-eval: manifests, published-copy hashes, result labels, and a content scan.

    python3 tools/verify.py            # everything
    python3 tools/verify.py --quiet    # failures and the final line only

Checks
  1. Every MANIFEST.json (the repository's and each results/<run>/ one): every listed file exists with that
     sha256, and every file under the manifest's directory is listed.
  2. docs/ (the Pages site): static HTML and CSS only, no scripts, external stylesheets, fonts or remote images; every
     link to another page or anchor of the site resolves.
  3. protocol/HASHES.json: every file marked identical to a frozen file has the frozen sha256.
  4. results/<run>/RUN.json: a kind (measurement, exploratory, withdrawn or check); runs that are not
     measurements open their README with a banner naming the kind; slots marked done have their files.
  5. README.md: the results section links measurement runs only, so exploratory or withdrawn numbers never
     sit in a comparison table with measured ones.
  0. A self-test of the content patterns (absolute paths after ":-", "=", quotes and brackets are caught; relative
     segments such as "humanevalplus/data/x" are not).
  7. Block Q tails: tools/kl_tails.py --check recomputes every results/<run>/q/tails/<panel>-tails.json whose
     per-position file is in the repository and requires byte-identical output.
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
    ("excluded benchmark", re.compile(J(["(?i)gp", "qa"]))),
    ("excluded project", re.compile(J(["(?i)tensor", "fold|aevo", r"nix|\bm", r"ia\b"]))),
    # an engine arm of the K4 protocol that is not published: its build tag, its author and its run labels
    ("unpublished arm", re.compile(J(["(?i)tf1", "17|ashh", r"art|\bT-", r"[rqtd]1"]))),
    ("attribution", re.compile(J(["(?i)clau", "de|anthro", "pic|co-author", "ed-by|generated with \\[", "|\U0001F916"]))),
    ("credential", re.compile(J([r"\bs", r"k-[A-Za-z0-9_\-]{12,}|\bh", r"f_[A-Za-z0-9]{20,}|\bgh[pousr]", r"_[A-Za-z0-9]{20,}"]))),
    ("credential", re.compile(J([r"github_", r"pat_|AK", r"IA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIV", r"ATE KEY|Bear", r"er [A-Za-z0-9._\-]{20,}"]))),
    ("GPU identifier", re.compile(J([r"\bGP", r"U-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}|(?i:serial)(?: number)?\W{1,4}\d{8,}"]))),
]
fails = []

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


def check_site():
    d = ROOT / "docs"
    if not d.is_dir(): fails.append("docs/ missing"); return 0
    pages = {p.name: p.read_text() for p in sorted(d.glob("*.html"))}
    if "index.html" not in pages: fails.append("docs/index.html missing")
    for name, html in pages.items():
        for what, rx in SITE_FORBIDDEN:
            if rx.search(html): fails.append(f"docs/{name}: {what} not allowed on the static site")
        for href in re.findall(r'href="([^"]+)"', html):
            if re.match(r"(?i)[a-z][a-z0-9+.-]*:", href): continue          # absolute link (repository files)
            page, _, frag = href.partition("#")
            target = pages.get(page or name)
            if target is None: fails.append(f"docs/{name}: link to missing page {href}"); continue
            if frag and f'id="{frag}"' not in target: fails.append(f"docs/{name}: link to missing anchor {href}")
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


def check_readme_links(kinds):
    t = (ROOT / "README.md").read_text()
    a, b = t.find("<!-- results:start -->"), t.find("<!-- results:end -->")
    if a < 0 or b < a: fails.append("README.md: results markers missing"); return
    for name in re.findall(r"results/([^/)\s`]+)", t[a:b]):
        if kinds.get(name) != "measurement":
            fails.append(f"README.md: results section cites {name} (kind {kinds.get(name)}); only measurement runs belong there")


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
    kinds = check_runs(); check_readme_links(kinds); check_tails()
    files = len(files_under(ROOT)); hits = scan()
    if not quiet:
        print(f"self-test: {len(SELF_TEST)} cases; site pages: {pages}; manifests: {1 + len(list((ROOT / 'results').glob('*/MANIFEST.json')))} ({n} entries); files scanned: {files}; "
              f"runs: {', '.join(f'{k} ({v})' for k, v in kinds.items())}; content hits: {hits}")
    for f in fails: print("FAIL", f)
    print("OK" if not fails else f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
