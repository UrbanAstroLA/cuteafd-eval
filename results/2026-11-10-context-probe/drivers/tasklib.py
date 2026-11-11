"""Shared by the generator, the driver and the analysis of the context probe (../PROTOCOL-DRAFT.md).
Standard library only: how an item becomes messages (one prompt, or the same records delivered as turns), and the
scoring rule. One definition of each, so the generator's token counts, the driver's requests and the analysis
agree.

Scoring rule: the last line of the reply's visible content that starts with "ANSWER:" must hold one JSON object.
A field is correct when its value equals the item's value (integers compared as integers, strings after
strip()). The score is correct fields / fields. No ANSWER line, unparseable JSON or an unfinished reply scores 0
of N and is counted in its own class, so format failures are never folded silently into wrong answers.
"""
from __future__ import annotations

import json
import re

TURN_NOTE = ("The records arrive in {parts} parts, one per message. After each part reply with exactly "
             "`ACK <part number>` and nothing else. The question follows the last part.")
ANSWER_RE = re.compile(r"^\s*ANSWER:\s*(.*\S)\s*$", re.M)


def single_content(item: dict) -> str:
    return item["preamble"] + "\n\n" + item["sep"].join(item["records"]) + "\n\n" + item["question"]


def single_messages(item: dict) -> list[dict]:
    return [{"role": "user", "content": single_content(item)}]


def split_parts(records: list[str], parts: int) -> list[list[str]]:
    """Contiguous groups, sizes differing by at most one record."""
    n = len(records)
    cuts = [round(k * n / parts) for k in range(parts + 1)]
    return [records[cuts[k]:cuts[k + 1]] for k in range(parts)]


def turn_user_contents(item: dict, parts: int) -> list[str]:
    """The user side of the as-turns delivery: `parts` record messages, then the question. The assistant side is
    whatever the engine replied (the driver sends it back unchanged)."""
    groups = split_parts(item["records"], parts)
    out = []
    for k, g in enumerate(groups, 1):
        head = f"Part {k} of {parts}:\n"
        if k == 1:
            head = item["preamble"] + "\n\n" + TURN_NOTE.format(parts=parts) + "\n\n" + head
        out.append(head + item["sep"].join(g))
    out.append(item["question"])
    return out


def extract_answer(content: str):
    """(object or None, class). Classes: ok, no_answer_line, bad_json, not_object."""
    hits = ANSWER_RE.findall(content or "")
    if not hits:
        return None, "no_answer_line"
    raw = hits[-1].strip().strip("`")
    try:
        obj = json.loads(raw)
    except ValueError:
        return None, "bad_json"
    if not isinstance(obj, dict):
        return None, "not_object"
    return obj, "ok"


def field_equal(want, got) -> bool:
    if isinstance(want, int):
        if isinstance(got, bool):
            return False
        if isinstance(got, (int, float)):
            return got == want
        if isinstance(got, str):
            try:
                return int(got.strip().replace(",", "")) == want
            except ValueError:
                return False
        return False
    return isinstance(got, str) and got.strip() == want


def score(answer: dict, content: str) -> dict:
    obj, cls = extract_answer(content)
    per = {k: bool(obj is not None and k in obj and field_equal(v, obj[k])) for k, v in answer.items()}
    return {"format": cls, "fields": len(answer), "correct": sum(per.values()), "per_field": per,
            "given": None if obj is None else {k: obj.get(k) for k in answer}}
