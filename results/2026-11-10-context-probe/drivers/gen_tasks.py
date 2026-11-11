#!/usr/bin/env python3
"""Build the graded long-context items (../PROTOCOL-DRAFT.md, layers 2 and 3). CPU only; needs `tokenizers`.

An item is a fixed set of records that carry the answer ("signal"), near-miss records that share all but one
character of a queried key ("confusers"), a question with N fields and its exact answer. The same item is rendered
at every length: signal, confusers, question and answer are byte-identical, and only the number of distractor
records between them changes. Length is therefore a pure dilution dial - same work, more look-alike context - and
every item is its own control across lengths as well as across engine configurations.

Families:
  ledger  time-ordered stock events (set / add / take); field = final quantity of a bin. A field needs every
          event of that bin since its last `set`, wherever they sit.
  join    three record kinds in no order (courier->parcel, parcel->hub, hub->dock); field = the dock a courier's
          parcel ships from. A field needs three keyed lookups at unrelated depths.
  trace   a Python module of small pure functions; field = the value of one call. A field needs a call chain
          followed through functions scattered across the file.

Every rendered item is checked by an oracle that re-derives the answer from the rendered text alone (parsing the
lines, or executing the module), so a rendering or ordering mistake cannot ship as a wrong key.

  gen_tasks.py --out ../items --items 20 [--lengths 4k 16k 64k 128k] [--families ledger join trace]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasklib as T  # noqa: E402

TOKENIZER = Path("<hf-hub>/models--brandonmusic--GLM-5.3-Flash-tr3-4bpw/snapshots/"
                 "a5fee929cf4888b1824323e33e8a19b60129e025/tokenizer.json")
TOKENIZER_SHA256 = "19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d"
# content tokens (the user text, before the chat template); 128k leaves 4,096 under 131,072 for template + slack
LENGTHS = {"4k": 4_096, "16k": 16_384, "64k": 65_536, "128k": 126_976}
TOLERANCE = 0.0025
FAMILIES = ("ledger", "join", "trace")
ITEM_SEED_BASE = 2_026_111_000          # + family index * 10,000 + item index
UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no I O 0 1
LOWER = "abcdefghjkmnpqrstuvwxyz23456789"
DEFAULTS = {
    "ledger": {"fields": 8, "ops_min": 3, "ops_max": 6, "reset_prob": 0.3, "confusers": 3},
    "join": {"fields": 8, "confusers": 3},
    "trace": {"fields": 8, "depth": 4, "branch_prob": 0.35, "mod": 97},
}


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def new_id(rng, used, shape, alphabet=UPPER):
    """shape: e.g. "C-#####" - every # becomes a random character."""
    while True:
        s = "".join(rng.choice(alphabet) if c == "#" else c for c in shape)
        if s not in used:
            used.add(s)
            return s


def near_miss(rng, used, s, first, alphabet=UPPER):
    """A new id equal to s except at one position >= first."""
    while True:
        i = rng.randrange(first, len(s))
        if s[i] in "-_":
            continue
        t = s[:i] + rng.choice(alphabet) + s[i + 1:]
        if t not in used:
            used.add(t)
            return t


class Stream:
    """A distractor generator whose first n records can be taken repeatedly (the sets are nested by length)."""

    def __init__(self, gen):
        self.gen, self.buf = gen, []

    def take(self, n):
        while len(self.buf) < n:
            self.buf.append(next(self.gen))
        return self.buf[:n]


# --- ledger -----------------------------------------------------------------------------------------------------
LEDGER_PREAMBLE = ("Below is a stock ledger. Each line is one event: a sequence number, a bin, and an operation. "
                   "Lines are in time order. `set N` replaces the bin's quantity with N, `add N` increases it by N, "
                   "`take N` decreases it by N. A question follows the ledger.")


def ledger_ops(rng, n, reset_prob):
    qty = rng.randint(100, 9999)
    ops = [("set", qty)]
    for _ in range(n - 1):
        r = rng.random()
        if r < reset_prob:
            qty = rng.randint(100, 9999)
            ops.append(("set", qty))
        elif r < reset_prob + (1 - reset_prob) / 2 or qty < 2:
            k = rng.randint(1, 99)
            qty += k
            ops.append(("add", k))
        else:
            k = rng.randint(1, min(99, qty))
            qty -= k
            ops.append(("take", k))
    return ops, qty


