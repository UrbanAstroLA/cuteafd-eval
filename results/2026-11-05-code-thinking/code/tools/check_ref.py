#!/usr/bin/env python3
"""Run a project's hidden tests against its reference in the Block L sandbox (code_check.run_tests: CPU-only container,
no network). Standard library only.   check_ref.py <project dir>   (expects <dir>/reference/<pkg>/... and <dir>/tests/)"""
import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, "<run>/stage0/prompts/checkers")
import code_check  # noqa: E402
d = os.path.abspath(sys.argv[1]); ref = os.path.join(d, "reference")
files = {os.path.relpath(os.path.join(r, f), ref): open(os.path.join(r, f)).read()
         for r, _, fs in os.walk(ref) for f in fs if f.endswith(".py")}
res = code_check.run_tests(files, os.path.join(d, "tests"))
print(json.dumps({k: res.get(k) for k in ("tests", "passed", "failures", "errors", "all_pass", "exit_code")}))
if not res.get("all_pass"):
    print(res.get("stdout_tail", "")[-2500:])
