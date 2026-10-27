#!/usr/bin/env python3
"""JSON catalogue checker (Block L json, and optional for Block T). Needs `jsonschema` (in the CPU image).

Rule (fixed before any run):
  1. final_text(): text after the last "</think>" if the content contains one (see math_check.final_text).
  2. Strip surrounding whitespace. If the text is exactly one fenced block (```json ... ``` or ``` ... ```),
     unwrap it and record fenced=true. Nothing else is repaired or trimmed.
  3. json.loads the text. Failure -> status "parse_error" (records_valid counted as 0).
  4. Top level must be an array; its length must equal N (count_ok).
  5. Every element is validated against the record schema in prompts/authored/json_task.json
     (Draft 2020-12): records_valid = number of elements that validate.
  6. ids are exactly 1..len in order (ids_ok); sku values are unique (skus_unique).
  7. valid = parse ok AND array AND count_ok AND records_valid == N AND ids_ok AND skus_unique.
"""
import json
import re

from jsonschema import Draft202012Validator


def final_text(content):
    content = content or ""
    if "</think>" in content:
        return content.rsplit("</think>", 1)[1]
    return content


_FENCE = re.compile(r"\A```[a-zA-Z]*\n(.*)\n```\Z", re.S)


def check(content, n_expected, record_schema):
    t = final_text(content).strip()
    out = {"n_expected": n_expected, "fenced": False, "content_had_think_close": "</think>" in (content or "")}
    m = _FENCE.match(t)
    if m and "```" not in m.group(1):
        t, out["fenced"] = m.group(1), True
    try:
        doc = json.loads(t)
    except (json.JSONDecodeError, RecursionError) as e:
        out.update(status="parse_error", error=str(e)[:200], valid=False, records_valid=0, n_found=None)
        return out
    if not isinstance(doc, list):
        out.update(status="not_array", valid=False, records_valid=0, n_found=None)
        return out
    v = Draft202012Validator(record_schema)
    good, first_err = 0, None
    for i, rec in enumerate(doc):
        errs = list(v.iter_errors(rec))
        if not errs:
            good += 1
        elif first_err is None:
            first_err = f"record {i}: {errs[0].message[:160]}"
    ids = [r.get("id") if isinstance(r, dict) else None for r in doc]
    skus = [r.get("sku") if isinstance(r, dict) else None for r in doc]
    out.update(n_found=len(doc), count_ok=len(doc) == n_expected, records_valid=good,
               ids_ok=ids == list(range(1, len(doc) + 1)),
               skus_unique=len(set(map(str, skus))) == len(skus), first_error=first_err)
    out["valid"] = bool(out["count_ok"] and good == n_expected and out["ids_ok"] and out["skus_unique"])
    out["status"] = "valid" if out["valid"] else "invalid"
    return out
