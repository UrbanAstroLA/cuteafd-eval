#!/usr/bin/env python3
"""Block L code checker: extract the files from a reply, run the hidden pytest suite in a CPU-only sandbox.
Standard library only on the host; pytest runs inside a local image.

Rule (fixed before any run):
  1. final_text(): text after the last "</think>" if the content contains one.
  2. Extraction: every line matching FILE_RE (a "FILE: <path>" line, optionally preceded by markdown heading
     marks or bold markers) followed, after optional blank lines, by a fenced code block. The block body is
     the file. A later block for the same path replaces an earlier one. Kept only when the path is relative,
     has no "..", ends in ".py", and lies under the project package directory ("<package>/..."); others are
     listed in `ignored`.
  3. Sandbox: the kept files plus the project's tests/ (copied from prompts/L/code/<project>/tests) are
     written to a fresh directory and run with
        docker run --rm --network none --cpus 2 --memory 2g --pids-limit 256 --user UID:GID
          -e PYTHONDONTWRITEBYTECODE=1 -v SRC:/work:ro -v OUT:/out -w /work --entrypoint python3 IMAGE
          -m pytest -q -p no:cacheprovider --junitxml=/out/junit.xml tests
     with a 300 s wall limit (container killed on timeout). No GPU is passed in.
  4. Score: tests / passed / failed / errors / skipped from junit.xml; all_pass = tests > 0 and
     passed == tests. Collection errors (e.g. ImportError) count as errors with tests = 0 -> all_pass false.
"""
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

SANDBOX_IMAGE = "sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a"
TIMEOUT_S = 300
FILE_RE = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[ \t]*FILE:[ \t]*`?([^\s`*]+)`?[ \t]*(?:\*\*)?[ \t]*$",
                     re.M)
FENCE_RE = re.compile(r"(?:[ \t]*\n)*[ \t]*```[a-zA-Z0-9_+-]*[ \t]*\n(.*?)\n[ \t]*```", re.S)


def final_text(content):
    content = content or ""
    if "</think>" in content:
        return content.rsplit("</think>", 1)[1]
    return content


def extract_files(content, package):
    text = final_text(content)
    files, ignored = {}, []
    for m in FILE_RE.finditer(text):
        path = m.group(1).strip()
        fm = FENCE_RE.match(text, m.end() + 1) if m.end() < len(text) else None
        if fm is None:
            ignored.append({"path": path, "reason": "no fenced block after header"})
            continue
        p = Path(path)
        if p.is_absolute() or ".." in p.parts or p.suffix != ".py" or p.parts[0] != package:
            ignored.append({"path": path, "reason": "outside package or not .py"})
            continue
        files[str(p)] = fm.group(1) + "\n"
    return files, ignored


def run_tests(files, tests_dir, image=SANDBOX_IMAGE, keep_dir=None):
    work = Path(tempfile.mkdtemp(prefix="codecheck-"))
    src, out = work / "src", work / "out"
    try:
        src.mkdir()
        out.mkdir()
        for rel, body in files.items():
            dst = src / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(body)
        shutil.copytree(tests_dir, src / "tests")
        name = f"codecheck-{uuid.uuid4().hex[:12]}"
        cmd = ["docker", "run", "--rm", "--name", name, "--network", "none", "--cpus", "2", "--memory", "2g",
               "--pids-limit", "256", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "PYTHONDONTWRITEBYTECODE=1",
               "-v", f"{src}:/work:ro", "-v", f"{out}:/out", "-w", "/work", "--entrypoint", "python3", image,
               "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=/out/junit.xml", "tests"]
        res = {"timeout": False}
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
            res["exit_code"] = p.returncode
            res["stdout_tail"] = p.stdout[-3000:]
            res["stderr_tail"] = p.stderr[-1500:]
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True)
            res.update(timeout=True, exit_code=None)
        j = out / "junit.xml"
        if j.exists():
            root = ET.parse(j).getroot()
            suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
            tot = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
            res.update(tot)
            res["passed"] = tot["tests"] - tot["failures"] - tot["errors"] - tot["skipped"]
        else:
            res.update(tests=0, failures=0, errors=1, skipped=0, passed=0)
        res["all_pass"] = bool(res["tests"] > 0 and res["passed"] == res["tests"])
        if keep_dir:
            shutil.copytree(work, keep_dir, dirs_exist_ok=True)
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check(content, project, package, tests_dir, image=SANDBOX_IMAGE):
    files, ignored = extract_files(content, package)
    out = {"files": sorted(files), "ignored": ignored, "content_had_think_close": "</think>" in (content or "")}
    if not files:
        out.update(status="no_files", all_pass=False, tests=0, passed=0)
        return out
    out.update(run_tests(files, tests_dir, image))
    out["status"] = "all_pass" if out["all_pass"] else ("timeout" if out.get("timeout") else "fail")
    return out
