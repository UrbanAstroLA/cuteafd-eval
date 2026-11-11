"""Exploratory reading of the `ledger` family (NOT part of the frozen protocol, PROTOCOL.md section 13).

1. Paired arm differences on `ledger` alone (field score, item as the unit, 95% interval from resampling items).
2. What kind of wrong answer each wrong field is, on stop-finished replies: the value the reply gave is compared
   with the values the bin's own events produce if one event is left out, two are left out, the events stop early,
   or the last `set` is skipped. Anything else is `digit` (off by one digit times a power of ten) or `other`.
   Heuristic: a wrong value can match a class by coincidence.

Usage: ledger_errors.py [--set measured] [--arms anchor hqa compact]
"""
import argparse
import itertools
import json
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parent.parent
LENGTHS = ("4k", "16k", "64k", "128k")


def fold(events):
    q = 0
    for op, n in events:
        q = n if op == "set" else q + n if op == "add" else q - n
    return q


def bin_events(item):
    ev = {b: [] for b in item["answer"]}
    for rec in item["records"]:
        _, b, op, n = rec.split()
        if b in ev:
            ev[b].append((op, int(n)))
    return ev


def classify(events, want, got):
    if not isinstance(got, int) or isinstance(got, bool):
        return "no value"
    last_set = max(i for i, e in enumerate(events) if e[0] == "set")
    live = list(range(last_set + 1, len(events)))
    for i in live:
        if fold(events[:i] + events[i + 1:]) == got:
            return "one dropped"
    for i, j in itertools.combinations(live, 2):
        if fold([e for k, e in enumerate(events) if k not in (i, j)]) == got:
            return "two dropped"
    for k in range(1, len(events)):
        if fold(events[:k]) == got:
            return "stopped early"
    if last_set > 0 and fold(events[:last_set] + events[last_set + 1:]) == got:
        return "set skipped"
    d = abs(got - want)
    while d and d % 10 == 0:
        d //= 10
    return "digit" if 0 < d < 10 else "other"


def load(arm, tag, unit_dir, items):
    out = {}
    p = RUN / "tasks" / arm / tag / unit_dir / "requests.jsonl"
    for line in open(p):
        r = json.loads(line)
        if r["family"] == "ledger" and r["final"]:
            out[(r["item"], r["length"])] = r
    return out


def interval(vals, n=10000, seed=20261111):
    rng = random.Random(seed)
    m = len(vals)
    means = sorted(sum(vals[rng.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return sum(vals) / m, means[int(0.025 * n)], means[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="measured")
    ap.add_argument("--tag", default="m0")
    ap.add_argument("--arms", nargs="+", default=["anchor", "hqa", "compact"])
    a = ap.parse_args()
    items = {}
    for f in (RUN / "items" / a.set / "ledger").glob("*.json"):
        it = json.load(open(f))
        items[(it["id"], it["length"])] = it
    units = {"single": ["single-rep0", "single-rep1"], "turns": ["turns-p8-rep0"]}
    data = {arm: {u: load(arm, a.tag, u, items) for us in units.values() for u in us} for arm in a.arms}

    def item_score(arm, us, key):
        return sum(data[arm][u][key]["score"]["correct"] / data[arm][u][key]["score"]["fields"]
                   if data[arm][u][key]["finish_class"] == "stop" else 0.0 for u in us) / len(us)

    ids = sorted({k[0] for k in items})
    for mode, us in units.items():
        print(f"ledger field score, {mode} ({len(us)} pass(es)), paired difference b - a [95%], {len(ids)} items")
        for x, y in itertools.combinations(a.arms, 2):
            for L in LENGTHS:
                d = [item_score(y, us, (i, L)) - item_score(x, us, (i, L)) for i in ids]
                m, lo, hi = interval(d)
                print(f"  {y:>7} - {x:<7} {L:>4}: {m:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    print()
    classes = ["one dropped", "two dropped", "stopped early", "set skipped", "digit", "other", "no value"]
    table = []
    print("wrong fields on stop-finished ledger replies, by kind (unfinished replies listed apart)")
    print(f"{'arm':>8} {'unit':>14} {'len':>5} {'fields':>6} {'wrong':>5} " + " ".join(f"{c:>13}" for c in classes)
          + f" {'unfinished':>10}")
    for arm in a.arms:
        for u in [u for us in units.values() for u in us]:
            for L in LENGTHS:
                n = wrong = unfinished = 0
                cnt = dict.fromkeys(classes, 0)
                for i in ids:
                    r = data[arm][u][(i, L)]
                    if r["finish_class"] != "stop":
                        unfinished += 1
                        continue
                    it = items[(i, L)]
                    ev = bin_events(it)
                    given = r["score"].get("given") or {}
                    for b, want in it["answer"].items():
                        n += 1
                        if r["score"]["per_field"].get(b):
                            continue
                        wrong += 1
                        cnt[classify(ev[b], want, given.get(b))] += 1
                print(f"{arm:>8} {u:>14} {L:>5} {n:>6} {wrong:>5} " + " ".join(f"{cnt[c]:>13}" for c in classes)
                      + f" {unfinished:>10}")
                table.append({"arm": arm, "pass": u, "length": L, "fields": n, "wrong": wrong, "kinds": cnt,
                              "unfinished": unfinished})
    out = Path(__file__).resolve().parent / "ledger_errors.json"
    out.write_text(json.dumps({
        "about": "exploratory reading, not part of the frozen protocol: wrong answer fields on stop-finished "
                 "`ledger` replies, by the kind of arithmetic slip the given value matches (heuristic: a wrong "
                 "value can match a kind by coincidence)", "set": a.set, "rows": table}, indent=1) + "\n")


if __name__ == "__main__":
    main()