def make_ledger(seed, p):
    rs, used = random.Random(f"{seed}:signal"), set()
    fixed, answer, evidence = [], {}, {}
    for _ in range(p["fields"]):
        b = new_id(rs, used, "###-###")
        ops, qty = ledger_ops(rs, rs.randint(p["ops_min"], p["ops_max"]), p["reset_prob"])
        us = sorted(rs.random() for _ in ops)
        fixed += [(u, f"{b} {op} {k}", b) for u, (op, k) in zip(us, ops)]
        answer[b] = qty
        for _ in range(p["confusers"]):
            c = near_miss(rs, used, b, 0)
            cops, _ = ledger_ops(rs, rs.randint(2, 4), p["reset_prob"])
            fixed += [(u, f"{c} {op} {k}", None) for u, (op, k) in zip(sorted(rs.random() for _ in cops), cops)]

    def distractors():
        rd, live, qty = random.Random(f"{seed}:distractor"), [], {}
        while True:
            if not live or rd.random() < 0.3:
                b = new_id(rd, used, "###-###")
                live.append(b)
                qty[b] = rd.randint(100, 9999)
                yield f"{b} set {qty[b]}"
            else:
                b = rd.choice(live)
                if rd.random() < 0.5 or qty[b] < 2:
                    k = rd.randint(1, 99)
                    qty[b] += k
                    yield f"{b} add {k}"
                else:
                    k = rd.randint(1, min(99, qty[b]))
                    qty[b] -= k
                    yield f"{b} take {k}"

    keys = list(answer)
    question = ("Question: what is the final quantity in each of these bins?\n" + ", ".join(keys) + "\n\n"
                "Work it out, then finish your reply with one line in exactly this form - a JSON object with one "
                "key per bin and integer values:\nANSWER: {" + ", ".join(f'"{k}": <quantity>' for k in keys) + "}")
    return {"preamble": LEDGER_PREAMBLE, "fixed": fixed, "stream": Stream(distractors()), "question": question,
            "answer": answer, "ordered": True, "sep": "\n"}


def oracle_ledger(item):
    qty = {}
    for i, line in enumerate(item["records"]):
        seq, b, op, k = line.split()
        assert int(seq) == i + 1, "sequence numbers not consecutive"
        k = int(k)
        qty[b] = k if op == "set" else qty[b] + k if op == "add" else qty[b] - k
        assert qty[b] >= 0
    return {b: qty[b] for b in item["answer"]}


# --- join -------------------------------------------------------------------------------------------------------
JOIN_PREAMBLE = ("Below are dispatch records of three kinds, in no particular order: `courier C carries parcel P`, "
                 "`parcel P routes via hub H`, `hub H ships from dock D`. Each courier carries exactly one parcel, "
                 "each parcel routes via exactly one hub, and each hub ships from exactly one dock. A question "
                 "follows the records.")


def join_chain(rng, used, courier=None, parcel=None, hub=None):
    c = courier or new_id(rng, used, "C-#####")
    p = parcel or new_id(rng, used, "P-#####")
    h = hub or new_id(rng, used, "H-####")
    d = new_id(rng, used, "D-####")
    return c, d, [f"courier {c} carries parcel {p}", f"parcel {p} routes via hub {h}", f"hub {h} ships from dock {d}"]


def make_join(seed, p):
    rs, used = random.Random(f"{seed}:signal"), set()
    fixed, answer = [], {}
    for _ in range(p["fields"]):
        c, d, lines = join_chain(rs, used)
        answer[c] = d
        fixed += [(rs.random(), ln, c) for ln in lines]
        parcel, hub = lines[0].split()[-1], lines[1].split()[-1]
        variants = [{"courier": near_miss(rs, used, c, 2)}, {"parcel": near_miss(rs, used, parcel, 2)},
                    {"hub": near_miss(rs, used, hub, 2)}]
        for v in variants[:p["confusers"]]:
            fixed += [(rs.random(), ln, None) for ln in join_chain(rs, used, **v)[2]]

    def distractors():
        rd = random.Random(f"{seed}:distractor")
        while True:
            block = [ln for _ in range(64) for ln in join_chain(rd, used)[2]]
            rd.shuffle(block)
            yield from block

    keys = list(answer)
    question = ("Question: from which dock does the parcel carried by each of these couriers ship?\n"
                + ", ".join(keys) + "\n\nWork it out, then finish your reply with one line in exactly this form - "
                "a JSON object with one key per courier and the dock as a string:\nANSWER: {"
                + ", ".join(f'"{k}": "<dock>"' for k in keys) + "}")
    return {"preamble": JOIN_PREAMBLE, "fixed": fixed, "stream": Stream(distractors()), "question": question,
            "answer": answer, "ordered": False, "sep": "\n"}


