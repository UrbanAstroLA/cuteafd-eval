#!/usr/bin/env python3
"""Self-test of the three Block L checkers. Run on the host (stdlib + jsonschema; docker for the code sandbox):
    python3 prompts/checkers/selftest.py
Writes prompts/selftest/checkers_selftest.json and exits non-zero on any failed expectation.
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTS = HERE.parent
sys.path.insert(0, str(HERE))
import code_check  # noqa: E402
import json_check  # noqa: E402
import math_check  # noqa: E402

MATH500 = Path("<datasets>/2026-10-26-engine-compare/math500/test.jsonl")
PROJECTS = {"minicalc": "minicalc", "kvstore": "kvstore", "graphkit": "graphkit", "csvreport": "csvreport"}
failures = []


def expect(name, cond, detail=None):
    if not cond:
        failures.append({"case": name, "detail": detail})
    return bool(cond)


def math_tests():
    rows = [json.loads(line) for line in MATH500.open()]
    ref = sum(math_check.is_equiv(math_check.last_boxed(r["solution"]), r["answer"]) for r in rows)
    expect("math: all 500 reference solutions match", ref == len(rows), ref)
    pos = [("\\dfrac{1}{2}", "\\frac12"), ("0.5", "\\frac{1}{2}"), ("1,000", "1000"), ("\\text{(C)}", "(C)"),
           ("x = 5", "5"), ("10\\%", "10"), ("90^\\circ", "90"), ("3.0", "3"), ("-\\frac{3}{4}", "-0.75"),
           ("\\left( 3, \\frac{\\pi}{2} \\right)", "(3,\\frac{\\pi}{2})"), ("\\$18.90", "18.90"), ("3/4", "\\frac34")]
    neg = [("2", "3"), ("\\sqrt{2}", "2"), ("(1,2)", "(2,1)"), ("", "0"), ("12,34", "1234")]
    res = {"reference_solutions_match": f"{ref}/{len(rows)}", "equiv_cases": [], "non_equiv_cases": []}
    for a, b in pos:
        res["equiv_cases"].append([a, b, expect(f"math equiv {a!r} {b!r}", math_check.is_equiv(a, b))])
    for a, b in neg:
        res["non_equiv_cases"].append([a, b, expect(f"math non-equiv {a!r} {b!r}", not math_check.is_equiv(a, b))])
    c = math_check.check("reasoning text</think>So the answer is $\\boxed{\\frac{7}{2}}$.", "\\frac72")
    expect("math: answer after </think> counted", c["correct"] and c["content_had_think_close"], c)
    c = math_check.check("The answer is \\boxed{4} ... wait, actually \\boxed{5}.", "5")
    expect("math: last boxed wins", c["correct"], c)
    c = math_check.check("No box here: 5", "5")
    expect("math: no boxed answer -> no_answer", c["status"] == "no_answer" and not c["correct"], c)
    c = math_check.check("\\boxed{\\frac{a}{b+\\{c\\}}}", "x")
    expect("math: nested braces extracted", c["extracted"] == "\\frac{a}{b+\\{c\\}}", c)
    return res


def json_tests():
    task = json.loads((PROMPTS / "authored" / "json_task.json").read_text())
    schema = task["record_schema"]
    base = task["example_record"]
    recs = []
    for i in range(1, 6):
        r = copy.deepcopy(base)
        r["id"], r["sku"] = i, f"ABC-{i:05d}"
        recs.append(r)
    good = "\n".join(["[", ",\n".join(json.dumps(r) for r in recs), "]"])
    cases = {
        "valid": (good, 5, True),
        "valid_fenced": ("```json\n" + good + "\n```", 5, True),
        "valid_after_think": ("planning...</think>\n" + good, 5, True),
        "wrong_count": (good, 6, False),
        "trailing_prose": (good + "\nHope this helps!", 5, False),
        "bad_sku": (good.replace("ABC-00003", "abc-3"), 5, False),
        "dup_sku": (good.replace("ABC-00004", "ABC-00003"), 5, False),
        "ids_out_of_order": (good.replace('"id": 2,', '"id": 7,'), 5, False),
        "extra_field": (good.replace('"in_stock": true', '"in_stock": true, "color": "red"', 1), 5, False),
        "truncated": (good[:-40], 5, False),
        "object_not_array": (json.dumps({"items": recs}), 5, False),
    }
    res = {}
    for name, (text, n, want) in cases.items():
        r = json_check.check(text, n, schema)
        res[name] = {"valid": r["valid"], "status": r["status"], "expected_valid": want}
        expect(f"json {name}", r["valid"] == want, r)
    return res


def reply_from_reference(project, pkg):
    ref = PROMPTS / "L" / "code" / project / "reference"
    parts = ["Here is the implementation.\n"]
    for f in sorted(ref.rglob("*.py")):
        rel = f.relative_to(ref).as_posix()
        parts.append(f"### FILE: {rel}\n```python\n{f.read_text().rstrip()}\n```\n")
    return "\n".join(parts)


def code_tests():
    res = {}
    for project, pkg in PROJECTS.items():
        tests = PROMPTS / "L" / "code" / project / "tests"
        reply = reply_from_reference(project, pkg)
        r = code_check.check(reply, project, pkg, tests)
        res[f"{project}/reference"] = {k: r.get(k) for k in ("status", "tests", "passed", "failures", "errors",
                                                             "files")}
        expect(f"code {project}: reference passes all tests", r["all_pass"], r)
        # think-close prefix (vLLM thinking-off form) and bold header variant
        r2 = code_check.check("thinking...</think>\n" + reply.replace("### FILE: ", "**FILE: ").replace(
            ".py\n```", ".py**\n```"), project, pkg, tests)
        res[f"{project}/reference_bold_after_think"] = {"status": r2["status"], "passed": r2.get("passed")}
        expect(f"code {project}: bold headers after </think> pass", r2["all_pass"], r2)
        # broken: drop the last file -> import error
        cut = reply.rsplit("### FILE:", 1)[0]
        r3 = code_check.check(cut, project, pkg, tests)
        res[f"{project}/missing_file"] = {"status": r3["status"], "passed": r3.get("passed"),
                                          "tests": r3.get("tests"), "errors": r3.get("errors")}
        expect(f"code {project}: missing file fails", not r3["all_pass"], r3)
    r4 = code_check.check("I cannot do that.", "minicalc", "minicalc", PROMPTS / "L" / "code" / "minicalc" / "tests")
    expect("code: no files -> no_files", r4["status"] == "no_files", r4)
    r5 = code_check.check("### FILE: ../evil.py\n```python\nprint(1)\n```\n### FILE: /etc/x.py\n```python\n```\n",
                          "minicalc", "minicalc", PROMPTS / "L" / "code" / "minicalc" / "tests")
    expect("code: paths outside package ignored", r5["status"] == "no_files" and len(r5["ignored"]) == 2, r5)
    res["no_files"], res["outside_paths"] = r4["status"], [i["path"] for i in r5["ignored"]]
    return res


def main():
    out = {"math": math_tests(), "json": json_tests(), "code": code_tests(),
           "sandbox_image": code_check.SANDBOX_IMAGE, "failures": failures}
    dst = PROMPTS / "selftest" / "checkers_selftest.json"
    dst.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"failures": failures}, indent=1)[:4000])
    print("PASS" if not failures else f"FAIL ({len(failures)})")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
