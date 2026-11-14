#!/usr/bin/env python3
"""Writes each goal's `findings` list in next/site/runs/<run>.json from the findings' own `goal` fields.

  link_findings.py [RUN ...]   the finding is the source of truth for which goal it answers; run after adding
                              findings (only the named runs' index files are rewritten when runs are given)

Ids already listed under a goal that are not yet written in the new format (older published ids) are kept, after
the new ones, unless a new finding `replaces` them, so nothing listed is dropped.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
SITE = Path(__file__).resolve().parents[1] / "site"


def main():
    new, replaced = {}, set()
    for src in sorted((SITE / "findings").glob("*.json")):
        for f in json.loads(src.read_text()):
            new.setdefault((f["run"], f["goal"]), []).append(f["id"])
            replaced.update(f.get("replaces", []))
    ids = {i for v in new.values() for i in v} | replaced
    for src in sorted((SITE / "runs").glob("*.json")):
        if sys.argv[1:] and src.stem not in sys.argv[1:]:
            continue
        r = json.loads(src.read_text())
        for g in r["goals"]:
            mine = new.get((r["id"], g["id"]), [])
            g["findings"] = mine + [x for x in g["findings"] if x not in ids and x not in mine]
            if g["findings"]:
                g.pop("no_findings_reason", None)
            elif not g.get("no_findings_reason"):
                g["no_findings_reason"] = "pending"
        src.write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
