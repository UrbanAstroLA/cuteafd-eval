#!/usr/bin/env python3
"""Derives, for every single-message request of the four passes, counts that describe what the reasoning text was
made of. Reads the saved reply texts (not published) and the items; writes endings.csv (counts only, no text).

  make_endings.py <run folder> <out.csv>

Per request
  lines            reasoning lines after strip(), empty lines dropped
  chars            characters on those lines
  walk_lines       lines that carry a record of the prompt (definition per family below)
  walk_chars       characters on those lines
  step_lines       walk lines whose record is the one that follows the previous walk line's record in the prompt
  step_chars       characters on those lines
  reached          highest record position (1-based) among step lines, 0 if none
  records          records in the prompt
  repeat_chars     characters on lines of 8 or more characters that already occurred earlier in the same reasoning
  run_start_chars  characters before the first run of 20 or more consecutive step lines; empty if there is no such run
  answers_before   join only: how many of the item's correct docks occur as text in the reasoning before that run
                   (in the whole reasoning if there is no run); empty for the other families, whose answers are
                   integers that also occur by coincidence

A line carries a record when, after leading list marks and surrounding quotes are removed,
  join    it equals a record of the prompt
  ledger  it starts with a five-digit sequence number that exists in the prompt (the rest of the line is free, so
          a shortened or annotated copy of a ledger line counts)
  trace   it equals the `def` line of a record
"""
import csv, glob, gzip, json, re, sys

LEAD = re.compile(r"^[\s\-\*•>]+")
SEQ = re.compile(r"^(\d{5})\b")


def norm(l):
    return LEAD.sub("", l).strip().strip('"').strip()


def describe(item, reasoning):
    fam, recs = item["family"], item["records"]
    if fam == "join":
        pos = {}
        for i, r in enumerate(recs, 1):
            pos.setdefault(r.strip(), i)
        def where(l):
            return pos.get(l, 0)
    elif fam == "ledger":
        n = len(recs)
        def where(l):
            m = SEQ.match(l)
            return int(m.group(1)) if m and 1 <= int(m.group(1)) <= n else 0
    else:
        pos = {}
        for i, r in enumerate(recs, 1):
            pos.setdefault(r.split("\n")[0].strip(), i)
        def where(l):
            return pos.get(l, 0)
    o = dict(lines=0, chars=0, walk_lines=0, walk_chars=0, step_lines=0, step_chars=0, reached=0, records=len(recs),
             repeat_chars=0)
    seen, prev, run, run_at, run_head, start, head = set(), 0, 0, 0, 0, None, []
    for raw in reasoning.split("\n"):
        s = raw.strip()
        if not s:
            continue
        before = o["chars"]
        if start is None:
            head.append(s)
        o["lines"] += 1
        o["chars"] += len(s)
        if len(s) >= 8 and s in seen:
            o["repeat_chars"] += len(s)
        seen.add(s)
        w = where(norm(s))
        if w:
            o["walk_lines"] += 1
            o["walk_chars"] += len(s)
            if w == prev + 1:
                o["step_lines"] += 1
                o["step_chars"] += len(s)
                o["reached"] = max(o["reached"], w)
                if run == 0:
                    run_at, run_head = before, len(head) - 1
                run += 1
                if run == 20 and start is None:
                    start, head = run_at, head[:run_head]
            else:
                run = 0
            prev = w
        else:
            run = 0
    o["run_start_chars"] = "" if start is None else start
    o["answers_before"] = sum(str(v) in "\n".join(head) for v in item["answer"].values()) if fam == "join" else ""
    return o


def main(run, out):
    rows = []
    for f in ("samples.csv", "samples-reference.csv", "samples-extension.csv"):
        rows += [r for r in csv.DictReader(open(f"{run}/analysis/{f}", newline="")) if r["cell"] == "single" and r["final"] == "1"]
    items, w = {}, None
    with open(out, "w", newline="") as fh:
        for r in rows:
            k = (r["item"], r["length"])
            if k not in items:
                items[k] = json.load(open(f"{run}/items/measured/{r['family']}/{r['item']}-{r['length']}.json"))
            g = glob.glob(f"{run}/tasks/{r['arm']}/m0/{r['pass']}/texts/{r['item']}-{r['length']}.*.json.gz")
            assert len(g) == 1, g
            t = json.load(gzip.open(g[0], "rt"))["turns"][0]
            assert len(t["reasoning"]) == int(r["reasoning_chars"]) and len(t["content"]) == int(r["content_chars"])
            row = {"arm": r["arm"], "pass": r["pass"], "item": r["item"], "family": r["family"], "length": r["length"],
                   "seed": r["seed"]}
            row.update(describe(items[k], t["reasoning"]))
            if w is None:
                w = csv.DictWriter(fh, fieldnames=list(row), lineterminator="\n")
                w.writeheader()
            w.writerow(row)
    print(len(rows), "rows")


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