def oracle_join(item):
    maps = {"courier": {}, "parcel": {}, "hub": {}}
    for line in item["records"]:
        w = line.split()
        assert w[1] not in maps[w[0]], f"duplicate key {w[1]}"
        maps[w[0]][w[1]] = w[-1]
    return {c: maps["hub"][maps["parcel"][maps["courier"][c]]] for c in item["answer"]}


# --- trace ------------------------------------------------------------------------------------------------------
TRACE_PREAMBLE = ("Below is a Python module. Every function is pure and takes one integer. A question follows the "
                  "module.")


def fn_leaf(rng, name, m):
    return f"def {name}(x):\n    return (x * {rng.randint(2, 9)} + {rng.randint(1, 20)}) % {m}"


def fn_call(rng, name, callee, m):
    return (f"def {name}(x):\n    return ({callee}(x + {rng.randint(1, 9)}) * {rng.randint(2, 7)} + "
            f"{rng.randint(1, 20)}) % {m}")


def fn_branch(rng, name, c1, c2, m):
    return (f"def {name}(x):\n    if x % {rng.choice((2, 3))} == 0:\n"
            f"        return ({c1}(x + {rng.randint(1, 9)}) + {rng.randint(1, 20)}) % {m}\n"
            f"    return ({c2}(x * {rng.randint(2, 5)}) + {rng.randint(1, 20)}) % {m}")


def make_trace(seed, p):
    rs, used, m = random.Random(f"{seed}:signal"), set(), p["mod"]
    fixed, calls = [], []
    for _ in range(p["fields"]):
        names = [new_id(rs, used, "fn_#####", LOWER) for _ in range(p["depth"])]
        twins = [near_miss(rs, used, n, 3, LOWER) for n in names]   # look-alike leaves; a branch may call one
        arg = rs.randint(1, 30)
        key = f"{names[0]}({arg})"
        for i, n in enumerate(names):
            if i == p["depth"] - 1:
                src = fn_leaf(rs, n, m)
            elif rs.random() < p["branch_prob"]:
                pair = [names[i + 1], twins[i + 1]]
                rs.shuffle(pair)
                src = fn_branch(rs, n, pair[0], pair[1], m)
            else:
                src = fn_call(rs, n, names[i + 1], m)
            fixed.append((rs.random(), src, key))
        fixed += [(rs.random(), fn_leaf(rs, t, m), None) for t in twins]
        calls.append(key)
    ns: dict = {}
    exec("\n\n".join(src for _, src, _ in fixed), ns)                 # our own generated code, pure integer functions
    answer = {k: eval(k, ns) for k in calls}

    def distractors():
        rd, made = random.Random(f"{seed}:distractor"), []
        while True:
            n = new_id(rd, used, "fn_#####", LOWER)
            r = rd.random()
            if len(made) < 2 or r < 0.3:
                src = fn_leaf(rd, n, m)
            elif r < 0.8:
                src = fn_call(rd, n, rd.choice(made), m)       # only earlier functions: any prefix is a valid module
            else:
                src = fn_branch(rd, n, rd.choice(made), rd.choice(made), m)
            made.append(n)
            yield src

    question = ("Question: what does each of these calls return?\n" + ", ".join(calls) + "\n\n"
                "Work it out, then finish your reply with one line in exactly this form - a JSON object with one "
                "key per call and integer values:\nANSWER: {" + ", ".join(f'"{k}": <value>' for k in calls) + "}")
    return {"preamble": TRACE_PREAMBLE, "fixed": fixed, "stream": Stream(distractors()), "question": question,
            "answer": answer, "ordered": False, "sep": "\n\n"}


def oracle_trace(item):
    ns: dict = {}
    exec(item["sep"].join(item["records"]), ns)
    return {k: eval(k, ns) for k in item["answer"]}


MAKE = {"ledger": make_ledger, "join": make_join, "trace": make_trace}
ORACLE = {"ledger": oracle_ledger, "join": oracle_join, "trace": oracle_trace}


