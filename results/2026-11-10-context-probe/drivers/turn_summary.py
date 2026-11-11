"""Exploratory reader: one line per comparison from turncheck/<arm>/<tag>/report.json, plus the repeat check.

usage: turn_summary.py <arm> [tag]
"""
import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent.parent
arm, tag = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "r0")
r = json.load(open(RUN / "turncheck" / arm / tag / "report.json"))
whats = []
for c in r["conversations"]:
    for p in c.get("pairs") or []:
        if p["what"] not in whats:
            whats.append(p["what"])
for i, w in enumerate(whats):
    print(i, w)
for c in r["conversations"]:
    t = c["turns"]
    lr = c.get("live_round_trip") or {}
    print(f"{c['item']:16s} {c['mode']:6s} ok={c['complete']} turns={len(t)} gen={sum(x['generated'] for x in t)} "
          f"fin={sorted({x['finish_reason'] for x in t})} rt_exact={lr.get('exact')} "
          f"live_cached={c.get('live_cached_tokens')}/{c.get('live_prompt_tokens')}")
    for p in c.get("pairs") or []:
        print(f"    [{whats.index(p['what'])}] rows {p['rows']:3d} hash_eq {p['hash_equal']:3d} "
              f"top1diff {p['top1_differs']} tokid {p['tokens_identical']}/{p['tokens_generated']} "
              f"kl mean {p['kl_mean']:.5f} max {p['kl_max']:.4f}")
rp = RUN / "repeat" / arm / tag / "report.json"
if rp.exists():
    q = json.load(open(rp))["summary"]
    print("repeat:", json.dumps({k: v for k, v in q.items() if k != "variants"}))
    print("variants:", [(v["count"], v["first_difference_char"]) for v in q.get("variants", [])])
