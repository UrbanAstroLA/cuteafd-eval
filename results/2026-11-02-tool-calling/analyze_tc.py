#!/usr/bin/env python3
"""Block TC analysis (PROTOCOL.md reading rule). Standard library only; CPU.

    python3 analyze_tc.py            # writes ../tc/TC-SUMMARY.json and prints it

Per arm: points of 176 per repeat, pass/partial/fail, per-category points. Per scenario: status in every repeat.
Engine contrast per checkpoint (V vs C on K3.25 and K4): a scenario "differs" only when no vLLM repeat shares a status
with any CuteAFD repeat (the status sets are disjoint); scenarios whose status changes between repeats of one arm are
counted as unstable. K4-Core-K6 against K4, both CuteAFD, with the same rule. Gate R2: prompt_tokens per conversation.
Descriptive: no significance test.
"""
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent
ARMS = ["V-k325", "C-k325", "V-k4", "C-k4", "C-k6"]
PAIRS = [("V-k325", "C-k325"), ("V-k4", "C-k4"), ("C-k4", "C-k6")]


def load(arm):
    reps = []
    for n in (1, 2, 3):
        p = R / "tc" / f"{arm}-r{n}.json"
        if p.exists():
            reps.append(json.loads(p.read_text()))
    return reps


def main():
    out = {"arms": {}, "pairs": {}, "gate_r2": {}}
    status = {}
    for arm in ARMS:
        reps = load(arm)
        if not reps:
            continue
        a = {"repeats": [], "categories": {}}
        for d in reps:
            s = d["scores"]; sr = s["scenario_results"]
            assert s["total_points"] == sum(x["points"] for x in sr)
            a["repeats"].append({"points": s["total_points"], "max": s["max_points"],
                                 "pass": sum(x["status"] == "pass" for x in sr), "partial": sum(x["status"] == "partial" for x in sr),
                                 "fail": sum(x["status"] == "fail" for x in sr), "seed": d["metadata"].get("seed"),
                                 "model": d["metadata"].get("server_model_id"), "engine": d["metadata"].get("engine_name")})
            for c in s["category_scores"]:
                a["categories"].setdefault(c["label"], []).append(c["earned"])
            for x in sr:
                status.setdefault(arm, {}).setdefault(x["scenario_id"], []).append(x["status"])
        a["unstable"] = sorted(k for k, v in status[arm].items() if len(set(v)) > 1)
        out["arms"][arm] = a
        g = R / "gate" / f"{arm}.json"
        if g.exists():
            out["gate_r2"][arm] = json.loads(g.read_text())["prompt_tokens"]
    for x, y in PAIRS:
        if x in status and y in status:
            diff = sorted(k for k in status[x] if k in status[y] and not set(status[x][k]) & set(status[y][k]))
            out["pairs"][f"{y} vs {x}"] = {"differs": {k: {x: status[x][k], y: status[y][k]} for k in diff}}
    g = out["gate_r2"]
    out["gate_r2_pass"] = bool(g) and all(len({v[c] for v in g.values()}) == 1 for c in next(iter(g.values())))
    (R / "tc" / "TC-SUMMARY.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