# --- rendering --------------------------------------------------------------------------------------------------
def render(base, seed, length_name, n_distractors):
    """Merge the fixed records (at their own fractional positions) with the first n distractors. Time-ordered
    families keep both orders (distractors evenly spaced); the others place distractors at random positions drawn
    per length."""
    d = base["stream"].take(n_distractors)
    if base["ordered"]:
        du = [(k + 0.5) / max(1, len(d)) for k in range(len(d))]
    else:
        rp = random.Random(f"{seed}:place:{length_name}")
        du = [rp.random() for _ in d]
    merged = sorted([(u, 0, i, text, tag) for i, (u, text, tag) in enumerate(base["fixed"])]
                    + [(u, 1, i, text, None) for i, (u, text) in enumerate(zip(du, d))])
    records = [m[3] for m in merged]
    if base["ordered"]:
        records = [f"{i + 1:05d} {r}" for i, r in enumerate(records)]
    # where each field's evidence sits, as a fraction of the record text (0 = start, 1 = just before the question)
    total = sum(len(r) for r in records) or 1
    evidence, at = {k: [] for k in base["answer"]}, 0
    for r, m in zip(records, merged):
        if m[4] is not None:
            evidence[m[4]].append(round(at / total, 4))
        at += len(r)
    return {"preamble": base["preamble"], "records": records, "sep": base["sep"], "question": base["question"],
            "answer": base["answer"], "evidence_frac": evidence, "distractors": n_distractors,
            "fixed_records": len(base["fixed"])}


def fit(base, seed, length_name, target, count):
    """Choose the distractor count that puts the single-prompt content within TOLERANCE of the target (or within one
    record of it, where a record is larger than that)."""
    lo = count(T.single_content(render(base, seed, length_name, 0)))
    if lo > target * (1 + TOLERANCE):
        sys.exit(f"fixed records alone are {lo} tokens, over the {length_name} target")
    probe = 200
    per = (count(T.single_content(render(base, seed, length_name, probe))) - lo) / probe
    slack = max(target * TOLERANCE, per)        # a record is the smallest step (a trace function is ~30 tokens)
    n = max(0, round((target - lo) / per))
    for _ in range(12):
        item = render(base, seed, length_name, n)
        got = count(T.single_content(item))
        if abs(got - target) <= slack:
            return item, got
        n = max(0, n + round((target - got) / per))
    sys.exit(f"could not fit {length_name}: last {got} tokens for target {target}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--items", type=int, default=20, help="items per family")
    ap.add_argument("--first", type=int, default=0, help="index of the first item (pilot and measured sets differ)")
    ap.add_argument("--lengths", nargs="+", default=list(LENGTHS), choices=list(LENGTHS))
    ap.add_argument("--families", nargs="+", default=list(FAMILIES), choices=list(FAMILIES))
    ap.add_argument("--params", help="JSON overriding DEFAULTS, e.g. '{\"trace\": {\"depth\": 5}}'")
    a = ap.parse_args()
    from tokenizers import Tokenizer
    if hashlib.sha256(TOKENIZER.read_bytes()).hexdigest() != TOKENIZER_SHA256:
        sys.exit("tokenizer.json differs from the one earlier runs recorded")
    tok = Tokenizer.from_file(str(TOKENIZER))

    def count(text):
        return len(tok.encode(text, add_special_tokens=False).ids)

    params = {f: dict(v) for f, v in DEFAULTS.items()}
    for f, v in json.loads(a.params or "{}").items():
        params[f].update(v)
    out = Path(a.out)
    index = {"tokenizer_sha256": TOKENIZER_SHA256, "generator_sha256": sha256_text(Path(__file__).read_text()),
             "tasklib_sha256": sha256_text(Path(T.__file__).read_text()), "lengths": {k: LENGTHS[k] for k in a.lengths},
             "tolerance": TOLERANCE, "params": {f: params[f] for f in a.families}, "items": []}
    for f in a.families:
        (out / f).mkdir(parents=True, exist_ok=True)
        for i in range(a.first, a.first + a.items):
            seed = ITEM_SEED_BASE + FAMILIES.index(f) * 10_000 + i
            base = MAKE[f](seed, params[f])
            for ln in a.lengths:
                item, tokens = fit(base, seed, ln, LENGTHS[ln], count)
                if ORACLE[f](item) != item["answer"]:
                    sys.exit(f"oracle disagrees with the stored answer: {f} {i} {ln}")
                item.update(id=f"{f}-{i:03d}", family=f, index=i, seed=seed, length=ln, content_tokens=tokens,
                            content_sha256=sha256_text(T.single_content(item)))
                path = out / f / f"{f}-{i:03d}-{ln}.json"
                path.write_text(json.dumps(item, indent=0) + "\n")
                index["items"].append({"id": item["id"], "family": f, "index": i, "length": ln, "seed": seed,
                                       "file": f"{f}/{path.name}", "content_tokens": tokens,
                                       "content_sha256": item["content_sha256"], "records": len(item["records"]),
                                       "distractors": item["distractors"], "fields": len(item["answer"]),
                                       "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            print(f"{f}-{i:03d}", {r["length"]: r["content_tokens"] for r in index["items"][-len(a.lengths):]},
                  flush=True)
    (out / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    print(f"{len(index['items'])} rendered items -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
